from routellm.evals.comparison import PolicyBenchmark
from routellm.evals.dataset_loader import load_requests_from_json
from routellm.evals.paths import DEFAULT_BENCHMARK_DATASET
from routellm.evals.replay import ReplayRunner, ReplaySummary
from routellm.schemas.benchmark import BenchmarkComparisonResponse
from routellm.services.router import RoutingService


class ReplayService:
    def __init__(self, routing_service: RoutingService) -> None:
        self.runner = ReplayRunner(routing_service)
        self.benchmark = PolicyBenchmark(self.runner)
        self.model_registry = routing_service.model_registry

    async def run_default_benchmark(self) -> ReplaySummary:
        requests = load_requests_from_json(DEFAULT_BENCHMARK_DATASET)
        return await self.runner.run(requests, dataset_name=DEFAULT_BENCHMARK_DATASET.stem)

    async def compare_default_benchmark(
        self,
        *,
        reference_cloud_model_key: str,
    ) -> BenchmarkComparisonResponse:
        reference_cloud_model = self.model_registry.get_model(reference_cloud_model_key)
        if reference_cloud_model is None:
            raise ValueError(
                f"Reference cloud model {reference_cloud_model_key!r} is not configured."
            )
        requests = load_requests_from_json(DEFAULT_BENCHMARK_DATASET)
        return await self.benchmark.compare(
            requests,
            dataset_name=DEFAULT_BENCHMARK_DATASET.stem,
            reference_cloud_model=reference_cloud_model,
        )
