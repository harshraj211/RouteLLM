from routellm.agent_native.policy import AgentNativeRouter


def test_coding_work_uses_current_agent_without_api_key() -> None:
    recommendation = AgentNativeRouter().recommend(
        "Fix the failing Python test and add coverage for the regression.",
        host="codex",
    )

    assert recommendation.intent == "coding"
    assert recommendation.task_mode == "standard"
    assert recommendation.execution_target == "current_agent"
    assert recommendation.model_control == "host_managed"
    assert "NO_PROVIDER_API_KEY_REQUIRED" in recommendation.reason_codes
    assert recommendation.suggested_tools == ("repository_search", "test_runner")


def test_research_and_high_risk_work_require_deep_verification() -> None:
    recommendation = AgentNativeRouter().recommend(
        "Research sources for a security threat model.",
        host="claude_cowork",
        requires_external_research=True,
        high_risk=True,
    )

    assert recommendation.intent == "research"
    assert recommendation.task_mode == "deep"
    assert recommendation.verification_level == "strict"
    assert recommendation.suggested_tools == ("web_research",)
    assert "EXTERNAL_RESEARCH_REQUESTED" in recommendation.reason_codes
    assert "HIGH_RISK_VERIFICATION_REQUIRED" in recommendation.reason_codes


def test_recommendation_is_json_serializable() -> None:
    payload = AgentNativeRouter().recommend("Summarize this document.").to_dict()

    assert payload["intent"] == "summarization"
    assert payload["execution_target"] == "current_agent"
    assert payload["host"] == "codex"
