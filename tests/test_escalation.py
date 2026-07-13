from fastapi.testclient import TestClient

from routellm.main import app


def test_route_response_exposes_structured_escalation_path() -> None:
    client = TestClient(app)
    payload = {
        "tenant_id": "demo",
        "workflow_id": "ops-extract",
        "task_type": "extraction",
        "messages": [{"role": "user", "content": "Extract fields as JSON."}],
        "max_budget_usd": 0.02,
        "latency_slo_ms": 2500,
        "response_format": "json",
    }

    response = client.post("/v1/route", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "escalation_path" in data
    assert isinstance(data["escalation_path"], list)
    assert data["execution_attempts"][0]["outcome"] == "success"
