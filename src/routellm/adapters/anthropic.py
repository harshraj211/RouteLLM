import os
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from routellm.adapters.base import InferenceAdapter, InferenceAdapterError, InferenceResult
from routellm.adapters.http import post_json
from routellm.schemas.models import ModelDescriptor
from routellm.schemas.routing import RouteRequest


class _AnthropicContentBlock(BaseModel):
    type: str
    text: str | None = None


class _AnthropicUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class _AnthropicResponse(BaseModel):
    id: str | None = None
    model: str | None = None
    content: list[_AnthropicContentBlock]
    stop_reason: str | None = None
    usage: _AnthropicUsage


class AnthropicInferenceAdapter(InferenceAdapter):
    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self._client = client

    async def invoke(self, request: RouteRequest, model: ModelDescriptor) -> InferenceResult:
        if model.endpoint is None:
            raise InferenceAdapterError(
                "The selected Anthropic model has no endpoint configured.",
                model_key=model.key,
                reason_code="UPSTREAM_CONFIGURATION_ERROR",
            )
        api_key = os.getenv(model.api_key_env) if model.api_key_env else None
        if model.requires_api_key and not api_key:
            raise InferenceAdapterError(
                f"Required API key environment variable {model.api_key_env!r} is not set.",
                model_key=model.key,
                reason_code="UPSTREAM_AUTH_CONFIGURATION_ERROR",
            )

        system_parts = [
            message.content
            for message in request.messages
            if message.role in {"system", "developer"}
        ]
        messages = [
            {
                "role": "assistant" if message.role == "assistant" else "user",
                "content": message.content,
            }
            for message in request.messages
            if message.role not in {"system", "developer"}
        ]
        payload: dict[str, Any] = {
            "model": model.model_id,
            "max_tokens": request.max_output_tokens
            or (256 if request.response_format == "json" else 180),
            "messages": messages,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        if model.supports_sampling_parameters and request.temperature is not None:
            payload["temperature"] = request.temperature
        if model.supports_sampling_parameters and request.top_p is not None:
            payload["top_p"] = request.top_p
        if request.stop is not None:
            payload["stop_sequences"] = (
                request.stop if isinstance(request.stop, list) else [request.stop]
            )

        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        if api_key:
            headers["x-api-key"] = api_key
        endpoint = f"{str(model.endpoint).rstrip('/')}/messages"
        if self._client is not None:
            return await self._invoke_client(self._client, endpoint, headers, payload, model)
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            return await self._invoke_client(client, endpoint, headers, payload, model)

    async def _invoke_client(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        model: ModelDescriptor,
    ) -> InferenceResult:
        data, latency_ms = await post_json(
            client,
            endpoint=endpoint,
            headers=headers,
            payload=payload,
            model=model,
        )
        try:
            response = _AnthropicResponse.model_validate(data)
        except ValidationError as exc:
            raise InferenceAdapterError(
                "Anthropic returned an invalid Messages response.",
                model_key=model.key,
                reason_code="UPSTREAM_INVALID_RESPONSE",
            ) from exc
        text = "".join(block.text or "" for block in response.content if block.type == "text")
        if not text:
            raise InferenceAdapterError(
                "Anthropic returned no text content.",
                model_key=model.key,
                reason_code="UPSTREAM_EMPTY_RESPONSE",
            )
        return InferenceResult(
            text=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=latency_ms,
            provider_request_id=response.id,
            provider_model=response.model,
            finish_reason="length" if response.stop_reason == "max_tokens" else "stop",
        )
