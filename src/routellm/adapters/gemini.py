import os
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import BaseModel, Field, ValidationError

from routellm.adapters.base import InferenceAdapter, InferenceAdapterError, InferenceResult
from routellm.adapters.http import post_json
from routellm.schemas.models import ModelDescriptor
from routellm.schemas.routing import RouteRequest


class _GeminiPart(BaseModel):
    text: str | None = None


class _GeminiContent(BaseModel):
    parts: list[_GeminiPart]


class _GeminiCandidate(BaseModel):
    content: _GeminiContent
    finish_reason: str | None = Field(default=None, alias="finishReason")


class _GeminiUsage(BaseModel):
    prompt_token_count: int = Field(default=0, alias="promptTokenCount")
    candidates_token_count: int = Field(default=0, alias="candidatesTokenCount")


class _GeminiResponse(BaseModel):
    candidates: list[_GeminiCandidate]
    usage: _GeminiUsage = Field(default_factory=_GeminiUsage, alias="usageMetadata")
    model_version: str | None = Field(default=None, alias="modelVersion")
    response_id: str | None = Field(default=None, alias="responseId")


class GeminiInferenceAdapter(InferenceAdapter):
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
                "The selected Gemini model has no endpoint configured.",
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
        contents = [
            {
                "role": "model" if message.role == "assistant" else "user",
                "parts": [{"text": message.content}],
            }
            for message in request.messages
            if message.role not in {"system", "developer"}
        ]
        generation_config: dict[str, Any] = {}
        if request.max_output_tokens is not None:
            generation_config["maxOutputTokens"] = request.max_output_tokens
        if request.temperature is not None:
            generation_config["temperature"] = request.temperature
        if request.top_p is not None:
            generation_config["topP"] = request.top_p
        if request.stop is not None:
            generation_config["stopSequences"] = (
                request.stop if isinstance(request.stop, list) else [request.stop]
            )
        if request.response_format == "json":
            generation_config["responseMimeType"] = "application/json"

        payload: dict[str, Any] = {"contents": contents}
        if system_parts:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
        if generation_config:
            payload["generationConfig"] = generation_config
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["x-goog-api-key"] = api_key
        model_id = quote(model.model_id.removeprefix("models/"), safe="")
        endpoint = f"{str(model.endpoint).rstrip('/')}/models/{model_id}:generateContent"
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
            response = _GeminiResponse.model_validate(data)
            candidate = response.candidates[0]
        except (IndexError, ValidationError) as exc:
            raise InferenceAdapterError(
                "Gemini returned an invalid GenerateContent response.",
                model_key=model.key,
                reason_code="UPSTREAM_INVALID_RESPONSE",
            ) from exc
        text = "".join(part.text or "" for part in candidate.content.parts)
        if not text:
            raise InferenceAdapterError(
                "Gemini returned no text content.",
                model_key=model.key,
                reason_code="UPSTREAM_EMPTY_RESPONSE",
            )
        return InferenceResult(
            text=text,
            input_tokens=response.usage.prompt_token_count,
            output_tokens=response.usage.candidates_token_count,
            latency_ms=latency_ms,
            provider_request_id=response.response_id,
            provider_model=response.model_version or model.model_id,
            finish_reason="length" if candidate.finish_reason == "MAX_TOKENS" else "stop",
        )
