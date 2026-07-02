from dataclasses import dataclass

from routellm.schemas.models import ModelDescriptor, ModelLatencyProfile, ModelPricing


@dataclass(slots=True)
class InMemoryModelRegistry:
    models: list[ModelDescriptor]

    @classmethod
    def bootstrap_defaults(cls) -> "InMemoryModelRegistry":
        return cls(
            models=[
                ModelDescriptor(
                    key="local-small",
                    provider="vllm",
                    display_name="Local Small",
                    endpoint="http://localhost:8001/v1",
                    quality_tier=1,
                    supports_structured_output=False,
                    max_context_tokens=8192,
                    pricing=ModelPricing(
                        input_cost_per_1k_tokens=0.0003,
                        output_cost_per_1k_tokens=0.0005,
                    ),
                    latency=ModelLatencyProfile(p50_ms=350, p95_ms=900),
                ),
                ModelDescriptor(
                    key="local-medium-json",
                    provider="vllm",
                    display_name="Local Medium JSON",
                    endpoint="http://localhost:8002/v1",
                    quality_tier=2,
                    supports_structured_output=True,
                    max_context_tokens=16384,
                    pricing=ModelPricing(
                        input_cost_per_1k_tokens=0.0008,
                        output_cost_per_1k_tokens=0.0011,
                    ),
                    latency=ModelLatencyProfile(p50_ms=700, p95_ms=1800),
                ),
                ModelDescriptor(
                    key="hosted-premium",
                    provider="hosted",
                    display_name="Hosted Premium",
                    endpoint="https://api.example.com/v1",
                    quality_tier=3,
                    supports_structured_output=True,
                    max_context_tokens=128000,
                    pricing=ModelPricing(
                        input_cost_per_1k_tokens=0.01,
                        output_cost_per_1k_tokens=0.03,
                    ),
                    latency=ModelLatencyProfile(p50_ms=1200, p95_ms=2500),
                ),
            ]
        )

    def list_models(self) -> list[ModelDescriptor]:
        return list(self.models)
