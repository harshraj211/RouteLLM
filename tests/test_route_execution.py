from fastapi.testclient import TestClient

from routellm.main import app


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
