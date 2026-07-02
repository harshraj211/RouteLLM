from fastapi.testclient import TestClient

from routellm.main import app


def test_healthcheck() -> None:
    client = TestClient(app)
    response = client.get("/v1/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
