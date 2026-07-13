from routellm.adapters.anthropic import AnthropicInferenceAdapter
from routellm.adapters.base import InferenceAdapter, InferenceAdapterError, InferenceResult
from routellm.adapters.gemini import GeminiInferenceAdapter
from routellm.adapters.hosted import HostedInferenceAdapter
from routellm.adapters.mock import MockInferenceAdapter
from routellm.adapters.ollama import OllamaInferenceAdapter
from routellm.adapters.vllm import VLLMInferenceAdapter
from routellm.config import Settings, get_settings
from routellm.schemas.models import ModelDescriptor
from routellm.schemas.routing import RouteRequest


class ExecutionService:
    def __init__(
        self,
        settings: Settings | None = None,
        adapters: dict[str, InferenceAdapter] | None = None,
    ) -> None:
        settings = settings or get_settings()
        if adapters is not None:
            self._adapters = adapters
        elif settings.inference_mode == "mock":
            mock_adapter = MockInferenceAdapter()
            self._adapters = {
                "vllm": mock_adapter,
                "hosted": mock_adapter,
                "anthropic": mock_adapter,
                "gemini": mock_adapter,
                "ollama": mock_adapter,
            }
        else:
            self._adapters = {
                "vllm": VLLMInferenceAdapter(
                    timeout_seconds=settings.inference_timeout_seconds,
                ),
                "hosted": HostedInferenceAdapter(
                    timeout_seconds=settings.inference_timeout_seconds,
                ),
                "anthropic": AnthropicInferenceAdapter(
                    timeout_seconds=settings.inference_timeout_seconds,
                ),
                "gemini": GeminiInferenceAdapter(
                    timeout_seconds=settings.inference_timeout_seconds,
                ),
                "ollama": OllamaInferenceAdapter(
                    timeout_seconds=settings.ollama_inference_timeout_seconds,
                ),
            }

    async def invoke(self, request: RouteRequest, model: ModelDescriptor) -> InferenceResult:
        adapter = self._adapters.get(model.provider)
        if adapter is None:
            raise InferenceAdapterError(
                f"No inference adapter is registered for provider {model.provider!r}.",
                model_key=model.key,
                reason_code="UPSTREAM_PROVIDER_UNSUPPORTED",
            )
        return await adapter.invoke(request, model)
