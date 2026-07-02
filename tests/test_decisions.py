from fastapi.testclient import TestClient

from routellm.main import app


def test_route_decisions_are_persisted_and_listed() -> None:
    client = TestClient(app)
    payload = {
        "tenant_id": "demo",
        "workflow_id": "audit",
        "task_type": "qa",
        "messages": [{"role": "user", "content": "Summarize this text."}],
        "max_budget_usd": 0.02,
        "latency_slo_ms": 2000,
    }

    route_response = client.post("/v1/route", json=payload)
    assert route_response.status_code == 200

    decisions_response = client.get("/v1/decisions")
    assert decisions_response.status_code == 200
    assert len(decisions_response.json()) >= 1
