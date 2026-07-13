from pydantic import BaseModel, Field


class BenchmarkComparisonResponse(BaseModel):
    dataset_name: str
    requests_replayed: int
    route_estimated_cost_usd: float
    always_cloud_estimated_cost_usd: float
    estimated_savings_usd: float
    estimated_savings_percent: float = Field(ge=0, le=100)
    reference_cloud_model: str
    selected_models: list[str]
