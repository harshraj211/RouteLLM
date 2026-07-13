from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from routellm.schemas.escalation import EscalationAttempt, InferenceAttempt
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
    requested_model: str | None = None
    messages: list[Message]
    max_budget_usd: float
    latency_slo_ms: int
    safety_tier: str = "medium"
    response_format: Literal["text", "json"] = "text"
    max_output_tokens: int | None = Field(default=None, gt=0)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    stop: str | list[str] | None = None
    presence_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    frequency_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    seed: int | None = None


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
    latency_ms: int | None = None
    provider_request_id: str | None = None
    provider_model: str | None = None


class RouteOutput(BaseModel):
    text: str
    finish_reason: str | None = None


class RouteResponse(BaseModel):
    request_id: str
    decision: RouteDecision
    evaluation: EvaluationResult
    usage: RouteUsage
    execution_attempts: list[InferenceAttempt]
    escalation_path: list[EscalationAttempt]
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
