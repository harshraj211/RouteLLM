from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from routellm.api import routes
from routellm.main import app
from routellm.schemas.models import ModelDescriptor, ModelLatencyProfile, ModelPricing
from routellm.services.registry import (
    ModelAlreadyExistsError,
    ModelRegistryValidationError,
    YamlModelRegistry,
)


def _model(*, key: str = "test-model", display_name: str = "Test Model") -> ModelDescriptor:
    return ModelDescriptor(
        key=key,
        provider="vllm",
        display_name=display_name,
        model_id=f"upstream-{key}",
        endpoint="http://localhost:9000/v1",
        quality_tier=2,
        supports_structured_output=True,
        max_context_tokens=8192,
        pricing=ModelPricing(
            input_cost_per_1k_tokens=0.001,
            output_cost_per_1k_tokens=0.002,
        ),
        latency=ModelLatencyProfile(p50_ms=100, p95_ms=250),
    )


def test_yaml_registry_persists_crud_and_reloads(tmp_path: Path) -> None:
    registry_path = tmp_path / "models.yaml"
    registry = YamlModelRegistry.create(registry_path, [_model(key="first")])

    registry.create_model(_model(key="second"))
    registry.upsert_model(_model(key="second", display_name="Updated Second"))
    reloaded = YamlModelRegistry.from_file(registry_path)

    assert [model.key for model in reloaded.list_models()] == ["first", "second"]
    assert reloaded.get_model("second").display_name == "Updated Second"  # type: ignore[union-attr]

    reloaded.delete_model("second")
    assert YamlModelRegistry.from_file(registry_path).get_model("second") is None


def test_yaml_registry_rejects_duplicate_keys(tmp_path: Path) -> None:
    registry_path = tmp_path / "models.yaml"
    registry_path.write_text(
        """
version: 1
models:
  - key: duplicate
    provider: vllm
    display_name: First
    model_id: first
    quality_tier: 1
    max_context_tokens: 1024
    pricing: {input_cost_per_1k_tokens: 0, output_cost_per_1k_tokens: 0}
    latency: {p50_ms: 1, p95_ms: 2}
  - key: duplicate
    provider: vllm
    display_name: Second
    model_id: second
    quality_tier: 1
    max_context_tokens: 1024
    pricing: {input_cost_per_1k_tokens: 0, output_cost_per_1k_tokens: 0}
    latency: {p50_ms: 1, p95_ms: 2}
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ModelRegistryValidationError, match="Duplicate model keys"):
        YamlModelRegistry.from_file(registry_path)


def test_yaml_registry_expands_environment_values(tmp_path: Path) -> None:
    registry_path = tmp_path / "models.yaml"
    registry_path.write_text(
        """
version: 1
models:
  - key: configured
    provider: vllm
    display_name: Configured
    model_id: ${TEST_MODEL_ID:-fallback-model}
    endpoint: ${TEST_MODEL_ENDPOINT:-http://localhost:8000/v1}
    quality_tier: 1
    max_context_tokens: 1024
    pricing: {input_cost_per_1k_tokens: 0, output_cost_per_1k_tokens: 0}
    latency: {p50_ms: 1, p95_ms: 2}
""".strip(),
        encoding="utf-8",
    )

    registry = YamlModelRegistry.from_file(
        registry_path,
        environment={"TEST_MODEL_ID": "configured-model"},
    )

    assert registry.list_models()[0].model_id == "configured-model"
    assert str(registry.list_models()[0].endpoint) == "http://localhost:8000/v1"


def test_yaml_registry_create_rejects_existing_key(tmp_path: Path) -> None:
    registry = YamlModelRegistry.create(tmp_path / "models.yaml", [_model()])

    with pytest.raises(ModelAlreadyExistsError):
        registry.create_model(_model())


def test_disabled_models_are_visible_only_when_requested(tmp_path: Path) -> None:
    disabled = _model(key="disabled").model_copy(update={"enabled": False})
    registry = YamlModelRegistry.create(
        tmp_path / "models.yaml",
        [_model(key="enabled"), disabled],
    )

    assert [model.key for model in registry.list_models()] == ["enabled"]
    assert [
        model.key for model in registry.list_models(include_disabled=True)
    ] == ["enabled", "disabled"]


def test_live_registry_excludes_models_with_missing_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TEST_PROVIDER_API_KEY", raising=False)
    credentialed = _model(key="credentialed").model_copy(
        update={
            "api_key_env": "TEST_PROVIDER_API_KEY",
            "requires_api_key": True,
        }
    )
    registry_path = tmp_path / "models.yaml"
    YamlModelRegistry.create(registry_path, [_model(key="local"), credentialed])

    live_registry = YamlModelRegistry.from_file(
        registry_path,
        require_credentials=True,
    )

    assert [model.key for model in live_registry.list_models()] == ["local"]
    assert [
        model.key for model in live_registry.list_models(include_disabled=True)
    ] == ["local", "credentialed"]


def test_live_registry_includes_models_with_configured_credentials(
    tmp_path: Path,
) -> None:
    credentialed = _model(key="credentialed").model_copy(
        update={
            "api_key_env": "TEST_PROVIDER_API_KEY",
            "requires_api_key": True,
        }
    )
    registry_path = tmp_path / "models.yaml"
    YamlModelRegistry.create(registry_path, [credentialed])

    live_registry = YamlModelRegistry.from_file(
        registry_path,
        environment={"TEST_PROVIDER_API_KEY": "configured"},
        require_credentials=True,
    )

    assert [model.key for model in live_registry.list_models()] == ["credentialed"]


def test_model_crud_api_persists_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry = YamlModelRegistry.create(tmp_path / "models.yaml", [_model(key="existing")])
    monkeypatch.setattr(routes, "registry", registry)
    monkeypatch.setattr(routes.router_service, "model_registry", registry)
    client = TestClient(app)
    model_payload = _model(key="created").model_dump(mode="json")

    created = client.post("/v1/models", json=model_payload)
    fetched = client.get("/v1/models/created")
    model_payload["display_name"] = "Updated"
    updated = client.put("/v1/models/created", json=model_payload)
    deleted = client.delete("/v1/models/created")

    assert created.status_code == 201
    assert fetched.status_code == 200
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Updated"
    assert deleted.status_code == 204
    assert YamlModelRegistry.from_file(registry.path).get_model("created") is None


def test_model_crud_api_can_be_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry = YamlModelRegistry.create(tmp_path / "models.yaml", [_model(key="existing")])
    monkeypatch.setattr(routes, "registry", registry)
    monkeypatch.setattr(routes.settings, "model_registry_writes_enabled", False)
    client = TestClient(app)

    response = client.post("/v1/models", json=_model(key="blocked").model_dump(mode="json"))

    assert response.status_code == 403
    assert registry.get_model("blocked") is None


def test_model_list_api_includes_disabled_models(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    disabled = _model(key="disabled").model_copy(update={"enabled": False})
    registry = YamlModelRegistry.create(tmp_path / "models.yaml", [disabled])
    monkeypatch.setattr(routes, "registry", registry)
    client = TestClient(app)

    response = client.get("/v1/models")

    assert response.status_code == 200
    assert response.json()[0]["key"] == "disabled"
    assert response.json()[0]["enabled"] is False
