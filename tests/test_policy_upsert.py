from fastapi.testclient import TestClient

from routellm.main import app


def test_policy_upsert_endpoint_persists_runtime_policy() -> None:
    client = TestClient(app)
    payload = {
        "key": "runtime-policy",
        "task_types": ["qa"],
        "minimum_quality_tier": 2,
        "allowed_providers": ["vllm"],
    }

    response = client.post("/v1/policies", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["key"] == "runtime-policy"
    assert data["minimum_quality_tier"] == 2
