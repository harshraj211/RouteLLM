from fastapi import APIRouter, Header, HTTPException, Response
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from routellm.adapters.base import InferenceAdapterError
from routellm.config import get_settings
from routellm.db.session import get_session
from routellm.observability.metrics import ACTIVE_REQUESTS
from routellm.repositories.routing_decisions import RoutingDecisionRepository
from routellm.schemas.analytics import AnalyticsDecision, AnalyticsSummary
from routellm.schemas.budget import TenantBudgetSnapshot
from routellm.schemas.chat_completions import ChatCompletionRequest
from routellm.schemas.health import ModelHealthSnapshot
from routellm.schemas.models import ModelDescriptor
from routellm.schemas.policies import RoutingPolicy
from routellm.schemas.replay import ReplaySummaryResponse
from routellm.schemas.routing import (
    HealthResponse,
    RouteRequest,
    RouteResponse,
    RoutingDecisionRecordResponse,
)
from routellm.schemas.runtime import OllamaRuntimeStatus
from routellm.services.analytics import AnalyticsService
from routellm.services.chat_completions import (
    ChatCompletionsService,
    ChatRoutingControls,
    UnsupportedChatCompletionRequest,
)
from routellm.services.model_health import ModelHealthService
from routellm.services.ollama_runtime import OllamaRuntimeService
from routellm.services.policy_store import InMemoryPolicyStore
from routellm.services.registry import (
    ModelAlreadyExistsError,
    ModelNotFoundError,
    ModelRegistryValidationError,
    YamlModelRegistry,
)
from routellm.services.replay_service import ReplayService
from routellm.services.router import RoutingService

api_router = APIRouter()
settings = get_settings()
registry = YamlModelRegistry.from_settings(settings)
policy_store = InMemoryPolicyStore.bootstrap_defaults()
router_service = RoutingService(model_registry=registry, settings=settings)
chat_completions_service = ChatCompletionsService(router_service, settings)
replay_service = ReplayService(router_service)
model_health_service = ModelHealthService()
analytics_service = AnalyticsService()
ollama_runtime_service = OllamaRuntimeService(
    timeout_seconds=min(settings.inference_timeout_seconds, 3.0),
)


@api_router.get("/healthz", response_model=HealthResponse, tags=["system"])
async def healthcheck() -> HealthResponse:
    return HealthResponse(status="ok")


@api_router.get("/models", response_model=list[ModelDescriptor], tags=["models"])
async def list_models() -> list[ModelDescriptor]:
    return registry.list_models(include_disabled=True)


@api_router.post(
    "/models",
    response_model=ModelDescriptor,
    status_code=201,
    tags=["models"],
)
async def create_model(model: ModelDescriptor) -> ModelDescriptor:
    _ensure_registry_writes_enabled()
    try:
        return registry.create_model(model)
    except ModelAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@api_router.get("/models/health", response_model=list[ModelHealthSnapshot], tags=["models"])
async def list_model_health() -> list[ModelHealthSnapshot]:
    return model_health_service.summarize(registry.list_models(include_disabled=True))


@api_router.get("/runtime/ollama", response_model=list[OllamaRuntimeStatus], tags=["system"])
async def inspect_ollama_runtime() -> list[OllamaRuntimeStatus]:
    """Report whether configured local Ollama models are available to RouteLLM."""

    return await ollama_runtime_service.inspect(registry.list_models())


@api_router.post("/models/reload", response_model=list[ModelDescriptor], tags=["models"])
async def reload_models() -> list[ModelDescriptor]:
    try:
        return registry.reload()
    except ModelRegistryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@api_router.get("/models/{model_key}", response_model=ModelDescriptor, tags=["models"])
async def get_model(model_key: str) -> ModelDescriptor:
    model = registry.get_model(model_key)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Model {model_key!r} was not found.")
    return model


@api_router.put("/models/{model_key}", response_model=ModelDescriptor, tags=["models"])
async def update_model(model_key: str, model: ModelDescriptor) -> ModelDescriptor:
    _ensure_registry_writes_enabled()
    if model.key != model_key:
        raise HTTPException(
            status_code=400,
            detail="The model key in the path must match the request body.",
        )
    if registry.get_model(model_key) is None:
        raise HTTPException(status_code=404, detail=f"Model {model_key!r} was not found.")
    return registry.upsert_model(model)


@api_router.delete("/models/{model_key}", status_code=204, tags=["models"])
async def delete_model(model_key: str) -> Response:
    _ensure_registry_writes_enabled()
    try:
        registry.delete_model(model_key)
    except ModelNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)


def _ensure_registry_writes_enabled() -> None:
    if not settings.model_registry_writes_enabled:
        raise HTTPException(status_code=403, detail="Model registry writes are disabled.")


@api_router.get("/policies", response_model=list[RoutingPolicy], tags=["policies"])
async def list_policies() -> list[RoutingPolicy]:
    return policy_store.list_policies()


@api_router.post("/policies", response_model=RoutingPolicy, tags=["policies"])
async def create_or_update_policy(policy: RoutingPolicy) -> RoutingPolicy:
    return policy_store.upsert_policy(policy)


@api_router.get("/budgets/{tenant_id}", response_model=TenantBudgetSnapshot, tags=["budgets"])
async def get_tenant_budget_snapshot(tenant_id: str) -> TenantBudgetSnapshot:
    return router_service.budget_ledger.get_snapshot(tenant_id)


