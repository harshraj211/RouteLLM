import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Literal, Protocol

import yaml
from pydantic import BaseModel, HttpUrl, ValidationError, model_validator

from routellm.config import Settings, get_settings
from routellm.schemas.models import ModelDescriptor, ModelLatencyProfile, ModelPricing

_ENV_PATTERN = re.compile(r"^\$\{([A-Z_][A-Z0-9_]*)(?::-([^}]*))?\}$")


class ModelRegistryError(RuntimeError):
    """Base error for model registry operations."""


class ModelRegistryValidationError(ModelRegistryError):
    """Raised when a registry document is missing or invalid."""


class ModelAlreadyExistsError(ModelRegistryError):
    """Raised when creating a model whose key already exists."""


class ModelNotFoundError(ModelRegistryError):
    """Raised when a model key does not exist."""


class ModelRegistry(Protocol):
    def list_models(self, *, include_disabled: bool = False) -> list[ModelDescriptor]: ...

    def get_model(self, model_key: str) -> ModelDescriptor | None: ...

    def create_model(self, model: ModelDescriptor) -> ModelDescriptor: ...

    def upsert_model(self, model: ModelDescriptor) -> ModelDescriptor: ...

    def delete_model(self, model_key: str) -> None: ...

    def reload(self) -> list[ModelDescriptor]: ...


class ModelRegistryDocument(BaseModel):
    version: Literal[1] = 1
    models: list[ModelDescriptor]

    @model_validator(mode="after")
    def validate_unique_keys(self) -> "ModelRegistryDocument":
        keys = [model.key for model in self.models]
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        if duplicates:
            raise ValueError(f"Duplicate model keys: {', '.join(duplicates)}")
        return self


@dataclass(slots=True)
class InMemoryModelRegistry:
    models: list[ModelDescriptor]

    @classmethod
    def bootstrap_defaults(cls, settings: Settings | None = None) -> "InMemoryModelRegistry":
        settings = settings or get_settings()
        return cls(
            models=[
                ModelDescriptor(
                    key="local-small",
                    provider="vllm",
                    display_name="Local Small",
                    model_id=settings.local_small_model,
                    endpoint=HttpUrl(settings.local_small_base_url),
                    quality_tier=1,
                    supports_structured_output=False,
                    max_context_tokens=8192,
                    pricing=ModelPricing(
                        input_cost_per_1k_tokens=0.0003,
                        output_cost_per_1k_tokens=0.0005,
                    ),
                    latency=ModelLatencyProfile(p50_ms=350, p95_ms=900),
                ),
                ModelDescriptor(
                    key="local-medium-json",
                    provider="vllm",
                    display_name="Local Medium JSON",
                    model_id=settings.local_medium_model,
                    endpoint=HttpUrl(settings.local_medium_base_url),
                    quality_tier=2,
                    supports_structured_output=True,
                    max_context_tokens=16384,
                    pricing=ModelPricing(
                        input_cost_per_1k_tokens=0.0008,
                        output_cost_per_1k_tokens=0.0011,
                    ),
                    latency=ModelLatencyProfile(p50_ms=700, p95_ms=1800),
                ),
                ModelDescriptor(
                    key="hosted-premium",
                    provider="hosted",
                    display_name="Hosted Premium",
                    model_id=settings.hosted_model,
                    endpoint=HttpUrl(settings.hosted_base_url),
                    api_key_env=settings.hosted_api_key_env,
                    requires_api_key=True,
                    max_output_tokens_param="max_completion_tokens",
                    quality_tier=3,
                    supports_structured_output=True,
                    max_context_tokens=128000,
                    pricing=ModelPricing(
                        input_cost_per_1k_tokens=0.01,
                        output_cost_per_1k_tokens=0.03,
                    ),
                    latency=ModelLatencyProfile(p50_ms=1200, p95_ms=2500),
                ),
            ]
        )

    def list_models(self, *, include_disabled: bool = False) -> list[ModelDescriptor]:
        return [model for model in self.models if include_disabled or model.enabled]

    def get_model(self, model_key: str) -> ModelDescriptor | None:
        return next((model for model in self.models if model.key == model_key), None)

    def create_model(self, model: ModelDescriptor) -> ModelDescriptor:
        if self.get_model(model.key):
            raise ModelAlreadyExistsError(f"Model {model.key!r} already exists.")
        self.models.append(model)
        return model

    def upsert_model(self, model: ModelDescriptor) -> ModelDescriptor:
        self.models = [existing for existing in self.models if existing.key != model.key]
        self.models.append(model)
        return model

    def delete_model(self, model_key: str) -> None:
        if self.get_model(model_key) is None:
            raise ModelNotFoundError(f"Model {model_key!r} was not found.")
        self.models = [model for model in self.models if model.key != model_key]

    def reload(self) -> list[ModelDescriptor]:
        return self.list_models()


