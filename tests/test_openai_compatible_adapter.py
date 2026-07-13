import json

import httpx
import pytest
from pydantic import HttpUrl

from routellm.adapters.base import InferenceAdapterError
from routellm.adapters.openai_compatible import OpenAICompatibleInferenceAdapter
from routellm.schemas.models import ModelDescriptor, ModelLatencyProfile, ModelPricing
from routellm.schemas.routing import Message, RouteRequest


def _model() -> ModelDescriptor:
    return ModelDescriptor(
        key="test-model",
        provider="hosted",
        display_name="Test Model",
        model_id="provider-model-id",
        endpoint=HttpUrl("https://provider.test/v1"),
        api_key_env="TEST_PROVIDER_API_KEY",
        requires_api_key=True,
        quality_tier=2,
        supports_structured_output=True,
        max_context_tokens=8192,
        pricing=ModelPricing(
            input_cost_per_1k_tokens=0.001,
            output_cost_per_1k_tokens=0.002,
        ),
        latency=ModelLatencyProfile(p50_ms=100, p95_ms=500),
    )


def _request(*, response_format: str = "text") -> RouteRequest:
    return RouteRequest(
        tenant_id="tenant",
        workflow_id="workflow",
        task_type="qa",
        messages=[Message(role="user", content="Hello")],
        max_budget_usd=0.01,
        latency_slo_ms=1000,
        response_format=response_format,
    )


@pytest.mark.asyncio
async def test_adapter_calls_chat_completions_and_normalizes_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_PROVIDER_API_KEY", "secret-key")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://provider.test/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer secret-key"
        body = json.loads(request.content)
        assert body == {
            "model": "provider-model-id",
            "messages": [{"role": "user", "content": "Hello"}],
            "response_format": {"type": "json_object"},
        }
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "model": "provider-model-id-2026-01-01",
                "choices": [{"message": {"content": '{"answer":"ok"}'}, "finish_reason": "length"}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 5},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await OpenAICompatibleInferenceAdapter(client=client).invoke(
            _request(response_format="json"),
            _model(),
        )

    assert result.text == '{"answer":"ok"}'
    assert result.input_tokens == 7
    assert result.output_tokens == 5
    assert result.provider_request_id == "chatcmpl-test"
    assert result.provider_model == "provider-model-id-2026-01-01"
    assert result.finish_reason == "length"


@pytest.mark.asyncio
async def test_adapter_rejects_missing_required_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TEST_PROVIDER_API_KEY", raising=False)
    adapter = OpenAICompatibleInferenceAdapter()

    with pytest.raises(InferenceAdapterError, match="TEST_PROVIDER_API_KEY"):
        await adapter.invoke(_request(), _model())


@pytest.mark.asyncio
async def test_adapter_marks_rate_limit_as_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_PROVIDER_API_KEY", "secret-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, request=request, json={"error": {"message": "slow down"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OpenAICompatibleInferenceAdapter(client=client)
        with pytest.raises(InferenceAdapterError) as error:
            await adapter.invoke(_request(), _model())

    assert error.value.status_code == 429
    assert error.value.retryable is True
    assert error.value.reason_code == "UPSTREAM_RATE_LIMIT"


@pytest.mark.asyncio
async def test_adapter_does_not_retry_uncertain_read_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_PROVIDER_API_KEY", "secret-key")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("read timed out", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OpenAICompatibleInferenceAdapter(client=client)
        with pytest.raises(InferenceAdapterError) as error:
            await adapter.invoke(_request(), _model())

    assert error.value.retryable is False
    assert error.value.reason_code == "UPSTREAM_UNCERTAIN_TIMEOUT"


@pytest.mark.asyncio
async def test_adapter_forwards_generation_parameters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_PROVIDER_API_KEY", "secret-key")
    model = _model().model_copy(update={"max_output_tokens_param": "max_completion_tokens"})
    request = _request().model_copy(
        update={
            "max_output_tokens": 42,
            "temperature": 0.3,
            "top_p": 0.8,
            "stop": ["END"],
            "presence_penalty": 0.2,
            "frequency_penalty": -0.1,
            "seed": 7,
        }
    )

    def handler(http_request: httpx.Request) -> httpx.Response:
        body = json.loads(http_request.content)
        assert body["max_completion_tokens"] == 42
        assert body["temperature"] == 0.3
        assert body["top_p"] == 0.8
        assert body["stop"] == ["END"]
        assert body["presence_penalty"] == 0.2
        assert body["frequency_penalty"] == -0.1
        assert body["seed"] == 7
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "done"}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await OpenAICompatibleInferenceAdapter(client=client).invoke(request, model)

    assert result.text == "done"
