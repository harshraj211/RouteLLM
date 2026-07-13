from dataclasses import dataclass

from fastapi import HTTPException

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
        eligible_models = models
        reason_codes: list[str] = [f"SEMANTIC_INTENT_{analysis.semantic_intent.upper()}"]
        if any(self._matches_specialist_preference(model, analysis) for model in models):
            reason_codes.append("SEMANTIC_SPECIALIST_PREFERENCE_AVAILABLE")
        if request.requested_model:
            eligible_models = [
                model for model in models if request.requested_model in {model.key, model.model_id}
            ]
            if not eligible_models:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown model {request.requested_model!r}.",
                )
            reason_codes.append("REQUESTED_MODEL_PINNED")

        filtered = [
            model for model in eligible_models if model.latency.p95_ms <= request.latency_slo_ms
        ]
        reason_codes.append("LATENCY_FILTER_APPLIED")

        if analysis.risk_level == "high":
            filtered = [model for model in filtered if model.quality_tier >= 2]
            reason_codes.append("HIGH_RISK_REQUIRES_STRONGER_MODEL")

        if request.response_format == "json":
            filtered = [model for model in filtered if model.supports_structured_output]
            reason_codes.append("STRUCTURED_OUTPUT_REQUIRED")

        capability_matches = [
            model
            for model in filtered
            if analysis.required_capabilities.issubset(model.capabilities)
        ]
        if capability_matches:
            filtered = capability_matches
            reason_codes.append("SEMANTIC_CAPABILITY_MATCH_APPLIED")

        if not filtered:
            filtered = sorted(eligible_models, key=lambda model: model.quality_tier, reverse=True)
            reason_codes.append("FALLBACK_TO_BEST_AVAILABLE_MODEL")

        return PolicyDecision(candidates=filtered, reason_codes=reason_codes)

    @staticmethod
    def _matches_specialist_preference(
        model: ModelDescriptor,
        analysis: RequestAnalysis,
    ) -> bool:
        provider_family = model.provider_family or model.provider
        return (
            model.key in analysis.preferred_model_keys
            or provider_family in analysis.preferred_provider_families
        )
