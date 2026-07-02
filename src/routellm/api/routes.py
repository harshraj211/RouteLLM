from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from routellm.observability.metrics import ACTIVE_REQUESTS
from routellm.schemas.models import ModelDescriptor
from routellm.schemas.routing import HealthResponse, RouteRequest, RouteResponse
from routellm.services.registry import InMemoryModelRegistry
from routellm.services.router import RoutingService

api_router = APIRouter()
registry = InMemoryModelRegistry.bootstrap_defaults()
router_service = RoutingService(model_registry=registry)


@api_router.get("/healthz", response_model=HealthResponse, tags=["system"])
async def healthcheck() -> HealthResponse:
    return HealthResponse(status="ok")


@api_router.get("/models", response_model=list[ModelDescriptor], tags=["models"])
async def list_models() -> list[ModelDescriptor]:
    return registry.list_models()


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