@api_router.get("/analytics/summary", response_model=AnalyticsSummary, tags=["analytics"])
async def get_analytics_summary() -> AnalyticsSummary:
    session = get_session()
    try:
        records = RoutingDecisionRepository(session).list_recent(limit=10_000)
        return analytics_service.summarize(
            records,
            registry.list_models(include_disabled=True),
            baseline_model_key=settings.analytics_baseline_model_key,
        )
    finally:
        session.close()


@api_router.get(
    "/analytics/decisions",
    response_model=list[AnalyticsDecision],
    tags=["analytics"],
)
async def list_analytics_decisions(limit: int = 50) -> list[AnalyticsDecision]:
    session = get_session()
    try:
        records = RoutingDecisionRepository(session).list_recent(limit=limit)
        return analytics_service.decisions(
            records,
            registry.list_models(include_disabled=True),
            baseline_model_key=settings.analytics_baseline_model_key,
        )
    finally:
        session.close()


@api_router.post("/replay/default", response_model=ReplaySummaryResponse, tags=["evals"])
async def replay_default_benchmark() -> ReplaySummaryResponse:
    summary = await replay_service.run_default_benchmark()
    return ReplaySummaryResponse(
        dataset_name=summary.dataset_name,
        requests_replayed=summary.requests_replayed,
        average_estimated_cost_usd=summary.average_estimated_cost_usd,
        selected_models=summary.selected_models,
    )


@api_router.get("/metrics", response_class=PlainTextResponse, tags=["system"])
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)


@api_router.post("/route", response_model=RouteResponse, tags=["routing"])
async def route_request(payload: RouteRequest) -> RouteResponse:
    ACTIVE_REQUESTS.inc()
    try:
        try:
            return await router_service.route(payload)
        except InferenceAdapterError as exc:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "UPSTREAM_MODEL_ERROR",
                    "model": exc.model_key,
                    "message": str(exc),
                    "retryable": exc.retryable,
                },
            ) from exc
    finally:
        ACTIVE_REQUESTS.dec()


@api_router.post("/chat/completions", response_model=None, tags=["compatibility"])
async def create_chat_completion(
    payload: ChatCompletionRequest,
    x_routellm_tenant_id: str | None = Header(default=None, alias="X-RouteLLM-Tenant-Id"),
    x_routellm_workflow_id: str | None = Header(default=None, alias="X-RouteLLM-Workflow-Id"),
    x_routellm_task_type: str | None = Header(default=None, alias="X-RouteLLM-Task-Type"),
    x_routellm_max_budget_usd: float | None = Header(
        default=None,
        alias="X-RouteLLM-Max-Budget-USD",
        gt=0,
    ),
    x_routellm_latency_slo_ms: int | None = Header(
        default=None,
        alias="X-RouteLLM-Latency-SLO-MS",
        gt=0,
    ),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> Response:
    controls = ChatRoutingControls(
        tenant_id=x_routellm_tenant_id or settings.chat_default_tenant_id,
        workflow_id=x_routellm_workflow_id or settings.chat_default_workflow_id,
        task_type=x_routellm_task_type or settings.chat_default_task_type,
        max_budget_usd=x_routellm_max_budget_usd or settings.chat_default_max_budget_usd,
        latency_slo_ms=x_routellm_latency_slo_ms or settings.chat_default_latency_slo_ms,
        request_id=x_request_id,
    )

    ACTIVE_REQUESTS.inc()
    try:
        try:
            route_response = await chat_completions_service.complete(payload, controls)
        except UnsupportedChatCompletionRequest as exc:
            return _chat_error_response(
                status_code=400,
                message=str(exc),
                error_type="invalid_request_error",
                code=exc.code,
                param=exc.param,
            )
        except InferenceAdapterError as exc:
            return _chat_error_response(
                status_code=502,
                message=str(exc),
                error_type="upstream_error",
                code=exc.reason_code.lower(),
            )
        except HTTPException as exc:
            message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            return _chat_error_response(
                status_code=exc.status_code,
                message=message,
                error_type="invalid_request_error",
                code="routing_error",
            )
    finally:
        ACTIVE_REQUESTS.dec()

    completion = chat_completions_service.to_response(route_response)
    headers = {
        "X-Request-Id": route_response.request_id,
        "X-RouteLLM-Selected-Model": route_response.decision.selected_model,
        "X-RouteLLM-Execution-Attempts": str(len(route_response.execution_attempts)),
    }
    if payload.stream:
        include_usage = bool(payload.stream_options and payload.stream_options.include_usage)
        headers["Cache-Control"] = "no-cache"
        headers["X-Accel-Buffering"] = "no"
        return StreamingResponse(
            chat_completions_service.stream_response(
                completion,
                include_usage=include_usage,
            ),
            media_type="text/event-stream",
            headers=headers,
        )
    return JSONResponse(
        completion.model_dump(exclude_none=True),
        headers=headers,
    )


def _chat_error_response(
    *,
    status_code: int,
    message: str,
    error_type: str,
    code: str,
    param: str | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "message": message,
                "type": error_type,
                "param": param,
                "code": code,
            }
        },
    )


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


@api_router.get(
    "/decisions/{decision_id}", response_model=RoutingDecisionRecordResponse, tags=["routing"]
)
async def get_decision(decision_id: int) -> RoutingDecisionRecordResponse:
    session = get_session()
    try:
        record = RoutingDecisionRepository(session).get_by_id(decision_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Routing decision not found.")

        return RoutingDecisionRecordResponse(
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
    finally:
        session.close()
