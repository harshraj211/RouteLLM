from routellm.schemas.health import ModelHealthSnapshot
from routellm.schemas.models import ModelDescriptor


class ModelHealthService:
    def summarize(self, models: list[ModelDescriptor]) -> list[ModelHealthSnapshot]:
        return [
            ModelHealthSnapshot(
                model_key=model.key,
                provider=model.provider,
                health_score=model.health_score,
                p50_latency_ms=model.latency.p50_ms,
                p95_latency_ms=model.latency.p95_ms,
            )
            for model in models
        ]
