from routellm.schemas.models import ModelDescriptor
from routellm.services.analyzer import RequestAnalysis


class CandidateScorer:
    """Scores candidates with explainable weighted heuristics."""

    def score(
        self,
        model: ModelDescriptor,
        analysis: RequestAnalysis,
    ) -> float:
        estimated_cost = (
            analysis.estimated_input_tokens * model.pricing.input_cost_per_1k_tokens / 1000
            + analysis.estimated_output_tokens * model.pricing.output_cost_per_1k_tokens / 1000
        )
        quality_bonus = model.quality_tier * 0.8
        availability_bonus = model.health_score * 0.4
        latency_penalty = model.latency.p95_ms / 1000
        complexity_bonus = analysis.complexity_score * model.quality_tier

        return quality_bonus + availability_bonus + complexity_bonus - latency_penalty - (
            estimated_cost * 100
        )
