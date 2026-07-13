import pytest

from routellm.schemas.routing import Message, RouteRequest
from routellm.services.analyzer import RequestAnalyzer
from routellm.services.policy import PolicyEngine
from routellm.services.registry import InMemoryModelRegistry
from routellm.services.scoring import CandidateScorer
from routellm.workflows.routing import RoutingWorkflow


def _route(prompt: str, *, response_format: str = "text"):
    request = RouteRequest(
        tenant_id="semantic-test",
        workflow_id="auto-router",
        task_type="qa",
        messages=[Message(role="user", content=prompt)],
        max_budget_usd=1.0,
        latency_slo_ms=10_000,
        response_format=response_format,
    )
    workflow = RoutingWorkflow(RequestAnalyzer(), PolicyEngine(), CandidateScorer())
    return workflow.run(request, InMemoryModelRegistry.bootstrap_defaults().list_models())


@pytest.mark.parametrize(
    ("prompt", "expected_intent", "expected_model"),
    [
        ("Hello, how are you?", "general_qa", "local-small"),
        (
            "Write a Python function and unit tests for binary search.",
            "coding",
            "hosted-premium",
        ),
        (
            "Research and compare sources about transformer efficiency.",
            "research",
            "hosted-premium",
        ),
        ("Solve this calculus derivative equation.", "math", "local-medium-json"),
    ],
)
def test_prompt_semantics_change_selected_model(
    prompt: str,
    expected_intent: str,
    expected_model: str,
) -> None:
    state = _route(prompt)

    assert state["analysis"].semantic_intent == expected_intent
    assert state["ranked_candidates"][0].key == expected_model
    assert f"SEMANTIC_INTENT_{expected_intent.upper()}" in state["policy"].reason_codes
    assert "SEMANTIC_CAPABILITY_MATCH_APPLIED" in state["policy"].reason_codes


def test_json_extraction_prefers_structured_extraction_model() -> None:
    state = _route(
        "Extract the customer names and dates and return them as JSON.",
        response_format="json",
    )

    assert state["analysis"].semantic_intent == "extraction"
    assert state["ranked_candidates"][0].key == "local-medium-json"
    assert all(model.supports_structured_output for model in state["ranked_candidates"])


def test_explicit_task_type_overrides_generic_prompt() -> None:
    request = RouteRequest(
        tenant_id="semantic-test",
        workflow_id="auto-router",
        task_type="classification",
        messages=[Message(role="user", content="Process this input.")],
        max_budget_usd=1.0,
        latency_slo_ms=10_000,
    )

    analysis = RequestAnalyzer().analyze(request)

    assert analysis.semantic_intent == "classification"
    assert analysis.required_capabilities == frozenset({"classification"})
