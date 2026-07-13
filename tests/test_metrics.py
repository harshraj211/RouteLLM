from fastapi.testclient import TestClient

from routellm.main import app


def test_metrics_endpoint_exposes_prometheus_payload() -> None:
    client = TestClient(app)
    response = client.get("/v1/metrics")

    assert response.status_code == 200
    assert "routellm_requests_total" in response.text
    assert "routellm_inference_retries_total" in response.text
    assert "routellm_model_failovers_total" in response.text
