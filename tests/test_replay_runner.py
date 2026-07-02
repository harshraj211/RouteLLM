import asyncio

from routellm.evals.replay import ReplayRunner
from routellm.schemas.routing import Message, RouteRequest
from routellm.services.registry import InMemoryModelRegistry
from routellm.services.router import RoutingService


def test_replay_runner_summarizes_replayed_requests() -> None:
    service = RoutingService(InMemoryModelRegistry.bootstrap_defaults())
    runner = ReplayRunner(service)
    requests = [
        RouteRequest(
            tenant_id="demo",
            workflow_id="eval",
            task_type="qa",
            messages=[Message(role="user", content="hello there")],
            max_budget_usd=0.01,
            latency_slo_ms=2000,
        ),
        RouteRequest(
            tenant_id="demo",
            workflow_id="eval",
            task_type="classification",
            messages=[Message(role="user", content="classify this")],
            max_budget_usd=0.02,
            latency_slo_ms=2500,
            response_format="json",
        ),
    ]

    summary = asyncio.run(runner.run(requests))

    assert summary.requests_replayed == 2
    assert len(summary.selected_models) == 2
