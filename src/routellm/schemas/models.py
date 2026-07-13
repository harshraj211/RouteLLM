from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator


class ModelPricing(BaseModel):
    input_cost_per_1k_tokens: float = Field(ge=0)
    output_cost_per_1k_tokens: float = Field(ge=0)
    currency: str = "USD"


class ModelLatencyProfile(BaseModel):
    p50_ms: int = Field(ge=0)
    p95_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_percentiles(self) -> "ModelLatencyProfile":
        if self.p95_ms < self.p50_ms:
            raise ValueError("p95_ms must be greater than or equal to p50_ms.")
        return self


class ModelDescriptor(BaseModel):
    key: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    enabled: bool = True
    provider: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    display_name: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    endpoint: HttpUrl | None = None
    api_key_env: str | None = None
    requires_api_key: bool = False
    max_output_tokens_param: Literal["max_tokens", "max_completion_tokens"] = "max_tokens"
    quality_tier: int = Field(ge=1, le=5)
    supports_structured_output: bool = False
    max_context_tokens: int = Field(gt=0)
    pricing: ModelPricing
    latency: ModelLatencyProfile
    health_score: float = Field(default=1.0, ge=0.0, le=1.0)
