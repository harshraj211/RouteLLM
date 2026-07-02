from fastapi import APIRouter

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


@api_router.post("/route", response_model=RouteResponse, tags=["routing"])
async def route_request(payload: RouteRequest) -> RouteResponse:
    return await router_service.route(payload)
