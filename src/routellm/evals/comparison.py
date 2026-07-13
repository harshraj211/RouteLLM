"""Compare RouteLLM's policy cost with an always-cloud reference model."""

from routellm.evals.replay import ReplayRunner
from routellm.schemas.benchmark import BenchmarkComparisonResponse
from routellm.schemas.models import ModelDescriptor
from routellm.schemas.routing import RouteRequest
from routellm.services.analyzer import RequestAnalyzer


class PolicyBenchmark:
    def __init__(self, runner: ReplayRunner) -> None:
        self.runner = runner
        self.analyzer = RequestAnalyzer()

    async def compare(
        self,
        requests: list[RouteRequest],
        *,
        dataset_name: str,
        reference_cloud_model: ModelDescriptor,
    ) -> BenchmarkComparisonResponse:
        routed = await self.runner.run(requests, dataset_name=dataset_name)
        baseline_cost = sum(
            self._reference_cost(request, reference_cloud_model) for request in requests
        )
        savings = max(0.0, baseline_cost - routed.total_estimated_cost_usd)

        return BenchmarkComparisonResponse(
            dataset_name=dataset_name,
            requests_replayed=routed.requests_replayed,
            route_estimated_cost_usd=routed.total_estimated_cost_usd,
            always_cloud_estimated_cost_usd=round(baseline_cost, 6),
            estimated_savings_usd=round(savings, 6),
            estimated_savings_percent=(
                round((savings / baseline_cost) * 100, 2) if baseline_cost else 0.0
            ),
            reference_cloud_model=reference_cloud_model.key,
            selected_models=routed.selected_models,
        )

    def _reference_cost(self, request: RouteRequest, model: ModelDescriptor) -> float:
        analysis = self.analyzer.analyze(request)
        return (
            analysis.estimated_input_tokens * model.pricing.input_cost_per_1k_tokens / 1000
            + analysis.estimated_output_tokens
            * model.pricing.output_cost_per_1k_tokens
            / 1000
        )
