"""Readiness checks for local Ollama endpoints."""

from collections import defaultdict
from urllib.parse import urlsplit, urlunsplit

import httpx
from pydantic import HttpUrl

from routellm.schemas.models import ModelDescriptor
from routellm.schemas.runtime import LocalModelReadiness, OllamaRuntimeStatus


class OllamaRuntimeService:
    def __init__(
        self,
        *,
        timeout_seconds: float = 3.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self._client = client

    async def inspect(self, models: list[ModelDescriptor]) -> list[OllamaRuntimeStatus]:
        models_by_endpoint: dict[str, list[ModelDescriptor]] = defaultdict(list)
        for model in models:
            if model.provider == "ollama" and model.endpoint is not None:
                models_by_endpoint[str(model.endpoint)].append(model)

        if self._client is not None:
            return [
                await self._inspect_endpoint(endpoint, configured_models, self._client)
                for endpoint, configured_models in models_by_endpoint.items()
            ]

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            return [
                await self._inspect_endpoint(endpoint, configured_models, client)
                for endpoint, configured_models in models_by_endpoint.items()
            ]

    async def discover_models(self, models: list[ModelDescriptor]) -> list[ModelDescriptor]:
        """Return chat-capable installed Ollama models absent from the static registry."""
        known_ids = {model.model_id for model in models if model.provider == "ollama"}
        discovered: list[ModelDescriptor] = []
        for status in await self.inspect(models):
            for model_id in status.installed_models:
                if model_id in known_ids or _is_embedding_model(model_id):
                    continue
                discovered.append(_descriptor_for_installed_model(model_id, status.endpoint))
        return discovered

    async def _inspect_endpoint(
        self,
        endpoint: str,
        configured_models: list[ModelDescriptor],
        client: httpx.AsyncClient,
    ) -> OllamaRuntimeStatus:
        try:
            response = await client.get(_tags_url(endpoint))
            response.raise_for_status()
            payload = response.json()
            installed_models = {
                item[name_field]
                for item in payload.get("models", [])
                if isinstance(item, dict)
                for name_field in ("name", "model")
                if isinstance(item.get(name_field), str)
            }
        except (httpx.HTTPError, ValueError) as exc:
            return OllamaRuntimeStatus(
                endpoint=endpoint,
                reachable=False,
                configured_models=[
                    LocalModelReadiness(
                        model_key=model.key,
                        model_id=model.model_id,
                        installed=False,
                    )
                    for model in configured_models
                ],
                installed_models=[],
                detail=f"Could not reach Ollama: {exc}",
            )

        readiness = [
            LocalModelReadiness(
                model_key=model.key,
                model_id=model.model_id,
                installed=model.model_id in installed_models,
            )
            for model in configured_models
        ]
        missing_models = [model.model_id for model in readiness if not model.installed]
        return OllamaRuntimeStatus(
            endpoint=endpoint,
            reachable=True,
            configured_models=readiness,
            installed_models=sorted(installed_models),
            detail=(
                f"Missing configured models: {', '.join(missing_models)}"
                if missing_models
                else None
            ),
        )


def _tags_url(endpoint: str) -> str:
    parsed = urlsplit(endpoint)
    return urlunsplit((parsed.scheme, parsed.netloc, "/api/tags", "", ""))


def _is_embedding_model(model_id: str) -> bool:
    name = model_id.lower()
    return any(token in name for token in ("embed", "bge-", "nomic-embed"))


def _descriptor_for_installed_model(model_id: str, endpoint: str) -> ModelDescriptor:
    name = model_id.lower()
    coder = any(token in name for token in ("coder", "code", "starcoder", "codellama"))
    reasoning = any(token in name for token in ("r1", "reason", "qwq", "deepseek"))
    capabilities = {"general_qa", "summarization", "classification"}
    affinities = {"general_qa": 0.85, "summarization": 0.8, "classification": 0.8}
    if coder:
        capabilities.update({"code_generation", "reasoning", "structured_output"})
        affinities.update({"coding": 0.95, "extraction": 0.85, "math": 0.8})
    if reasoning:
        capabilities.add("reasoning")
        affinities.update({"math": 0.9, "research": 0.8, "coding": 0.75})
    size_match = next(
        (int(value) for value in ("1", "3", "7", "8", "14", "32", "70") if f"{value}b" in name),
        7,
    )
    quality_tier = 1 if size_match <= 3 else 2 if size_match <= 8 else 3
    key = "ollama-" + "-".join(part for part in name.replace(":", "-").split() if part)
    return ModelDescriptor(
        key=key,
        provider="ollama",
        display_name=f"{model_id} (Ollama discovered)",
        model_id=model_id,
        endpoint=HttpUrl(endpoint),
        quality_tier=quality_tier,
        supports_structured_output=coder,
        capabilities=capabilities,
        task_affinities=affinities,
        max_context_tokens=32768,
        pricing={"input_cost_per_1k_tokens": 0.0, "output_cost_per_1k_tokens": 0.0},
        latency={"p50_ms": 5000, "p95_ms": 300000},
    )
