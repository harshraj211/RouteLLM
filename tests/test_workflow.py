from routellm.schemas.routing import Message, RouteRequest
from routellm.services.analyzer import RequestAnalyzer
from routellm.services.policy import PolicyEngine
from routellm.services.registry import InMemoryModelRegistry
from routellm.services.scoring import CandidateScorer
from routellm.workflows.routing import RoutingWorkflow


def test_routing_workflow_returns_ranked_candidates() -> None:
    workflow = RoutingWorkflow(
        analyzer=RequestAnalyzer(),
        policy_engine=PolicyEngine(),
        scorer=CandidateScorer(),
    )
    request = RouteRequest(
        tenant_id="demo",
        workflow_id="workflow",
        task_type="qa",
        messages=[Message(role="user", content="Hello from RouteLLM")],
        max_budget_usd=0.01,
        latency_slo_ms=2000,
    )

    state = workflow.run(request, InMemoryModelRegistry.bootstrap_defaults().list_models())

    assert state["analysis"].estimated_input_tokens >= 1
    assert len(state["ranked_candidates"]) >= 1
