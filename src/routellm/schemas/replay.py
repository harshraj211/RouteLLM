from pydantic import BaseModel


class ReplaySummaryResponse(BaseModel):
    dataset_name: str
    requests_replayed: int
    average_estimated_cost_usd: float
    selected_models: list[str]
