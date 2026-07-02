from fastapi.testclient import TestClient

from routellm.main import app


def test_route_rejects_when_budget_is_too_low() -> None:
    client = TestClient(app)
    payload = {
        "tenant_id": "demo",
        "workflow_id": "tight-budget",
        "task_type": "qa",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_budget_usd": 0.0,
        "latency_slo_ms": 2000,
    }

    response = client.post("/v1/route", json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == "No candidate model satisfies the request budget."
