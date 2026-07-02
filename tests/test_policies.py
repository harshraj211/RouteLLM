from fastapi.testclient import TestClient

from routellm.main import app


def test_policies_endpoint_lists_default_policies() -> None:
    client = TestClient(app)
    response = client.get("/v1/policies")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) >= 2
    assert any(policy["key"] == "default" for policy in payload)
