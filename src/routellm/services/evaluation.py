from routellm.schemas.evaluation import EvaluationResult
from routellm.schemas.models import ModelDescriptor
from routellm.schemas.routing import RouteRequest


class ResponseEvaluator:
    """Heuristic response evaluator for early-exit decisions."""

    def evaluate(
        self,
        request: RouteRequest,
        model: ModelDescriptor,
        response_text: str,
    ) -> EvaluationResult:
        confidence = 0.55 + (model.quality_tier * 0.1)
        reason_codes = ["BASE_CONFIDENCE_HEURISTIC"]

        if request.response_format == "json":
            confidence -= 0.05
            reason_codes.append("JSON_OUTPUT_MORE_STRICT")

        if len(response_text) >= 32:
            confidence += 0.05
            reason_codes.append("RESPONSE_LENGTH_PLAUSIBLE")

        accepted = confidence >= 0.65
        if accepted:
            reason_codes.append("EARLY_EXIT_ACCEPTED")
        else:
            reason_codes.append("ESCALATION_RECOMMENDED")

        return EvaluationResult(
            accepted=accepted,
            confidence_score=round(min(confidence, 0.99), 2),
            reason_codes=reason_codes,
        )
