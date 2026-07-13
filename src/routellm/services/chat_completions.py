import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from time import time

from routellm.config import Settings
from routellm.schemas.chat_completions import (
    ChatCompletionAssistantMessage,
    ChatCompletionChoice,
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkDelta,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionUsage,
)
from routellm.schemas.routing import Message, RouteRequest, RouteResponse
from routellm.services.router import RoutingService


@dataclass(slots=True, frozen=True)
class ChatRoutingControls:
    tenant_id: str
    workflow_id: str
    task_type: str
    max_budget_usd: float
    latency_slo_ms: int
    request_id: str | None = None


class UnsupportedChatCompletionRequest(ValueError):
    def __init__(self, message: str, *, param: str, code: str = "unsupported_parameter") -> None:
        super().__init__(message)
        self.param = param
        self.code = code


class ChatCompletionsService:
    def __init__(self, router: RoutingService, settings: Settings) -> None:
        self.router = router
        self.settings = settings

    async def complete(
        self,
        payload: ChatCompletionRequest,
        controls: ChatRoutingControls,
    ) -> RouteResponse:
        route_request = self._to_route_request(payload, controls)
        return await self.router.route(route_request)

    def _to_route_request(
        self,
        payload: ChatCompletionRequest,
        controls: ChatRoutingControls,
    ) -> RouteRequest:
        self._validate_supported_features(payload)
        response_format = (
            "json"
            if payload.response_format and payload.response_format.type == "json_object"
            else "text"
        )
        requested_model = None if payload.model in {"auto", "routellm-auto"} else payload.model
        request_data: dict[str, object] = {
            "tenant_id": controls.tenant_id,
            "workflow_id": controls.workflow_id,
            "task_type": controls.task_type,
            "requested_model": requested_model,
            "messages": [
                Message(role=message.role, content=message.content) for message in payload.messages
            ],
            "max_budget_usd": controls.max_budget_usd,
            "latency_slo_ms": controls.latency_slo_ms,
            "response_format": response_format,
            "max_output_tokens": payload.max_completion_tokens or payload.max_tokens,
            "temperature": payload.temperature,
            "top_p": payload.top_p,
            "stop": payload.stop,
            "presence_penalty": payload.presence_penalty,
            "frequency_penalty": payload.frequency_penalty,
            "seed": payload.seed,
        }
        if controls.request_id:
            request_data["request_id"] = controls.request_id
        return RouteRequest.model_validate(request_data)

    @staticmethod
    def _validate_supported_features(payload: ChatCompletionRequest) -> None:
        if payload.model_extra:
            parameter = sorted(payload.model_extra)[0]
            raise UnsupportedChatCompletionRequest(
                f"Parameter {parameter!r} is not supported by RouteLLM yet.",
                param=parameter,
            )
        if payload.n != 1:
            raise UnsupportedChatCompletionRequest(
                "RouteLLM currently supports only n=1.",
                param="n",
            )
        if payload.max_tokens is not None and payload.max_completion_tokens is not None:
            raise UnsupportedChatCompletionRequest(
                "Use either max_tokens or max_completion_tokens, not both.",
                param="max_tokens",
                code="invalid_parameter",
            )
        if payload.tools or payload.functions:
            raise UnsupportedChatCompletionRequest(
                "Tool and function calling are not supported by this endpoint yet.",
                param="tools" if payload.tools else "functions",
            )
        if (
            payload.tool_choice is not None
            and payload.tool_choice != "none"
            or payload.function_call is not None
            and payload.function_call != "none"
        ):
            raise UnsupportedChatCompletionRequest(
                "Tool and function calling are not supported by this endpoint yet.",
                param="tool_choice" if payload.tool_choice is not None else "function_call",
            )
        if payload.logprobs or payload.top_logprobs is not None:
            raise UnsupportedChatCompletionRequest(
                "Log probabilities are not supported by this endpoint yet.",
                param="logprobs",
            )
        for message in payload.messages:
            if message.role == "tool" or message.tool_calls or message.tool_call_id:
                raise UnsupportedChatCompletionRequest(
                    "Tool messages are not supported by this endpoint yet.",
                    param="messages",
                )
        if payload.response_format and payload.response_format.type == "json_schema":
            raise UnsupportedChatCompletionRequest(
                "json_schema response formatting is not supported yet; use json_object.",
                param="response_format",
            )

    @staticmethod
    def to_response(route_response: RouteResponse) -> ChatCompletionResponse:
        usage = ChatCompletionsService._usage(route_response)
        return ChatCompletionResponse(
            id=f"chatcmpl-{route_response.request_id}",
            created=int(time()),
            model=route_response.usage.provider_model or route_response.decision.selected_model,
            choices=[
                ChatCompletionChoice(
                    message=ChatCompletionAssistantMessage(content=route_response.output.text),
                    finish_reason=(
                        "length" if route_response.output.finish_reason == "length" else "stop"
                    ),
                )
            ],
            usage=usage,
        )

    @staticmethod
    async def stream_response(
        response: ChatCompletionResponse,
        *,
        include_usage: bool,
    ) -> AsyncIterator[str]:
        chunks = [
            ChatCompletionChunk(
                id=response.id,
                created=response.created,
                model=response.model,
                choices=[
                    ChatCompletionChunkChoice(
                        delta=ChatCompletionChunkDelta(role="assistant"),
                    )
                ],
            ),
            ChatCompletionChunk(
                id=response.id,
                created=response.created,
                model=response.model,
                choices=[
                    ChatCompletionChunkChoice(
                        delta=ChatCompletionChunkDelta(content=response.choices[0].message.content),
                    )
                ],
            ),
            ChatCompletionChunk(
                id=response.id,
                created=response.created,
                model=response.model,
                choices=[
                    ChatCompletionChunkChoice(
                        delta=ChatCompletionChunkDelta(),
                        finish_reason=response.choices[0].finish_reason,
                    )
                ],
            ),
        ]
        if include_usage:
            chunks.append(
                ChatCompletionChunk(
                    id=response.id,
                    created=response.created,
                    model=response.model,
                    choices=[],
                    usage=response.usage,
                )
            )

        for chunk in chunks:
            payload = chunk.model_dump(exclude_none=True)
            yield f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"
        yield "data: [DONE]\n\n"

    @staticmethod
    def _usage(route_response: RouteResponse) -> ChatCompletionUsage:
        prompt_tokens = route_response.usage.input_tokens
        completion_tokens = route_response.usage.output_tokens
        return ChatCompletionUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
