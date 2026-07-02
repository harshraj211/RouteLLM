from fastapi.testclient import TestClient

from routellm.main import app


def test_single_decision_endpoint_returns_saved_record() -> None:
    client = TestClient(app)
    payload = {
        "tenant_id": "demo",
        "workflow_id": "detail-check",
        "task_type": "qa",
        "messages": [{"role": "user", "content": "hello"}],
        "max_budget_usd": 0.01,
        "latency_slo_ms": 2000,
    }

    client.post("/v1/route", json=payload)
    decisions = client.get("/v1/decisions").json()
    detail = client.get(f"/v1/decisions/{decisions[0]['id']}")

    assert detail.status_code == 200
    assert detail.json()["id"] == decisions[0]["id"]
