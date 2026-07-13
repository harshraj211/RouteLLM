from dataclasses import dataclass

from routellm.schemas.routing import RouteRequest, RouteResponse
from routellm.services.router import RoutingService


@dataclass
class ReplaySummary:
    dataset_name: str
    requests_replayed: int
    average_estimated_cost_usd: float
    selected_models: list[str]


class ReplayRunner:
    def __init__(self, routing_service: RoutingService) -> None:
        self.routing_service = routing_service

    async def run(
        self, requests: list[RouteRequest], dataset_name: str = "ad-hoc"
    ) -> ReplaySummary:
        responses: list[RouteResponse] = []
        for request in requests:
            responses.append(await self.routing_service.route(request))

        total_cost = sum(response.decision.estimated_cost_usd for response in responses)
        average_cost = total_cost / len(responses) if responses else 0.0

        return ReplaySummary(
            dataset_name=dataset_name,
            requests_replayed=len(responses),
            average_estimated_cost_usd=round(average_cost, 6),
            selected_models=[response.decision.selected_model for response in responses],
        )
