from asyncio import sleep
from time import perf_counter

from fastapi import HTTPException

from routellm.adapters.base import InferenceAdapterError, InferenceResult
from routellm.config import Settings, get_settings
from routellm.db.session import get_session
from routellm.observability.metrics import (
    ESCALATION_COUNTER,
    INFERENCE_FAILURE_COUNTER,
    INFERENCE_RETRY_COUNTER,
    MODEL_FAILOVER_COUNTER,
    REQUEST_COST,
    REQUEST_COUNTER,
    REQUEST_LATENCY,
)
from routellm.repositories.routing_decisions import RoutingDecisionRepository
from routellm.schemas.escalation import EscalationAttempt, InferenceAttempt
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
from routellm.services.registry import ModelRegistry
from routellm.services.scoring import CandidateScorer
from routellm.services.tenant_budgets import InMemoryTenantBudgetLedger
from routellm.workflows.routing import RoutingWorkflow


class RoutingService:
    def __init__(
        self,
        model_registry: ModelRegistry,
        settings: Settings | None = None,
        execution_service: ExecutionService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.model_registry = model_registry
        self.analyzer = RequestAnalyzer()
        self.budget_service = BudgetService()
        self.evaluator = ResponseEvaluator()
        self.policy_engine = PolicyEngine()
        self.scorer = CandidateScorer()
        self.execution_service = execution_service or ExecutionService(self.settings)
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
        escalation_path: list[EscalationAttempt] = []
        execution_attempts: list[InferenceAttempt] = []
        selected, estimated_cost, execution = await self._execute_with_failover(
            request=request,
            ranked=ranked,
            selected=selected,
            estimated_cost=estimated_cost,
            estimated_input_tokens=analysis.estimated_input_tokens,
            estimated_output_tokens=analysis.estimated_output_tokens,
            escalation_path=escalation_path,
            execution_attempts=execution_attempts,
        )
        evaluation = self.evaluator.evaluate(request, selected, execution.text)

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
                alternate_cost = self.budget_service.ensure_within_budget(
                    alternate,
                    estimated_input_tokens=analysis.estimated_input_tokens,
                    estimated_output_tokens=analysis.estimated_output_tokens,
                    max_budget_usd=request.max_budget_usd,
                )
                selected, estimated_cost, execution = await self._execute_with_failover(
                    request=request,
                    ranked=ranked,
                    selected=alternate,
                    estimated_cost=alternate_cost,
                    estimated_input_tokens=analysis.estimated_input_tokens,
                    estimated_output_tokens=analysis.estimated_output_tokens,
                    escalation_path=escalation_path,
                    execution_attempts=execution_attempts,
                )
                evaluation = self.evaluator.evaluate(request, selected, execution.text)

        actual_input_tokens = execution.input_tokens or analysis.estimated_input_tokens
        actual_output_tokens = execution.output_tokens or min(analysis.estimated_output_tokens, 120)
        actual_cost = self.budget_service.estimate_cost(
            selected,
            estimated_input_tokens=actual_input_tokens,
            estimated_output_tokens=actual_output_tokens,
        )

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
        ).observe(actual_cost)
        if escalation_path:
            ESCALATION_COUNTER.labels(
                task_type=request.task_type,
                workflow_id=request.workflow_id,
            ).inc()

        selected_provider = selected.provider_family or selected.provider
        decision_reason_codes = policy.reason_codes + [
            "BEST_SCORE_SELECTED",
            f"PROVIDER_{selected_provider.upper()}_SELECTED",
        ]
        if any("TRANSPORT_FAILOVER" in attempt.reason_codes for attempt in escalation_path):
            decision_reason_codes.append("TRANSPORT_FAILOVER_APPLIED")
        if any("ESCALATION_RECOMMENDED" in attempt.reason_codes for attempt in escalation_path):
            decision_reason_codes.append("RESPONSE_EVALUATION_ESCALATION_APPLIED")
        decision_reason_codes.extend(evaluation.reason_codes)

        response = RouteResponse(
            request_id=request.request_id,
            decision=RouteDecision(
                selected_model=selected.key,
                selected_provider=selected_provider,
                reason_codes=decision_reason_codes,
                estimated_input_tokens=analysis.estimated_input_tokens,
                estimated_output_tokens=analysis.estimated_output_tokens,
                estimated_cost_usd=estimated_cost,
                estimated_latency_ms=selected.latency.p95_ms,
            ),
            evaluation=evaluation,
            usage=RouteUsage(
                input_tokens=actual_input_tokens,
                output_tokens=actual_output_tokens,
                actual_cost_usd=actual_cost,
                latency_ms=execution.latency_ms,
                provider_request_id=execution.provider_request_id,
                provider_model=execution.provider_model,
            ),
            execution_attempts=execution_attempts,
            escalation_path=escalation_path,
            output=RouteOutput(
                text=execution.text,
                finish_reason=execution.finish_reason,
            ),
        )
        self.budget_ledger.record_spend(request.tenant_id, response.usage.actual_cost_usd)
        self._persist_decision(request, response)
        return response

    async def _execute_with_failover(
        self,
        *,
        request: RouteRequest,
        ranked: list[ModelDescriptor],
        selected: ModelDescriptor,
        estimated_cost: float,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
        escalation_path: list[EscalationAttempt],
        execution_attempts: list[InferenceAttempt],
    ) -> tuple[ModelDescriptor, float, InferenceResult]:
        current = selected
        current_cost = estimated_cost

        while True:
            try:
                execution = await self._invoke_with_retries(
                    request,
                    current,
                    execution_attempts,
                )
                return current, current_cost, execution
            except InferenceAdapterError as exc:
                if not exc.retryable:
                    raise

                alternate = self._find_next_affordable_candidate(
                    ranked=ranked,
                    current_model_key=current.key,
                    max_budget_usd=request.max_budget_usd,
                    estimated_input_tokens=estimated_input_tokens,
                    estimated_output_tokens=estimated_output_tokens,
                )
                if alternate is None:
                    raise

                escalation_path.append(
                    EscalationAttempt(
                        from_model=current.key,
                        to_model=alternate.key,
                        reason_codes=[
                            exc.reason_code,
                            "UPSTREAM_RETRIES_EXHAUSTED",
                            "TRANSPORT_FAILOVER",
                        ],
                    )
                )
                MODEL_FAILOVER_COUNTER.labels(
                    from_model=current.key,
                    to_model=alternate.key,
                    reason_code=exc.reason_code,
                ).inc()
                current = alternate
                current_cost = self.budget_service.ensure_within_budget(
                    current,
                    estimated_input_tokens=estimated_input_tokens,
                    estimated_output_tokens=estimated_output_tokens,
                    max_budget_usd=request.max_budget_usd,
                )

    async def _invoke_with_retries(
        self,
        request: RouteRequest,
        model: ModelDescriptor,
        execution_attempts: list[InferenceAttempt],
    ) -> InferenceResult:
        for attempt_index in range(self.settings.inference_max_retries + 1):
            attempt_number = attempt_index + 1
            try:
                result = await self.execution_service.invoke(request, model)
                execution_attempts.append(
                    InferenceAttempt(
                        model=model.key,
                        attempt_number=attempt_number,
                        outcome="success",
                        reason_codes=["UPSTREAM_SUCCESS"],
                    )
                )
                return result
            except InferenceAdapterError as exc:
                execution_attempts.append(
                    InferenceAttempt(
                        model=model.key,
                        attempt_number=attempt_number,
                        outcome="retryable_error" if exc.retryable else "error",
                        reason_codes=[exc.reason_code],
                        status_code=exc.status_code,
                    )
                )
                INFERENCE_FAILURE_COUNTER.labels(
                    model=model.key,
                    reason_code=exc.reason_code,
                    retryable=str(exc.retryable).lower(),
                ).inc()

                if not exc.retryable or attempt_index >= self.settings.inference_max_retries:
                    raise

                INFERENCE_RETRY_COUNTER.labels(
                    model=model.key,
                    reason_code=exc.reason_code,
                ).inc()
                backoff_seconds = self.settings.inference_retry_backoff_seconds * (2**attempt_index)
                if backoff_seconds > 0:
                    await sleep(backoff_seconds)

        raise RuntimeError("Inference retry loop exited unexpectedly.")

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
