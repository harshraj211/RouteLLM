from fastapi.testclient import TestClient

from routellm.main import app


def test_budget_snapshot_endpoint_reflects_recorded_spend() -> None:
    client = TestClient(app)
    payload = {
        "tenant_id": "budget-check",
        "workflow_id": "ops",
        "task_type": "qa",
        "messages": [{"role": "user", "content": "hello"}],
        "max_budget_usd": 0.01,
        "latency_slo_ms": 2000,
    }

    client.post("/v1/route", json=payload)
    response = client.get("/v1/budgets/budget-check")

    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "budget-check"
    assert data["request_count"] >= 1
