from uuid import uuid4

from pydantic import BaseModel, Field

from routellm.schemas.evaluation import EvaluationResult


class HealthResponse(BaseModel):
    status: str


class Message(BaseModel):
    role: str
    content: str


class RouteRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    workflow_id: str
    task_type: str
    messages: list[Message]
    max_budget_usd: float
    latency_slo_ms: int
    safety_tier: str = "medium"
    response_format: str = "text"


class RouteDecision(BaseModel):
    selected_model: str
    reason_codes: list[str]
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost_usd: float
    estimated_latency_ms: int


class RouteUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    actual_cost_usd: float


class RouteOutput(BaseModel):
    text: str


class RouteResponse(BaseModel):
    request_id: str
    decision: RouteDecision
    evaluation: EvaluationResult
    usage: RouteUsage
    escalation_path: list[str]
    output: RouteOutput


class RoutingDecisionRecordResponse(BaseModel):
    id: int
    request_id: str
    tenant_id: str
    workflow_id: str
    task_type: str
    selected_model: str
    reason_codes: list[str]
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost_usd: float
    actual_cost_usd: float
    estimated_latency_ms: int
