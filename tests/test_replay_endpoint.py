from fastapi.testclient import TestClient

from routellm.main import app


def test_default_replay_endpoint_returns_summary() -> None:
    client = TestClient(app)
    response = client.post("/v1/replay/default")

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_name"] == "benchmark_requests"
    assert payload["requests_replayed"] == 3
    assert len(payload["selected_models"]) == 3


def test_compare_default_replay_reports_local_first_savings() -> None:
    client = TestClient(app)
    response = client.post("/v1/replay/compare-default")

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_name"] == "benchmark_requests"
    assert payload["requests_replayed"] == 3
    assert payload["reference_cloud_model"] == "hosted-premium"
    assert payload["always_cloud_estimated_cost_usd"] > 0
    assert payload["estimated_savings_usd"] > 0
    assert payload["estimated_savings_percent"] > 0
