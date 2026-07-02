from routellm.adapters.base import InferenceAdapter
from routellm.schemas.models import ModelDescriptor
from routellm.schemas.routing import RouteRequest


class VLLMInferenceAdapter(InferenceAdapter):
    async def invoke(self, request: RouteRequest, model: ModelDescriptor) -> str:
        return (
            f"[vllm:{model.key}] handled '{request.task_type}' within budget "
            f"${request.max_budget_usd:.4f}."
        )
