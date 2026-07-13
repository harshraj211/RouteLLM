from pydantic import HttpUrl

from routellm.schemas.models import ModelDescriptor, ModelLatencyProfile, ModelPricing
from routellm.schemas.routing import Message, RouteRequest
from routellm.services.evaluation import ResponseEvaluator


def _request(*, response_format: str = "text") -> RouteRequest:
    return RouteRequest(
        tenant_id="test",
        workflow_id="evaluation",
        task_type="qa",
        messages=[Message(role="user", content="Help me")],
        max_budget_usd=0,
        latency_slo_ms=1000,
        response_format=response_format,
    )


def _model() -> ModelDescriptor:
    return ModelDescriptor(
        key="local-coder",
        provider="ollama",
        display_name="Local Coder",
        model_id="qwen2.5-coder:7b",
        endpoint=HttpUrl("http://localhost:11434/v1"),
        quality_tier=3,
        max_context_tokens=32768,
        pricing=ModelPricing(input_cost_per_1k_tokens=0, output_cost_per_1k_tokens=0),
        latency=ModelLatencyProfile(p50_ms=900, p95_ms=2500),
    )


def test_evaluator_rejects_invalid_json_for_escalation() -> None:
    result = ResponseEvaluator().evaluate(_request(response_format="json"), _model(), "not json")

    assert result.accepted is False
    assert "JSON_OUTPUT_INVALID" in result.reason_codes
    assert "ESCALATION_RECOMMENDED" in result.reason_codes


def test_evaluator_rejects_model_decline() -> None:
    result = ResponseEvaluator().evaluate(
        _request(),
        _model(),
        "I cannot complete this task because there is insufficient information available.",
    )

    assert result.accepted is False
    assert "MODEL_DECLINED_TASK" in result.reason_codes


def test_evaluator_accepts_valid_substantive_json() -> None:
    result = ResponseEvaluator().evaluate(
        _request(response_format="json"),
        _model(),
        '{"result":"A valid structured response with enough useful detail to be credible."}',
    )

    assert result.accepted is True
    assert "JSON_OUTPUT_VALID" in result.reason_codes
    assert "EARLY_EXIT_ACCEPTED" in result.reason_codes


def test_evaluator_accepts_intentionally_brief_response() -> None:
    request = _request()
    request.messages = [Message(role="user", content="Say OK!")]

    result = ResponseEvaluator().evaluate(request, _model(), "OK!")

    assert result.accepted is True
    assert "BRIEF_RESPONSE_EXPECTED" in result.reason_codes
    assert "ESCALATION_RECOMMENDED" not in result.reason_codes
