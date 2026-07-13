import pytest

from routellm.adapters.base import InferenceAdapter, InferenceAdapterError, InferenceResult
from routellm.config import Settings
from routellm.schemas.models import ModelDescriptor
from routellm.schemas.routing import Message, RouteRequest
from routellm.services.execution import ExecutionService
from routellm.services.registry import InMemoryModelRegistry
from routellm.services.router import RoutingService


class ScriptedAdapter(InferenceAdapter):
    def __init__(
        self,
        outcomes: dict[str, list[InferenceResult | InferenceAdapterError]],
    ) -> None:
        self.outcomes = outcomes
        self.calls: list[str] = []

    async def invoke(self, request: RouteRequest, model: ModelDescriptor) -> InferenceResult:
        self.calls.append(model.key)
        outcome = self.outcomes[model.key].pop(0)
        if isinstance(outcome, InferenceAdapterError):
            raise outcome
        return outcome


def _settings(*, max_retries: int = 1) -> Settings:
    return Settings(
        _env_file=None,
        inference_max_retries=max_retries,
        inference_retry_backoff_seconds=0,
    )


def _request(*, max_budget_usd: float = 0.01, latency_slo_ms: int = 3000) -> RouteRequest:
    return RouteRequest(
        tenant_id="transport-tests",
        workflow_id="fallback",
        task_type="qa",
        messages=[Message(role="user", content="Hello")],
        max_budget_usd=max_budget_usd,
        latency_slo_ms=latency_slo_ms,
    )


def _retryable_error(model_key: str) -> InferenceAdapterError:
    return InferenceAdapterError(
        "The upstream model returned HTTP 503.",
        model_key=model_key,
        status_code=503,
        retryable=True,
        reason_code="UPSTREAM_SERVER_ERROR",
    )


def _success(model_key: str) -> InferenceResult:
    return InferenceResult(
        text="Successful response from the selected fallback model.",
        input_tokens=4,
        output_tokens=10,
        latency_ms=25,
        provider_request_id=f"request-{model_key}",
        provider_model=model_key,
    )


def _service(adapter: ScriptedAdapter, settings: Settings) -> RoutingService:
    registry = InMemoryModelRegistry.bootstrap_defaults(settings)
    execution_service = ExecutionService(
        settings,
        adapters={"vllm": adapter, "hosted": adapter},
    )
    return RoutingService(registry, settings=settings, execution_service=execution_service)


@pytest.mark.asyncio
async def test_retry_can_recover_without_model_failover() -> None:
    adapter = ScriptedAdapter(
        {"local-small": [_retryable_error("local-small"), _success("local-small")]}
    )

    response = await _service(adapter, _settings()).route(_request())

    assert response.decision.selected_model == "local-small"
    assert adapter.calls == ["local-small", "local-small"]
    assert [attempt.outcome for attempt in response.execution_attempts] == [
        "retryable_error",
        "success",
    ]
    assert response.escalation_path == []


@pytest.mark.asyncio
async def test_retry_exhaustion_fails_over_to_next_ranked_model() -> None:
    adapter = ScriptedAdapter(
        {
            "local-small": [
                _retryable_error("local-small"),
                _retryable_error("local-small"),
            ],
            "local-medium-json": [_success("local-medium-json")],
        }
    )

    response = await _service(adapter, _settings()).route(_request())

    assert response.decision.selected_model == "local-medium-json"
    assert "TRANSPORT_FAILOVER_APPLIED" in response.decision.reason_codes
    assert adapter.calls == ["local-small", "local-small", "local-medium-json"]
    assert response.escalation_path[0].model_dump() == {
        "from_model": "local-small",
        "to_model": "local-medium-json",
        "reason_codes": [
            "UPSTREAM_SERVER_ERROR",
            "UPSTREAM_RETRIES_EXHAUSTED",
            "TRANSPORT_FAILOVER",
        ],
    }
    assert response.execution_attempts[-1].outcome == "success"


@pytest.mark.asyncio
async def test_non_retryable_failure_stops_without_retry_or_failover() -> None:
    error = InferenceAdapterError(
        "Authentication failed.",
        model_key="local-small",
        status_code=401,
        retryable=False,
        reason_code="UPSTREAM_CLIENT_ERROR",
    )
    adapter = ScriptedAdapter({"local-small": [error]})

    with pytest.raises(InferenceAdapterError) as raised:
        await _service(adapter, _settings()).route(_request())

    assert raised.value is error
    assert adapter.calls == ["local-small"]


@pytest.mark.asyncio
async def test_failover_skips_candidates_outside_request_budget() -> None:
    adapter = ScriptedAdapter(
        {
            "local-small": [
                _retryable_error("local-small"),
                _retryable_error("local-small"),
            ],
            "local-medium-json": [_success("local-medium-json")],
        }
    )

    with pytest.raises(InferenceAdapterError):
        await _service(adapter, _settings()).route(_request(max_budget_usd=0.0001))

    assert adapter.calls == ["local-small", "local-small"]


@pytest.mark.asyncio
async def test_all_affordable_candidates_exhausted_returns_last_error() -> None:
    outcomes: dict[str, list[InferenceResult | InferenceAdapterError]] = {}
    for model_key in ("local-small", "local-medium-json", "hosted-premium"):
        outcomes[model_key] = [
            _retryable_error(model_key),
            _retryable_error(model_key),
        ]
    adapter = ScriptedAdapter(outcomes)

    with pytest.raises(InferenceAdapterError) as raised:
        await _service(adapter, _settings()).route(_request(max_budget_usd=0.1))

    assert raised.value.model_key == "hosted-premium"
    assert adapter.calls == [
        "local-small",
        "local-small",
        "local-medium-json",
        "local-medium-json",
        "hosted-premium",
        "hosted-premium",
    ]
