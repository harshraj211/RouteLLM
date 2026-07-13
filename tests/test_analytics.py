from routellm.db.models import RoutingDecisionRecord
from routellm.schemas.models import ModelDescriptor, ModelLatencyProfile, ModelPricing
from routellm.services.analytics import AnalyticsService


def _model(key: str, provider: str, input_cost: float, output_cost: float) -> ModelDescriptor:
    return ModelDescriptor(
        key=key,
        provider=provider,
        display_name=key,
        model_id=key,
        quality_tier=1,
        max_context_tokens=8192,
        pricing=ModelPricing(
            input_cost_per_1k_tokens=input_cost,
            output_cost_per_1k_tokens=output_cost,
        ),
        latency=ModelLatencyProfile(p50_ms=100, p95_ms=200),
    )


def _record(
    record_id: int,
    model_key: str,
    actual_cost: float,
    reason_codes: str = "BEST_SCORE_SELECTED",
) -> RoutingDecisionRecord:
    return RoutingDecisionRecord(
        id=record_id,
        request_id=f"request-{record_id}",
        tenant_id="demo",
        workflow_id="analytics",
        task_type="qa",
        selected_model=model_key,
        reason_codes=reason_codes,
        estimated_input_tokens=1000,
        estimated_output_tokens=1000,
        estimated_cost_usd=actual_cost,
        actual_cost_usd=actual_cost,
        estimated_latency_ms=200,
    )


def test_summary_calculates_savings_against_reference_cloud_model() -> None:
    local = _model("local-fast", "ollama", 0, 0)
    baseline = _model("cloud-reference", "hosted", 0.01, 0.03)
    records = [
        _record(1, "local-fast", 0),
        _record(2, "cloud-reference", 0.03, "ESCALATION_RECOMMENDED"),
    ]

    summary = AnalyticsService().summarize(
        records,
        [local, baseline],
        baseline_model_key="cloud-reference",
    )

    assert summary.request_count == 2
    assert summary.local_request_count == 1
    assert summary.cloud_request_count == 1
    assert summary.escalation_count == 1
    assert summary.actual_spend_usd == 0.03
    assert summary.reference_baseline_spend_usd == 0.08
    assert summary.estimated_savings_usd == 0.05
    assert summary.estimated_savings_percent == 62.5


def test_decisions_mark_local_routes_and_calculate_per_request_savings() -> None:
    local = _model("local-fast", "ollama", 0, 0)
    baseline = _model("cloud-reference", "hosted", 0.01, 0.03)

    decisions = AnalyticsService().decisions(
        [_record(1, "local-fast", 0)],
        [local, baseline],
        baseline_model_key="cloud-reference",
    )

    assert decisions[0].is_local is True
    assert decisions[0].reference_baseline_cost_usd == 0.04
    assert decisions[0].estimated_savings_usd == 0.04


def test_decisions_preserve_legacy_local_model_classification() -> None:
    baseline = _model("cloud-reference", "hosted", 0.01, 0.03)

    decisions = AnalyticsService().decisions(
        [_record(1, "local-medium-json", 0)],
        [baseline],
        baseline_model_key="cloud-reference",
    )

    assert decisions[0].is_local is True
