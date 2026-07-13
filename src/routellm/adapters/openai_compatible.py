import os
from time import perf_counter
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from routellm.adapters.base import InferenceAdapter, InferenceAdapterError, InferenceResult
from routellm.schemas.models import ModelDescriptor
from routellm.schemas.routing import RouteRequest


class _ResponseMessage(BaseModel):
    content: str | None = None


class _ResponseChoice(BaseModel):
    message: _ResponseMessage
    finish_reason: str | None = None


class _ResponseUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0


class _ChatCompletionResponse(BaseModel):
    id: str | None = None
    model: str | None = None
    choices: list[_ResponseChoice]
    usage: _ResponseUsage | None = None


class OpenAICompatibleInferenceAdapter(InferenceAdapter):
    """Calls an OpenAI-compatible Chat Completions endpoint."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.api_key = api_key
        self._client = client

    async def invoke(self, request: RouteRequest, model: ModelDescriptor) -> InferenceResult:
        if model.endpoint is None:
            raise InferenceAdapterError(
                "The selected model has no upstream endpoint configured.",
                model_key=model.key,
                reason_code="UPSTREAM_CONFIGURATION_ERROR",
            )

        api_key = self.api_key or (os.getenv(model.api_key_env) if model.api_key_env else None)
        if model.requires_api_key and not api_key:
            raise InferenceAdapterError(
                f"Required API key environment variable {model.api_key_env!r} is not set.",
                model_key=model.key,
                reason_code="UPSTREAM_AUTH_CONFIGURATION_ERROR",
            )

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload: dict[str, Any] = {
            "model": model.model_id,
            "messages": [message.model_dump() for message in request.messages],
        }
        if request.response_format == "json":
            payload["response_format"] = {"type": "json_object"}
        if request.max_output_tokens is not None:
            payload[model.max_output_tokens_param] = request.max_output_tokens
        for parameter in (
            "temperature",
            "top_p",
            "stop",
            "presence_penalty",
            "frequency_penalty",
            "seed",
        ):
            value = getattr(request, parameter)
            if value is not None:
                payload[parameter] = value

        endpoint = f"{str(model.endpoint).rstrip('/')}/chat/completions"
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
        started_at = perf_counter()
        try:
            response = await client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
        except (httpx.ConnectTimeout, httpx.PoolTimeout) as exc:
            raise InferenceAdapterError(
                "The upstream model connection timed out.",
                model_key=model.key,
                retryable=True,
                reason_code="UPSTREAM_CONNECTION_TIMEOUT",
            ) from exc
        except (httpx.ReadTimeout, httpx.WriteTimeout) as exc:
            raise InferenceAdapterError(
                "The upstream model timed out after transmission may have started.",
                model_key=model.key,
                retryable=False,
                reason_code="UPSTREAM_UNCERTAIN_TIMEOUT",
            ) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            raise InferenceAdapterError(
                f"The upstream model returned HTTP {status_code}.",
                model_key=model.key,
                status_code=status_code,
                retryable=status_code == 429 or status_code >= 500,
                reason_code=(
                    "UPSTREAM_RATE_LIMIT"
                    if status_code == 429
                    else "UPSTREAM_SERVER_ERROR"
                    if status_code >= 500
                    else "UPSTREAM_CLIENT_ERROR"
                ),
            ) from exc
        except httpx.ConnectError as exc:
            raise InferenceAdapterError(
                "The upstream model could not be reached.",
                model_key=model.key,
                retryable=True,
                reason_code="UPSTREAM_CONNECTION_ERROR",
            ) from exc
        except httpx.RequestError as exc:
            raise InferenceAdapterError(
                "The upstream connection failed after transmission may have started.",
                model_key=model.key,
                retryable=False,
                reason_code="UPSTREAM_UNCERTAIN_NETWORK_ERROR",
            ) from exc

        try:
            completion = _ChatCompletionResponse.model_validate(response.json())
            text = completion.choices[0].message.content
        except (IndexError, ValueError, ValidationError) as exc:
            raise InferenceAdapterError(
                "The upstream model returned an invalid Chat Completions response.",
                model_key=model.key,
                reason_code="UPSTREAM_INVALID_RESPONSE",
            ) from exc

        if text is None:
            raise InferenceAdapterError(
                "The upstream model response did not contain text.",
                model_key=model.key,
                reason_code="UPSTREAM_EMPTY_RESPONSE",
            )

        usage = completion.usage
        return InferenceResult(
            text=text,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
            latency_ms=round((perf_counter() - started_at) * 1000),
            provider_request_id=completion.id,
            provider_model=completion.model,
            finish_reason=completion.choices[0].finish_reason,
        )
