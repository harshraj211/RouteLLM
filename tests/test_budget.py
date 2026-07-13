from fastapi.testclient import TestClient

from routellm.main import app


def test_route_allows_zero_budget_for_a_zero_cost_local_model() -> None:
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

    assert response.status_code == 200
    assert response.json()["decision"]["selected_model"] == "local-small"
    assert response.json()["usage"]["actual_cost_usd"] == 0.0
