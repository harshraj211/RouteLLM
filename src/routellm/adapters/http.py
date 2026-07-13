from time import perf_counter
from typing import Any

import httpx

from routellm.adapters.base import InferenceAdapterError
from routellm.schemas.models import ModelDescriptor


async def post_json(
    client: httpx.AsyncClient,
    *,
    endpoint: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    model: ModelDescriptor,
) -> tuple[dict[str, Any], int]:
    started_at = perf_counter()
    try:
        response = await client.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
    except (httpx.ConnectTimeout, httpx.PoolTimeout) as exc:
        raise InferenceAdapterError(
            "The upstream model connection timed out.",
            model_key=model.key,
            retryable=True,
            reason_code="UPSTREAM_CONNECTION_TIMEOUT",
        ) from exc
    except (httpx.ReadTimeout, httpx.WriteTimeout) as exc:
        raise InferenceAdapterError(
            "The upstream model timed out after transmission may have started.",
            model_key=model.key,
            retryable=False,
            reason_code="UPSTREAM_UNCERTAIN_TIMEOUT",
        ) from exc
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        raise InferenceAdapterError(
            f"The upstream model returned HTTP {status_code}.",
            model_key=model.key,
            status_code=status_code,
            retryable=status_code == 429 or status_code >= 500,
            reason_code=(
                "UPSTREAM_RATE_LIMIT"
                if status_code == 429
                else "UPSTREAM_SERVER_ERROR"
                if status_code >= 500
                else "UPSTREAM_CLIENT_ERROR"
            ),
        ) from exc
    except httpx.ConnectError as exc:
        raise InferenceAdapterError(
            "The upstream model could not be reached.",
            model_key=model.key,
            retryable=True,
            reason_code="UPSTREAM_CONNECTION_ERROR",
        ) from exc
    except httpx.RequestError as exc:
        raise InferenceAdapterError(
            "The upstream connection failed after transmission may have started.",
            model_key=model.key,
            retryable=False,
            reason_code="UPSTREAM_UNCERTAIN_NETWORK_ERROR",
        ) from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise InferenceAdapterError(
            "The upstream model returned invalid JSON.",
            model_key=model.key,
            reason_code="UPSTREAM_INVALID_RESPONSE",
        ) from exc
    if not isinstance(data, dict):
        raise InferenceAdapterError(
            "The upstream model returned an invalid response object.",
            model_key=model.key,
            reason_code="UPSTREAM_INVALID_RESPONSE",
        )
    return data, round((perf_counter() - started_at) * 1000)
