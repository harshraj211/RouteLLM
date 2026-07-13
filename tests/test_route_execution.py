from fastapi.testclient import TestClient

from routellm.adapters.base import InferenceAdapterError
from routellm.api.routes import router_service
from routellm.main import app
from routellm.schemas.models import ModelDescriptor
from routellm.schemas.routing import RouteRequest


def test_route_uses_provider_adapter_output() -> None:
    client = TestClient(app)
    payload = {
        "tenant_id": "demo",
        "workflow_id": "support",
        "task_type": "qa",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_budget_usd": 0.01,
        "latency_slo_ms": 2000,
    }

    response = client.post("/v1/route", json=payload)

    assert response.status_code == 200
    assert "[vllm:" in response.json()["output"]["text"]
    assert response.json()["usage"]["provider_request_id"].startswith("mock-")


def test_route_maps_upstream_failure_to_bad_gateway(monkeypatch) -> None:
    async def fail_invoke(request: RouteRequest, model: ModelDescriptor) -> None:
        raise InferenceAdapterError(
            "The upstream model request timed out.",
            model_key=model.key,
            retryable=False,
            reason_code="UPSTREAM_UNCERTAIN_TIMEOUT",
        )

    monkeypatch.setattr(router_service.execution_service, "invoke", fail_invoke)
    client = TestClient(app)
    response = client.post(
        "/v1/route",
        json={
            "tenant_id": "demo",
            "workflow_id": "support",
            "task_type": "qa",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_budget_usd": 0.01,
            "latency_slo_ms": 2000,
        },
    )

    assert response.status_code == 502
    assert response.json()["detail"] == {
        "code": "UPSTREAM_MODEL_ERROR",
        "model": "local-small",
        "message": "The upstream model request timed out.",
        "retryable": False,
    }
