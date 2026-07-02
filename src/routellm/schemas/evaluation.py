from pydantic import BaseModel


class EvaluationResult(BaseModel):
    accepted: bool
    confidence_score: float
    reason_codes: list[str]
