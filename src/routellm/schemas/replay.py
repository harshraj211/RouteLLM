from pydantic import BaseModel


class ReplaySummaryResponse(BaseModel):
    requests_replayed: int
    average_estimated_cost_usd: float
    selected_models: list[str]
