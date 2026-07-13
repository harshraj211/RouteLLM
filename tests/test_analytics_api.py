from fastapi.testclient import TestClient

from routellm.main import app


def test_analytics_endpoints_and_dashboard_expose_routing_savings() -> None:
    client = TestClient(app)
    route_response = client.post(
        "/v1/route",
        json={
            "tenant_id": "analytics-api-test",
            "workflow_id": "dashboard",
            "task_type": "qa",
            "messages": [{"role": "user", "content": "Summarize this short note."}],
            "max_budget_usd": 0,
            "latency_slo_ms": 2000,
        },
    )

    assert route_response.status_code == 200

    summary_response = client.get("/v1/analytics/summary")
    decisions_response = client.get("/v1/analytics/decisions?limit=10")
    dashboard_response = client.get("/dashboard")

    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["request_count"] >= 1
    assert summary["reference_baseline_model"] == "hosted-premium"
    assert "estimated_savings_usd" in summary

    assert decisions_response.status_code == 200
    assert any(item["is_local"] for item in decisions_response.json())

    assert dashboard_response.status_code == 200
    assert "RouteLLM Control Room" in dashboard_response.text
