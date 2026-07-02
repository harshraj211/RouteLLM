from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from routellm.db.session import get_session
from routellm.observability.metrics import ACTIVE_REQUESTS
from routellm.repositories.routing_decisions import RoutingDecisionRepository
from routellm.schemas.models import ModelDescriptor
from routellm.schemas.policies import RoutingPolicy
from routellm.schemas.routing import (
    HealthResponse,
    RouteRequest,
    RouteResponse,
    RoutingDecisionRecordResponse,
)
from routellm.services.registry import InMemoryModelRegistry
from routellm.services.policy_store import InMemoryPolicyStore
from routellm.services.router import RoutingService

api_router = APIRouter()
registry = InMemoryModelRegistry.bootstrap_defaults()
policy_store = InMemoryPolicyStore.bootstrap_defaults()
router_service = RoutingService(model_registry=registry)


@api_router.get("/healthz", response_model=HealthResponse, tags=["system"])
async def healthcheck() -> HealthResponse:
    return HealthResponse(status="ok")


@api_router.get("/models", response_model=list[ModelDescriptor], tags=["models"])
async def list_models() -> list[ModelDescriptor]:
    return registry.list_models()


@api_router.get("/policies", response_model=list[RoutingPolicy], tags=["policies"])
async def list_policies() -> list[RoutingPolicy]:
    return policy_store.list_policies()


@api_router.get("/metrics", response_class=PlainTextResponse, tags=["system"])
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)


@api_router.post("/route", response_model=RouteResponse, tags=["routing"])
async def route_request(payload: RouteRequest) -> RouteResponse:
    ACTIVE_REQUESTS.inc()
    try:
        return await router_service.route(payload)
    finally:
        ACTIVE_REQUESTS.dec()


@api_router.get("/decisions", response_model=list[RoutingDecisionRecordResponse], tags=["routing"])
async def list_decisions(limit: int = 50) -> list[RoutingDecisionRecordResponse]:
    session = get_session()
    try:
        records = RoutingDecisionRepository(session).list_recent(limit=limit)
        return [
            RoutingDecisionRecordResponse(
                id=record.id,
                request_id=record.request_id,
                tenant_id=record.tenant_id,
                workflow_id=record.workflow_id,
                task_type=record.task_type,
                selected_model=record.selected_model,
                reason_codes=record.reason_codes.split(","),
                estimated_input_tokens=record.estimated_input_tokens,
                estimated_output_tokens=record.estimated_output_tokens,
                estimated_cost_usd=record.estimated_cost_usd,
                actual_cost_usd=record.actual_cost_usd,
                estimated_latency_ms=record.estimated_latency_ms,
            )
            for record in records
        ]
    finally:
        session.close()
