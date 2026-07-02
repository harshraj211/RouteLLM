from routellm.adapters.base import InferenceAdapter
from routellm.schemas.models import ModelDescriptor
from routellm.schemas.routing import RouteRequest


class HostedInferenceAdapter(InferenceAdapter):
    async def invoke(self, request: RouteRequest, model: ModelDescriptor) -> str:
        return (
            f"[hosted:{model.key}] handled '{request.task_type}' for workflow "
            f"'{request.workflow_id}' with premium routing."
        )
