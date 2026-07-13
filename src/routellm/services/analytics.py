"""Cost and routing analytics calculated from persisted decisions."""

from collections import Counter, defaultdict
from collections.abc import Iterable

from routellm.db.models import RoutingDecisionRecord
from routellm.schemas.analytics import AnalyticsDecision, AnalyticsSummary, ModelUsageAnalytics
from routellm.schemas.models import ModelDescriptor

_LOCAL_PROVIDERS = frozenset({"ollama", "vllm"})
_LEGACY_LOCAL_MODEL_KEYS = frozenset({"local-small", "local-medium-json"})


class AnalyticsService:
    def summarize(
        self,
        records: Iterable[RoutingDecisionRecord],
        models: list[ModelDescriptor],
        *,
        baseline_model_key: str,
    ) -> AnalyticsSummary:
        decisions = list(records)
        model_by_key = {model.key: model for model in models}
        baseline_model = model_by_key.get(baseline_model_key)
        if baseline_model is None:
            raise ValueError(f"Analytics baseline model {baseline_model_key!r} is not configured.")

        request_count = len(decisions)
        local_request_count = sum(
            self._is_local(decision.selected_model, model_by_key) for decision in decisions
        )
        actual_spend = sum(decision.actual_cost_usd for decision in decisions)
        baseline_spend = sum(
            self._baseline_cost(decision, baseline_model) for decision in decisions
        )
        savings = max(0.0, baseline_spend - actual_spend)
        usage_counts = Counter(decision.selected_model for decision in decisions)
        usage_spend: dict[str, float] = defaultdict(float)
        for decision in decisions:
            usage_spend[decision.selected_model] += decision.actual_cost_usd

        escalation_count = sum(
            any(token in decision.reason_codes for token in ("ESCALATION", "FAILOVER"))
            for decision in decisions
        )
        average_latency = (
            sum(decision.estimated_latency_ms for decision in decisions) / request_count
            if request_count
            else 0.0
        )

        return AnalyticsSummary(
            request_count=request_count,
            local_request_count=local_request_count,
            cloud_request_count=request_count - local_request_count,
            escalation_count=escalation_count,
            average_estimated_latency_ms=round(average_latency, 2),
            actual_spend_usd=round(actual_spend, 6),
            reference_baseline_model=baseline_model_key,
            reference_baseline_spend_usd=round(baseline_spend, 6),
            estimated_savings_usd=round(savings, 6),
            estimated_savings_percent=(
                round((savings / baseline_spend) * 100, 2) if baseline_spend else 0.0
            ),
            model_usage=[
                ModelUsageAnalytics(
                    model_key=model_key,
                    request_count=usage_counts[model_key],
                    actual_spend_usd=round(usage_spend[model_key], 6),
                )
                for model_key in sorted(usage_counts)
            ],
        )

    def decisions(
        self,
        records: Iterable[RoutingDecisionRecord],
        models: list[ModelDescriptor],
        *,
        baseline_model_key: str,
    ) -> list[AnalyticsDecision]:
        model_by_key = {model.key: model for model in models}
        baseline_model = model_by_key.get(baseline_model_key)
        if baseline_model is None:
            raise ValueError(f"Analytics baseline model {baseline_model_key!r} is not configured.")

        return [
            AnalyticsDecision(
                id=record.id,
                created_at=record.created_at,
                request_id=record.request_id,
                task_type=record.task_type,
                selected_model=record.selected_model,
                is_local=self._is_local(record.selected_model, model_by_key),
                reason_codes=[code for code in record.reason_codes.split(",") if code],
                actual_cost_usd=record.actual_cost_usd,
                reference_baseline_cost_usd=round(
                    self._baseline_cost(record, baseline_model),
                    6,
                ),
                estimated_savings_usd=round(
                    max(0.0, self._baseline_cost(record, baseline_model) - record.actual_cost_usd),
                    6,
                ),
            )
            for record in records
        ]

    @staticmethod
    def _baseline_cost(record: RoutingDecisionRecord, baseline_model: ModelDescriptor) -> float:
        return (
            record.estimated_input_tokens * baseline_model.pricing.input_cost_per_1k_tokens / 1000
            + record.estimated_output_tokens
            * baseline_model.pricing.output_cost_per_1k_tokens
            / 1000
        )

    @staticmethod
    def _is_local(model_key: str, model_by_key: dict[str, ModelDescriptor]) -> bool:
        model = model_by_key.get(model_key)
        return (
            model_key in _LEGACY_LOCAL_MODEL_KEYS
            or (model is not None and model.provider in _LOCAL_PROVIDERS)
        )
