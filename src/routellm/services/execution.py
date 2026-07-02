from routellm.adapters.base import InferenceAdapter
from routellm.adapters.hosted import HostedInferenceAdapter
from routellm.adapters.vllm import VLLMInferenceAdapter
from routellm.schemas.models import ModelDescriptor
from routellm.schemas.routing import RouteRequest


class ExecutionService:
    def __init__(self) -> None:
        self._adapters: dict[str, InferenceAdapter] = {
            "vllm": VLLMInferenceAdapter(),
            "hosted": HostedInferenceAdapter(),
        }

    async def invoke(self, request: RouteRequest, model: ModelDescriptor) -> str:
        adapter = self._adapters[model.provider]
        return await adapter.invoke(request, model)
