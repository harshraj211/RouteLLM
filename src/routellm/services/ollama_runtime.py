"""Readiness checks for local Ollama endpoints."""

from collections import defaultdict
from urllib.parse import urlsplit, urlunsplit

import httpx

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
