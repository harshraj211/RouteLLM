import json

import httpx
import pytest
from pydantic import HttpUrl

from routellm.adapters.anthropic import AnthropicInferenceAdapter
from routellm.adapters.base import InferenceAdapterError
from routellm.adapters.gemini import GeminiInferenceAdapter
from routellm.schemas.models import ModelDescriptor, ModelLatencyProfile, ModelPricing
from routellm.schemas.routing import Message, RouteRequest


def _model(*, provider: str, endpoint: str, model_id: str, api_key_env: str) -> ModelDescriptor:
    return ModelDescriptor(
        key=f"{provider}-test",
        provider=provider,
        display_name=f"{provider.title()} Test",
        model_id=model_id,
        endpoint=HttpUrl(endpoint),
        api_key_env=api_key_env,
        requires_api_key=True,
        quality_tier=3,
        supports_structured_output=True,
        max_context_tokens=100000,
        pricing=ModelPricing(
            input_cost_per_1k_tokens=0.001,
            output_cost_per_1k_tokens=0.002,
        ),
        latency=ModelLatencyProfile(p50_ms=100, p95_ms=300),
    )


def _request() -> RouteRequest:
    return RouteRequest(
        tenant_id="provider-tests",
        workflow_id="native-adapters",
        task_type="qa",
        messages=[
            Message(role="system", content="Be concise."),
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi"),
            Message(role="user", content="Return JSON"),
        ],
        max_budget_usd=0.1,
        latency_slo_ms=5000,
        response_format="json",
        max_output_tokens=64,
        temperature=0.2,
        top_p=0.8,
        stop=["END"],
    )


@pytest.mark.asyncio
async def test_anthropic_adapter_translates_messages_and_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-secret")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.anthropic.com/v1/messages"
        assert request.headers["x-api-key"] == "anthropic-secret"
        assert request.headers["anthropic-version"] == "2023-06-01"
        body = json.loads(request.content)
        assert body["system"] == "Be concise."
        assert body["model"] == "claude-test"
        assert body["max_tokens"] == 64
        assert body["messages"] == [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
            {"role": "user", "content": "Return JSON"},
        ]
        assert body["stop_sequences"] == ["END"]
        return httpx.Response(
            200,
            json={
                "id": "msg-test",
                "model": "claude-test-2026",
                "content": [{"type": "text", "text": '{"ok":true}'}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 12, "output_tokens": 6},
            },
        )

    model = _model(
        provider="anthropic",
        endpoint="https://api.anthropic.com/v1",
        model_id="claude-test",
        api_key_env="ANTHROPIC_API_KEY",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await AnthropicInferenceAdapter(client=client).invoke(_request(), model)

    assert result.text == '{"ok":true}'
    assert result.input_tokens == 12
    assert result.output_tokens == 6
    assert result.provider_request_id == "msg-test"
    assert result.finish_reason == "stop"


@pytest.mark.asyncio
async def test_gemini_adapter_translates_messages_config_and_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-secret")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == (
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent"
        )
        assert request.headers["x-goog-api-key"] == "gemini-secret"
        body = json.loads(request.content)
        assert body["systemInstruction"] == {"parts": [{"text": "Be concise."}]}
        assert body["contents"][1] == {"role": "model", "parts": [{"text": "Hi"}]}
        assert body["generationConfig"] == {
            "maxOutputTokens": 64,
            "temperature": 0.2,
            "topP": 0.8,
            "stopSequences": ["END"],
            "responseMimeType": "application/json",
        }
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {"parts": [{"text": '{"ok":'}, {"text": "true}"}]},
                        "finishReason": "MAX_TOKENS",
                    }
                ],
                "usageMetadata": {"promptTokenCount": 14, "candidatesTokenCount": 8},
                "modelVersion": "gemini-test-2026",
                "responseId": "gemini-response",
            },
        )

    model = _model(
        provider="gemini",
        endpoint="https://generativelanguage.googleapis.com/v1beta",
        model_id="gemini-test",
        api_key_env="GEMINI_API_KEY",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await GeminiInferenceAdapter(client=client).invoke(_request(), model)

    assert result.text == '{"ok":true}'
    assert result.input_tokens == 14
    assert result.output_tokens == 8
    assert result.provider_request_id == "gemini-response"
    assert result.provider_model == "gemini-test-2026"
    assert result.finish_reason == "length"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("adapter", "model"),
    [
        (
            AnthropicInferenceAdapter(),
            _model(
                provider="anthropic",
                endpoint="https://api.anthropic.com/v1",
                model_id="claude-test",
                api_key_env="MISSING_ANTHROPIC_KEY",
            ),
        ),
        (
            GeminiInferenceAdapter(),
            _model(
                provider="gemini",
                endpoint="https://generativelanguage.googleapis.com/v1beta",
                model_id="gemini-test",
                api_key_env="MISSING_GEMINI_KEY",
            ),
        ),
    ],
)
async def test_native_adapters_require_configured_api_key(
    adapter: AnthropicInferenceAdapter | GeminiInferenceAdapter,
    model: ModelDescriptor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert model.api_key_env is not None
    monkeypatch.delenv(model.api_key_env, raising=False)

    with pytest.raises(InferenceAdapterError) as error:
        await adapter.invoke(_request(), model)

    assert error.value.reason_code == "UPSTREAM_AUTH_CONFIGURATION_ERROR"
