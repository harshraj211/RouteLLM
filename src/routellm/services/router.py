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
from routellm.services.policy import PolicyEngine
from routellm.services.registry import InMemoryModelRegistry
from routellm.services.scoring import CandidateScorer


class RoutingService:
    def __init__(self, model_registry: InMemoryModelRegistry) -> None:
        self.model_registry = model_registry
        self.analyzer = RequestAnalyzer()
        self.policy_engine = PolicyEngine()
        self.scorer = CandidateScorer()

    async def route(self, request: RouteRequest) -> RouteResponse:
        started_at = perf_counter()
        analysis = self.analyzer.analyze(request)
        models = self.model_registry.list_models()
        policy = self.policy_engine.select_candidates(request, analysis, models)

        ranked = sorted(
            policy.candidates,
            key=lambda model: self.scorer.score(model, analysis),
            reverse=True,
        )
        selected = ranked[0]

        estimated_cost = self._estimate_cost(
            selected,
            analysis.estimated_input_tokens,
            analysis.estimated_output_tokens,
        )
        response_text = self._build_placeholder_response(request, selected)
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

    @staticmethod
    def _estimate_cost(
        model: ModelDescriptor,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
    ) -> float:
        return round(
            (estimated_input_tokens * model.pricing.input_cost_per_1k_tokens / 1000)
            + (estimated_output_tokens * model.pricing.output_cost_per_1k_tokens / 1000),
            6,
        )

    @staticmethod
    def _build_placeholder_response(request: RouteRequest, model: ModelDescriptor) -> str:
        return (
            f"RouteLLM selected '{model.key}' for task '{request.task_type}' "
            f"under budget ${request.max_budget_usd:.4f}."
        )

    @staticmethod
    def _persist_decision(request: RouteRequest, response: RouteResponse) -> None:
        session = get_session()
        try:
            RoutingDecisionRepository(session).create(request, response)
        finally:
            session.close()
