from routellm.evals.dataset_loader import load_requests_from_json
from routellm.evals.paths import DEFAULT_BENCHMARK_DATASET
from routellm.evals.replay import ReplayRunner, ReplaySummary
from routellm.services.router import RoutingService


class ReplayService:
    def __init__(self, routing_service: RoutingService) -> None:
        self.runner = ReplayRunner(routing_service)

    async def run_default_benchmark(self) -> ReplaySummary:
        requests = load_requests_from_json(DEFAULT_BENCHMARK_DATASET)
        return await self.runner.run(requests, dataset_name=DEFAULT_BENCHMARK_DATASET.stem)
