from pydantic import BaseModel


class EscalationAttempt(BaseModel):
    from_model: str
    to_model: str
    reason_codes: list[str]
