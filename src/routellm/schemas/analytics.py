from datetime import datetime

from pydantic import BaseModel, Field


class ModelUsageAnalytics(BaseModel):
    model_key: str
    request_count: int
    actual_spend_usd: float


class AnalyticsSummary(BaseModel):
    request_count: int
    local_request_count: int
    cloud_request_count: int
    escalation_count: int
    average_estimated_latency_ms: float
    actual_spend_usd: float
    reference_baseline_model: str
    reference_baseline_spend_usd: float
    estimated_savings_usd: float
    estimated_savings_percent: float
    model_usage: list[ModelUsageAnalytics]


class AnalyticsDecision(BaseModel):
    id: int
    created_at: datetime | None = None
    request_id: str
    task_type: str
    selected_model: str
    is_local: bool
    reason_codes: list[str]
    actual_cost_usd: float
    reference_baseline_cost_usd: float
    estimated_savings_usd: float = Field(ge=0)
