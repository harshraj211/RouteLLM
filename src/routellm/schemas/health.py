from pydantic import BaseModel


class ModelHealthSnapshot(BaseModel):
    model_key: str
    provider: str
    health_score: float
    p50_latency_ms: int
    p95_latency_ms: int
