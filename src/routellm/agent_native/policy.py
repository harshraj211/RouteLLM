"""Local, explainable routing policy for MCP-connected coding agents."""

from dataclasses import asdict, dataclass
from typing import Literal

AgentHost = Literal["codex", "claude_cowork", "antigravity", "generic_mcp"]
TaskMode = Literal["quick", "standard", "deep"]


@dataclass(frozen=True, slots=True)
class AgentRecommendation:
    """A host-safe recommendation that never requires a provider API key."""

    host: AgentHost
    intent: str
    task_mode: TaskMode
    execution_target: str
    model_control: str
    verification_level: str
    suggested_tools: tuple[str, ...]
    reason_codes: tuple[str, ...]
    host_boundary: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class AgentNativeRouter:
    """Selects an execution policy without calling, or naming, a paid provider API."""

    def recommend(
        self,
        prompt: str,
        *,
        host: AgentHost = "codex",
        requires_external_research: bool = False,
        high_risk: bool = False,
    ) -> AgentRecommendation:
        intent = self._detect_intent(prompt)
        task_mode = self._select_task_mode(
            prompt,
            intent=intent,
            requires_external_research=requires_external_research,
            high_risk=high_risk,
        )
        verification_level = "strict" if high_risk or intent in {"coding", "security"} else "normal"
        suggested_tools = self._suggest_tools(intent, requires_external_research)

        reason_codes = [
            "LOCAL_DETERMINISTIC_CLASSIFICATION",
            f"INTENT_{intent.upper()}",
            f"MODE_{task_mode.upper()}",
            "NO_PROVIDER_API_KEY_REQUIRED",
            "HOST_MODEL_CONTROLLED",
        ]
        if requires_external_research:
            reason_codes.append("EXTERNAL_RESEARCH_REQUESTED")
        if high_risk:
            reason_codes.append("HIGH_RISK_VERIFICATION_REQUIRED")

        return AgentRecommendation(
            host=host,
            intent=intent,
            task_mode=task_mode,
            execution_target="current_agent",
            model_control="host_managed",
            verification_level=verification_level,
            suggested_tools=suggested_tools,
            reason_codes=tuple(reason_codes),
            host_boundary=(
                "RouteLLM supplies a local execution policy. The host application owns its "
                "model choice and may not support runtime model switching through MCP."
            ),
        )

    @staticmethod
    def _detect_intent(prompt: str) -> str:
        text = prompt.lower()
        if any(word in text for word in ("code", "bug", "test", "refactor", "repository")):
            return "coding"
        if any(word in text for word in ("research", "citation", "paper", "sources")):
            return "research"
        if any(word in text for word in ("security", "vulnerability", "threat model")):
            return "security"
        if any(word in text for word in ("summarize", "summary", "condense")):
            return "summarization"
        if any(word in text for word in ("extract", "json", "parse")):
            return "extraction"
        return "general"

    @staticmethod
    def _select_task_mode(
        prompt: str,
        *,
        intent: str,
        requires_external_research: bool,
        high_risk: bool,
    ) -> TaskMode:
        if high_risk or requires_external_research or intent in {"security", "research"}:
            return "deep"
        if intent == "coding" or len(prompt) > 600:
            return "standard"
        return "quick"

    @staticmethod
    def _suggest_tools(intent: str, requires_external_research: bool) -> tuple[str, ...]:
        tools: list[str] = []
        if intent == "coding":
            tools.extend(("repository_search", "test_runner"))
        elif intent == "security":
            tools.extend(("repository_search", "test_runner", "dependency_inspector"))
        elif intent == "extraction":
            tools.append("structured_output_validator")
        if requires_external_research or intent == "research":
            tools.append("web_research")
        return tuple(tools)
