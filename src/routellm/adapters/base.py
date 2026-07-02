from abc import ABC, abstractmethod

from routellm.schemas.models import ModelDescriptor
from routellm.schemas.routing import RouteRequest


class InferenceAdapter(ABC):
    @abstractmethod
    async def invoke(self, request: RouteRequest, model: ModelDescriptor) -> str:
        """Invoke a model and return response text."""
