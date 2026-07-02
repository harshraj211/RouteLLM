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
