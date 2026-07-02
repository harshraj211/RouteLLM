from fastapi import HTTPException

from time import perf_counter

from routellm.db.session import get_session
from routellm.observability.metrics import ESCALATION_COUNTER, REQUEST_COST, REQUEST_COUNTER, REQUEST_LATENCY
from routellm.repositories.routing_decisions import RoutingDecisionRepository
from routellm.schemas.escalation import EscalationAttempt
from routellm.schemas.models import ModelDescriptor
from routellm.schemas.routing import (
    RouteDecision,
    RouteOutput,
    RouteRequest,
    RouteResponse,
    RouteUsage,
)
from routellm.services.analyzer import RequestAnalyzer
from routellm.services.budget import BudgetExceededError, BudgetService
from routellm.services.evaluation import ResponseEvaluator
from routellm.services.execution import ExecutionService
from routellm.services.policy import PolicyEngine
from routellm.services.registry import InMemoryModelRegistry
from routellm.services.scoring import CandidateScorer
from routellm.services.tenant_budgets import InMemoryTenantBudgetLedger
from routellm.workflows.routing import RoutingWorkflow


class RoutingService:
    def __init__(self, model_registry: InMemoryModelRegistry) -> None:
        self.model_registry = model_registry
        self.analyzer = RequestAnalyzer()
        self.budget_service = BudgetService()
        self.evaluator = ResponseEvaluator()
        self.policy_engine = PolicyEngine()
        self.scorer = CandidateScorer()
        self.execution_service = ExecutionService()
        self.budget_ledger = InMemoryTenantBudgetLedger()
        self.workflow = RoutingWorkflow(self.analyzer, self.policy_engine, self.scorer)

    async def route(self, request: RouteRequest) -> RouteResponse:
        started_at = perf_counter()
        models = self.model_registry.list_models()
        workflow_state = self.workflow.run(request, models)
        analysis = workflow_state["analysis"]
        policy = workflow_state["policy"]
        ranked = workflow_state["ranked_candidates"]
        selected, estimated_cost = self._select_affordable_candidate(
            ranked,
            request.max_budget_usd,
            analysis.estimated_input_tokens,
            analysis.estimated_output_tokens,
        )
        response_text = await self.execution_service.invoke(request, selected)
        evaluation = self.evaluator.evaluate(request, selected, response_text)
        escalation_path: list[EscalationAttempt] = []

        if not evaluation.accepted:
            alternate = self._find_next_affordable_candidate(
                ranked=ranked,
                current_model_key=selected.key,
                max_budget_usd=request.max_budget_usd,
                estimated_input_tokens=analysis.estimated_input_tokens,
                estimated_output_tokens=analysis.estimated_output_tokens,
            )
            if alternate is not None:
                escalation_path.append(
                    EscalationAttempt(
                        from_model=selected.key,
                        to_model=alternate.key,
                        reason_codes=evaluation.reason_codes,
                    )
                )
                selected = alternate
                estimated_cost = self.budget_service.ensure_within_budget(
                    selected,
                    estimated_input_tokens=analysis.estimated_input_tokens,
                    estimated_output_tokens=analysis.estimated_output_tokens,
                    max_budget_usd=request.max_budget_usd,
                )
                response_text = await self.execution_service.invoke(request, selected)
                evaluation = self.evaluator.evaluate(request, selected, response_text)

        latency_seconds = perf_counter() - started_at

        REQUEST_COUNTER.labels(
            task_type=request.task_type,
            workflow_id=request.workflow_id,
            selected_model=selected.key,
        ).inc()
        REQUEST_LATENCY.labels(
            task_type=request.task_type,
            workflow_id=request.workflow_id,
            selected_model=selected.key,
        ).observe(latency_seconds)
        REQUEST_COST.labels(
            task_type=request.task_type,
            workflow_id=request.workflow_id,
            selected_model=selected.key,
        ).observe(estimated_cost)
        if not evaluation.accepted:
            ESCALATION_COUNTER.labels(
                task_type=request.task_type,
                workflow_id=request.workflow_id,
            ).inc()

        response = RouteResponse(
            request_id=request.request_id,
            decision=RouteDecision(
                selected_model=selected.key,
                reason_codes=policy.reason_codes + ["BEST_SCORE_SELECTED"] + evaluation.reason_codes,
                estimated_input_tokens=analysis.estimated_input_tokens,
                estimated_output_tokens=analysis.estimated_output_tokens,
                estimated_cost_usd=estimated_cost,
                estimated_latency_ms=selected.latency.p95_ms,
            ),
            evaluation=evaluation,
            usage=RouteUsage(
                input_tokens=analysis.estimated_input_tokens,
                output_tokens=min(analysis.estimated_output_tokens, 120),
                actual_cost_usd=estimated_cost,
            ),
            escalation_path=escalation_path,
            output=RouteOutput(text=response_text),
        )
        self.budget_ledger.record_spend(request.tenant_id, response.usage.actual_cost_usd)
        self._persist_decision(request, response)
        return response

    def _select_affordable_candidate(
        self,
        ranked: list[ModelDescriptor],
        max_budget_usd: float,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
    ) -> tuple[ModelDescriptor, float]:
        for model in ranked:
            try:
                estimated_cost = self.budget_service.ensure_within_budget(
                    model,
                    estimated_input_tokens=estimated_input_tokens,
                    estimated_output_tokens=estimated_output_tokens,
                    max_budget_usd=max_budget_usd,
                )
                return model, estimated_cost
            except BudgetExceededError:
                continue

        raise HTTPException(
            status_code=400,
            detail="No candidate model satisfies the request budget.",
        )

    def _find_next_affordable_candidate(
        self,
        ranked: list[ModelDescriptor],
        current_model_key: str,
        max_budget_usd: float,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
    ) -> ModelDescriptor | None:
        seen_current = False
        for model in ranked:
            if model.key == current_model_key:
                seen_current = True
                continue
            if not seen_current:
                continue
            try:
                self.budget_service.ensure_within_budget(
                    model,
                    estimated_input_tokens=estimated_input_tokens,
                    estimated_output_tokens=estimated_output_tokens,
                    max_budget_usd=max_budget_usd,
                )
                return model
            except BudgetExceededError:
                continue
        return None

    @staticmethod
    def _persist_decision(request: RouteRequest, response: RouteResponse) -> None:
        session = get_session()
        try:
            RoutingDecisionRepository(session).create(request, response)
        finally:
            session.close()
