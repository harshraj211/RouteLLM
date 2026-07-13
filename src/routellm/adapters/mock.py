from routellm.adapters.base import InferenceAdapter, InferenceResult
from routellm.schemas.models import ModelDescriptor
from routellm.schemas.routing import RouteRequest


class MockInferenceAdapter(InferenceAdapter):
    """Deterministic adapter used only when RouteLLM runs in explicit mock mode."""

    async def invoke(self, request: RouteRequest, model: ModelDescriptor) -> InferenceResult:
        text = (
            f"[{model.provider}:{model.key}] handled '{request.task_type}' for workflow "
            f"'{request.workflow_id}'."
        )
        input_chars = sum(len(message.content) for message in request.messages)
        return InferenceResult(
            text=text,
            input_tokens=max(1, input_chars // 4),
            output_tokens=max(1, len(text) // 4),
            latency_ms=1,
            provider_request_id=f"mock-{request.request_id}",
            provider_model=model.model_id,
            finish_reason="stop",
        )
