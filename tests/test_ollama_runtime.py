import httpx
import pytest
from pydantic import HttpUrl

from routellm.schemas.models import ModelDescriptor, ModelLatencyProfile, ModelPricing
from routellm.services.ollama_runtime import OllamaRuntimeService


def _model(key: str, model_id: str) -> ModelDescriptor:
    return ModelDescriptor(
        key=key,
        provider="ollama",
        display_name=key,
        model_id=model_id,
        endpoint=HttpUrl("http://localhost:11434/v1"),
        quality_tier=1,
        max_context_tokens=8192,
        pricing=ModelPricing(input_cost_per_1k_tokens=0, output_cost_per_1k_tokens=0),
        latency=ModelLatencyProfile(p50_ms=100, p95_ms=200),
    )


@pytest.mark.asyncio
async def test_inspect_reports_installed_and_missing_configured_models() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://localhost:11434/api/tags"
        return httpx.Response(200, json={"models": [{"name": "qwen2.5:3b"}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        statuses = await OllamaRuntimeService(client=client).inspect(
            [_model("local-fast", "qwen2.5:3b"), _model("local-coder", "qwen2.5-coder:7b")]
        )

    assert len(statuses) == 1
    assert statuses[0].reachable is True
    assert [item.installed for item in statuses[0].configured_models] == [True, False]
    assert statuses[0].installed_models == ["qwen2.5:3b"]
    assert statuses[0].detail == "Missing configured models: qwen2.5-coder:7b"


@pytest.mark.asyncio
async def test_inspect_reports_unreachable_ollama() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        statuses = await OllamaRuntimeService(client=client).inspect(
            [_model("local-fast", "qwen2.5:3b")]
        )

    assert statuses[0].reachable is False
    assert statuses[0].configured_models[0].installed is False
    assert statuses[0].installed_models == []
    assert "Could not reach Ollama" in (statuses[0].detail or "")
