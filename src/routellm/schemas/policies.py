from pydantic import BaseModel, Field


class RoutingPolicy(BaseModel):
    key: str
    task_types: list[str] = Field(default_factory=list)
    max_cost_usd: float | None = None
    max_latency_ms: int | None = None
    require_structured_output: bool = False
    minimum_quality_tier: int = 1
    allowed_providers: list[str] = Field(default_factory=list)
    escalation_enabled: bool = True
