from typing import Literal

from pydantic import BaseModel


class InferenceAttempt(BaseModel):
    model: str
    attempt_number: int
    outcome: Literal["success", "retryable_error", "error"]
    reason_codes: list[str]
    status_code: int | None = None


class EscalationAttempt(BaseModel):
    from_model: str
    to_model: str
    reason_codes: list[str]
