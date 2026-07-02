from pydantic import BaseModel


class TenantBudgetSnapshot(BaseModel):
    tenant_id: str
    total_spend_usd: float
    request_count: int
