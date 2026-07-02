from pydantic import BaseModel, HttpUrl


class ModelPricing(BaseModel):
    input_cost_per_1k_tokens: float
    output_cost_per_1k_tokens: float
    currency: str = "USD"


class ModelLatencyProfile(BaseModel):
    p50_ms: int
    p95_ms: int


class ModelDescriptor(BaseModel):
    key: str
    provider: str
    display_name: str
    endpoint: HttpUrl | None = None
    quality_tier: int
    supports_structured_output: bool = False
    max_context_tokens: int
    pricing: ModelPricing
    latency: ModelLatencyProfile
    health_score: float = 1.0
