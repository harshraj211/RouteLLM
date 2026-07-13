from dataclasses import dataclass, field

from routellm.schemas.budget import TenantBudgetSnapshot


@dataclass
class InMemoryTenantBudgetLedger:
    spend_by_tenant: dict[str, float] = field(default_factory=dict)
    request_count_by_tenant: dict[str, int] = field(default_factory=dict)

    def record_spend(self, tenant_id: str, amount_usd: float) -> TenantBudgetSnapshot:
        self.spend_by_tenant[tenant_id] = round(
            self.spend_by_tenant.get(tenant_id, 0.0) + amount_usd, 6
        )
        self.request_count_by_tenant[tenant_id] = self.request_count_by_tenant.get(tenant_id, 0) + 1
        return self.get_snapshot(tenant_id)

    def get_snapshot(self, tenant_id: str) -> TenantBudgetSnapshot:
        return TenantBudgetSnapshot(
            tenant_id=tenant_id,
            total_spend_usd=self.spend_by_tenant.get(tenant_id, 0.0),
            request_count=self.request_count_by_tenant.get(tenant_id, 0),
        )
