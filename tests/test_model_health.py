from fastapi.testclient import TestClient

from routellm.main import app


def test_model_health_endpoint_lists_registered_models() -> None:
    client = TestClient(app)
    response = client.get("/v1/models/health")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) >= 1
    assert "model_key" in payload[0]
