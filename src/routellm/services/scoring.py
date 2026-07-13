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
        semantic_affinity = model.task_affinities.get(
            analysis.semantic_intent,
            model.task_affinities.get("general_qa", 0.5),
        )
        capability_coverage = self._capability_coverage(model, analysis)

        return (
            quality_bonus
            + availability_bonus
            + complexity_bonus
            + (semantic_affinity * 2.0)
            + (capability_coverage * 0.75)
            - latency_penalty
            - (estimated_cost * 100)
        )

    @staticmethod
    def _capability_coverage(model: ModelDescriptor, analysis: RequestAnalysis) -> float:
        if not analysis.required_capabilities:
            return 1.0
        matched = analysis.required_capabilities.intersection(model.capabilities)
        return len(matched) / len(analysis.required_capabilities)
