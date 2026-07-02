from dataclasses import dataclass

from routellm.schemas.models import ModelDescriptor
from routellm.schemas.routing import RouteRequest
from routellm.services.analyzer import RequestAnalysis


@dataclass(slots=True)
class PolicyDecision:
    candidates: list[ModelDescriptor]
    reason_codes: list[str]


class PolicyEngine:
    """Applies first-pass routing policy rules."""

    def select_candidates(
        self,
        request: RouteRequest,
        analysis: RequestAnalysis,
        models: list[ModelDescriptor],
    ) -> PolicyDecision:
        filtered = [model for model in models if model.latency.p95_ms <= request.latency_slo_ms]
        reason_codes = ["LATENCY_FILTER_APPLIED"]

        if analysis.risk_level == "high":
            filtered = [model for model in filtered if model.quality_tier >= 2]
            reason_codes.append("HIGH_RISK_REQUIRES_STRONGER_MODEL")

        if request.response_format == "json":
            filtered = [model for model in filtered if model.supports_structured_output]
            reason_codes.append("STRUCTURED_OUTPUT_REQUIRED")

        if not filtered:
            filtered = sorted(models, key=lambda model: model.quality_tier, reverse=True)
            reason_codes.append("FALLBACK_TO_BEST_AVAILABLE_MODEL")

        return PolicyDecision(candidates=filtered, reason_codes=reason_codes)
