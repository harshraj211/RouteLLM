from dataclasses import dataclass, field

from routellm.schemas.policies import RoutingPolicy


@dataclass
class InMemoryPolicyStore:
    policies: dict[str, RoutingPolicy] = field(default_factory=dict)

    @classmethod
    def bootstrap_defaults(cls) -> "InMemoryPolicyStore":
        defaults = {
            "default": RoutingPolicy(
                key="default",
                task_types=[],
                max_cost_usd=None,
                max_latency_ms=None,
                require_structured_output=False,
                minimum_quality_tier=1,
                allowed_providers=[],
                escalation_enabled=True,
            ),
            "json-heavy": RoutingPolicy(
                key="json-heavy",
                task_types=["extraction", "classification"],
                max_cost_usd=0.02,
                max_latency_ms=2500,
                require_structured_output=True,
                minimum_quality_tier=2,
                allowed_providers=["vllm", "hosted"],
                escalation_enabled=True,
            ),
        }
        return cls(policies=defaults)

    def list_policies(self) -> list[RoutingPolicy]:
        return list(self.policies.values())

    def upsert_policy(self, policy: RoutingPolicy) -> RoutingPolicy:
        self.policies[policy.key] = policy
        return policy
