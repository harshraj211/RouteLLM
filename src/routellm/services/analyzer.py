import re
from dataclasses import dataclass

from routellm.schemas.routing import RouteRequest


@dataclass(slots=True)
class RequestAnalysis:
    estimated_input_tokens: int
    estimated_output_tokens: int
    risk_level: str
    complexity_score: float
    semantic_intent: str
    required_capabilities: frozenset[str]
    preferred_model_keys: tuple[str, ...]
    preferred_provider_families: tuple[str, ...]


_INTENT_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "coding",
        (
            r"\b(code|coding|program|function|class|api|debug|bug|refactor)\b",
            r"\b(python|javascript|typescript|java|rust|golang|sql|regex)\b",
            r"\b(stack trace|unit test|pull request)\b",
        ),
    ),
    (
        "math",
        (
            r"\b(calculate|solve|equation|algebra|calculus|probability|theorem)\b",
            r"\b(derivative|integral|matrix|statistics|mathematical)\b",
        ),
    ),
    (
        "research",
        (
            r"\b(research|compare sources|literature review|evidence|citation)\b",
            r"\b(analy[sz]e (?:this )?(?:paper|report|study))\b",
        ),
    ),
    (
        "current_events",
        (
            (
                r"\b(current|latest|recent|today|this week|breaking)\b"
                r".{0,40}\b(news|events?|trends?|updates?)\b"
            ),
            (
                r"\b(news|events?|trends?|updates?)\b"
                r".{0,40}\b(current|latest|recent|today|this week|breaking)\b"
            ),
        ),
    ),
    (
        "legal",
        (r"\b(legal|law|contract|clause|compliance|regulation|lawsuit|liability)\b",),
    ),
    (
        "extraction",
        (
            r"\b(extract|parse|fields?|entities|schema|structured data)\b",
            r"\b(return|respond|output) (?:it )?(?:as|in) json\b",
        ),
    ),
    (
        "creative_writing",
        (r"\b(write|draft|compose)\b.{0,40}\b(story|poem|script|song|novel)\b",),
    ),
    (
        "summarization",
        (r"\b(summarize|summarise|summary|condense|key takeaways)\b",),
    ),
    (
        "classification",
        (r"\b(classify|categorize|categorise|label|sentiment)\b",),
    ),
)

_TASK_TYPE_ALIASES = {
    "codegen": "coding",
    "code": "coding",
    "sql": "coding",
    "creative": "creative_writing",
    "summary": "summarization",
    "extract": "extraction",
}

_INTENT_CAPABILITIES = {
    "coding": frozenset({"code_generation", "reasoning"}),
    "math": frozenset({"reasoning"}),
    "research": frozenset({"research", "long_context"}),
    "current_events": frozenset({"research", "long_context"}),
    "legal": frozenset({"reasoning"}),
    "extraction": frozenset({"structured_output"}),
    "creative_writing": frozenset({"creative_writing"}),
    "summarization": frozenset({"summarization"}),
    "classification": frozenset({"classification"}),
    "general_qa": frozenset({"general_qa"}),
}

_INTENT_SPECIALISTS = {
    "coding": (("openai-codex", "claude-sonnet", "grok-4.5"), ("openai", "anthropic", "xai")),
    "math": (("hosted-premium", "grok-4.5", "gemini-3.5-flash"), ("openai", "xai", "google")),
    "research": (("gemini-3.5-flash", "claude-sonnet"), ("google", "anthropic")),
    "current_events": (("grok-4.5", "gemini-3.5-flash"), ("xai", "google")),
    "legal": (("claude-sonnet",), ("anthropic",)),
    "creative_writing": (("claude-sonnet", "grok-4.5"), ("anthropic", "xai")),
    "summarization": (("gemini-3.5-flash", "claude-sonnet"), ("google", "anthropic")),
    "extraction": (("local-coder", "gemini-3.5-flash"), ("google",)),
    "classification": (("local-small", "gemini-3.5-flash"), ("google",)),
    "general_qa": (("local-small", "grok-4.5"), ("xai",)),
}


class RequestAnalyzer:
    """Infers request size, risk, intent, and required model capabilities."""

    def analyze(self, request: RouteRequest) -> RequestAnalysis:
        total_chars = sum(len(message.content) for message in request.messages)
        estimated_input_tokens = max(1, total_chars // 4)
        estimated_output_tokens = request.max_output_tokens or (
            256 if request.response_format == "json" else 180
        )

        semantic_intent = self._detect_intent(request)
        risk_level = (
            "high"
            if request.task_type in {"codegen", "sql", "legal"}
            or semantic_intent in {"coding", "legal"}
            else "medium"
        )
        complexity_score = min(1.0, estimated_input_tokens / 4000)

        preferred_model_keys, preferred_provider_families = _INTENT_SPECIALISTS[semantic_intent]

        return RequestAnalysis(
            estimated_input_tokens=estimated_input_tokens,
            estimated_output_tokens=estimated_output_tokens,
            risk_level=risk_level,
            complexity_score=complexity_score,
            semantic_intent=semantic_intent,
            required_capabilities=_INTENT_CAPABILITIES[semantic_intent],
            preferred_model_keys=preferred_model_keys,
            preferred_provider_families=preferred_provider_families,
        )

    @staticmethod
    def _detect_intent(request: RouteRequest) -> str:
        declared_task = _TASK_TYPE_ALIASES.get(request.task_type, request.task_type)
        if declared_task not in {"qa", "chat", "general", "auto"}:
            if declared_task in _INTENT_CAPABILITIES:
                return declared_task

        prompt = "\n".join(
            message.content for message in request.messages if message.role in {"user", "system"}
        ).lower()
        matches = (
            (intent, sum(bool(re.search(pattern, prompt)) for pattern in patterns))
            for intent, patterns in _INTENT_PATTERNS
        )
        best_intent, best_score = max(matches, key=lambda match: match[1])
        return best_intent if best_score else "general_qa"
