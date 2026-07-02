from routellm.schemas.models import ModelDescriptor


class BudgetExceededError(Exception):
    """Raised when no candidate fits within the request budget."""


class BudgetService:
    def estimate_cost(
        self,
        model: ModelDescriptor,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
    ) -> float:
        return round(
            (estimated_input_tokens * model.pricing.input_cost_per_1k_tokens / 1000)
            + (estimated_output_tokens * model.pricing.output_cost_per_1k_tokens / 1000),
            6,
        )

    def ensure_within_budget(
        self,
        model: ModelDescriptor,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
        max_budget_usd: float,
    ) -> float:
        estimated_cost = self.estimate_cost(
            model,
            estimated_input_tokens=estimated_input_tokens,
            estimated_output_tokens=estimated_output_tokens,
        )
        if estimated_cost > max_budget_usd:
            raise BudgetExceededError(
                f"Estimated cost {estimated_cost:.6f} exceeds budget {max_budget_usd:.6f}."
            )
        return estimated_cost
