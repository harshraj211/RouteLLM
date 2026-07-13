import json

from routellm.schemas.evaluation import EvaluationResult
from routellm.schemas.models import ModelDescriptor
from routellm.schemas.routing import RouteRequest


class ResponseEvaluator:
    """Deterministic quality gate used before accepting a low-cost model response."""

    def evaluate(
        self,
        request: RouteRequest,
        model: ModelDescriptor,
        response_text: str,
    ) -> EvaluationResult:
        confidence = 0.55 + (model.quality_tier * 0.1)
        reason_codes = ["BASE_CONFIDENCE_HEURISTIC"]

        if request.response_format == "json":
            try:
                json.loads(response_text)
                reason_codes.append("JSON_OUTPUT_VALID")
            except json.JSONDecodeError:
                confidence -= 0.5
                reason_codes.append("JSON_OUTPUT_INVALID")

        if len(response_text.strip()) >= 32:
            confidence += 0.05
            reason_codes.append("RESPONSE_LENGTH_PLAUSIBLE")
        else:
            confidence -= 0.25
            reason_codes.append("RESPONSE_TOO_SHORT")

        normalized_response = response_text.lower()
        if any(
            phrase in normalized_response
            for phrase in ("i cannot", "i can't", "unable to", "cannot help with")
        ):
            confidence -= 0.5
            reason_codes.append("MODEL_DECLINED_TASK")

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
