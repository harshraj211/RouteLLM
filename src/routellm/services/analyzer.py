from dataclasses import dataclass

from routellm.schemas.routing import RouteRequest


@dataclass(slots=True)
class RequestAnalysis:
    estimated_input_tokens: int
    estimated_output_tokens: int
    risk_level: str
    complexity_score: float


class RequestAnalyzer:
    """Simple heuristic analyzer for the first routing iteration."""

    def analyze(self, request: RouteRequest) -> RequestAnalysis:
        total_chars = sum(len(message.content) for message in request.messages)
        estimated_input_tokens = max(1, total_chars // 4)
        estimated_output_tokens = 256 if request.response_format == "json" else 180

        risk_level = "high" if request.task_type in {"codegen", "sql", "legal"} else "medium"
        complexity_score = min(1.0, estimated_input_tokens / 4000)

        return RequestAnalysis(
            estimated_input_tokens=estimated_input_tokens,
            estimated_output_tokens=estimated_output_tokens,
            risk_level=risk_level,
            complexity_score=complexity_score,
        )