class YamlModelRegistry:
    def __init__(
        self,
        path: Path,
        models: list[ModelDescriptor],
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self.path = path
        self._models = {model.key: model for model in models}
        self._environment = dict(environment or {})
        self._lock = RLock()

    @classmethod
    def from_file(
        cls,
        path: Path,
        environment: Mapping[str, str] | None = None,
    ) -> "YamlModelRegistry":
        registry = cls(path=path, models=[], environment=environment)
        registry.reload()
        return registry

    @classmethod
    def from_settings(cls, settings: Settings) -> "YamlModelRegistry":
        environment = {
            "ROUTELLM_LOCAL_SMALL_BASE_URL": settings.local_small_base_url,
            "ROUTELLM_LOCAL_SMALL_MODEL": settings.local_small_model,
            "ROUTELLM_LOCAL_MEDIUM_BASE_URL": settings.local_medium_base_url,
            "ROUTELLM_LOCAL_MEDIUM_MODEL": settings.local_medium_model,
            "ROUTELLM_HOSTED_BASE_URL": settings.hosted_base_url,
            "ROUTELLM_HOSTED_MODEL": settings.hosted_model,
        }
        return cls.from_file(settings.model_registry_path, environment=environment)

    @classmethod
    def create(cls, path: Path, models: list[ModelDescriptor]) -> "YamlModelRegistry":
        document = ModelRegistryDocument(models=models)
        registry = cls(path=path, models=document.models)
        registry._persist()
        return registry

    def list_models(self, *, include_disabled: bool = False) -> list[ModelDescriptor]:
        with self._lock:
            return [
                model
                for model in self._models.values()
                if include_disabled or model.enabled
            ]

    def get_model(self, model_key: str) -> ModelDescriptor | None:
        with self._lock:
            return self._models.get(model_key)

    def create_model(self, model: ModelDescriptor) -> ModelDescriptor:
        with self._lock:
            if model.key in self._models:
                raise ModelAlreadyExistsError(f"Model {model.key!r} already exists.")
            self._models[model.key] = model
            self._persist()
            return model

    def upsert_model(self, model: ModelDescriptor) -> ModelDescriptor:
        with self._lock:
            self._models[model.key] = model
            self._persist()
            return model

    def delete_model(self, model_key: str) -> None:
        with self._lock:
            if model_key not in self._models:
                raise ModelNotFoundError(f"Model {model_key!r} was not found.")
            del self._models[model_key]
            self._persist()

    def reload(self) -> list[ModelDescriptor]:
        with self._lock:
            try:
                raw_document = yaml.safe_load(self.path.read_text(encoding="utf-8"))
                expanded_document = _expand_environment_values(raw_document, self._environment)
                document = ModelRegistryDocument.model_validate(expanded_document)
            except FileNotFoundError as exc:
                raise ModelRegistryValidationError(
                    f"Model registry file {self.path} does not exist."
                ) from exc
            except (OSError, yaml.YAMLError, ValidationError, ValueError) as exc:
                raise ModelRegistryValidationError(
                    f"Model registry file {self.path} is invalid: {exc}"
                ) from exc
            self._models = {model.key: model for model in document.models}
            return list(self._models.values())

    def _persist(self) -> None:
        document = ModelRegistryDocument(models=list(self._models.values()))
        payload = document.model_dump(mode="json", exclude_none=True)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        try:
            temporary_path.write_text(
                yaml.safe_dump(payload, sort_keys=False),
                encoding="utf-8",
            )
            os.replace(temporary_path, self.path)
        except OSError as exc:
            temporary_path.unlink(missing_ok=True)
            raise ModelRegistryError(
                f"Could not persist model registry {self.path}: {exc}"
            ) from exc


def _expand_environment_values(value: Any, environment: Mapping[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _expand_environment_values(item, environment) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_environment_values(item, environment) for item in value]
    if not isinstance(value, str):
        return value

    match = _ENV_PATTERN.fullmatch(value)
    if not match:
        return value
    variable_name, default = match.groups()
    environment_value = os.getenv(variable_name, environment.get(variable_name, default))
    if environment_value is None:
        raise ModelRegistryValidationError(
            f"Environment variable {variable_name!r} required by the registry is not set."
        )
    return environment_value
