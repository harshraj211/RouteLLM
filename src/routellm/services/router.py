from fastapi import HTTPException

from time import perf_counter

from routellm.db.session import get_session
from routellm.observability.metrics import ESCALATION_COUNTER, REQUEST_COST, REQUEST_COUNTER, REQUEST_LATENCY
from routellm.repositories.routing_decisions import RoutingDecisionRepository
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
from routellm.services.execution import ExecutionService
from routellm.services.policy import PolicyEngine
from routellm.services.registry import InMemoryModelRegistry
from routellm.services.scoring import CandidateScorer
from routellm.workflows.routing import RoutingWorkflow


class RoutingService:
    def __init__(self, model_registry: InMemoryModelRegistry) -> None:
        self.model_registry = model_registry
        self.analyzer = RequestAnalyzer()
        self.budget_service = BudgetService()
        self.policy_engine = PolicyEngine()
        self.scorer = CandidateScorer()
        self.execution_service = ExecutionService()
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
        if len(ranked) > 1 and selected.quality_tier > ranked[-1].quality_tier:
            ESCALATION_COUNTER.labels(
                task_type=request.task_type,
                workflow_id=request.workflow_id,
            ).inc()

        response = RouteResponse(
            request_id=request.request_id,
            decision=RouteDecision(
                selected_model=selected.key,
                reason_codes=policy.reason_codes + ["BEST_SCORE_SELECTED"],
                estimated_input_tokens=analysis.estimated_input_tokens,
                estimated_output_tokens=analysis.estimated_output_tokens,
                estimated_cost_usd=estimated_cost,
                estimated_latency_ms=selected.latency.p95_ms,
            ),
            usage=RouteUsage(
                input_tokens=analysis.estimated_input_tokens,
                output_tokens=min(analysis.estimated_output_tokens, 120),
                actual_cost_usd=estimated_cost,
            ),
            escalation_path=[],
            output=RouteOutput(text=response_text),
        )
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

    @staticmethod
    def _persist_decision(request: RouteRequest, response: RouteResponse) -> None:
        session = get_session()
        try:
            RoutingDecisionRepository(session).create(request, response)
        finally:
            session.close()
