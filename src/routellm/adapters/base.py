from abc import ABC, abstractmethod
from dataclasses import dataclass

from routellm.schemas.models import ModelDescriptor
from routellm.schemas.routing import RouteRequest


@dataclass(slots=True, frozen=True)
class InferenceResult:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None
    provider_request_id: str | None = None
    provider_model: str | None = None
    finish_reason: str | None = None


class InferenceAdapterError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        model_key: str,
        status_code: int | None = None,
        retryable: bool = False,
        reason_code: str = "UPSTREAM_ERROR",
    ) -> None:
        super().__init__(message)
        self.model_key = model_key
        self.status_code = status_code
        self.retryable = retryable
        self.reason_code = reason_code


class InferenceAdapter(ABC):
    @abstractmethod
    async def invoke(self, request: RouteRequest, model: ModelDescriptor) -> InferenceResult:
        """Invoke a model and return normalized text, usage, and provider metadata."""
