from pathlib import Path
from typing import Literal

import pytest

from routellm.schemas.routing import Message, RouteRequest
from routellm.services.analyzer import RequestAnalyzer
from routellm.services.policy import PolicyEngine
from routellm.services.registry import YamlModelRegistry
from routellm.services.scoring import CandidateScorer
from routellm.workflows.routing import RoutingState, RoutingWorkflow


def _route(
    prompt: str,
    *,
    response_format: Literal["text", "json"] = "text",
    include_disabled: bool = False,
) -> RoutingState:
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
    registry = YamlModelRegistry.from_file(Path("config/models.yaml"))
    return workflow.run(request, registry.list_models(include_disabled=include_disabled))


@pytest.mark.parametrize(
    ("prompt", "expected_intent", "expected_model"),
    [
        ("Hello, how are you?", "general_qa", "local-small"),
        (
                "Write a Python function and unit tests for binary search.",
                "coding",
                "local-coder",
        ),
        (
                "Research and compare sources about transformer efficiency.",
                "research",
                "local-coder",
        ),
        (
                "Draft a moving short story about memory.",
                "creative_writing",
                "local-small",
        ),
        ("Review this contract clause for legal risks.", "legal", "local-coder"),
        ("Solve this calculus derivative equation.", "math", "local-coder"),
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
    assert state["ranked_candidates"][0].key == "local-coder"
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


@pytest.mark.parametrize(
    ("prompt", "expected_model", "expected_provider"),
    [
        (
            "Write a Python API client and unit tests for retry handling.",
            "openai-codex",
            "openai",
        ),
        (
            "Research and compare sources about transformer efficiency.",
            "gemini-3.5-flash",
            "google",
        ),
        (
            "Review this contract clause for legal risk and compliance issues.",
            "claude-sonnet",
            "anthropic",
        ),
        (
            "Draft a moving short story about memory and regret.",
            "claude-sonnet",
            "anthropic",
        ),
        (
            "Solve this probability theorem and show the reasoning.",
            "hosted-premium",
            "openai",
        ),
        (
            "Summarize the latest tech trends and current AI news updates.",
            "grok-4.5",
            "xai",
        ),
    ],
)
def test_specialist_cloud_models_win_when_available(
    prompt: str,
    expected_model: str,
    expected_provider: str,
) -> None:
    state = _route(prompt, include_disabled=True)
    selected = state["ranked_candidates"][0]

    assert selected.key == expected_model
    assert (selected.provider_family or selected.provider) == expected_provider
    assert "SEMANTIC_SPECIALIST_PREFERENCE_AVAILABLE" in state["policy"].reason_codes
