# RouteLLM

RouteLLM is an open-source cost-aware routing layer for LLM and agent workloads.

It helps teams send each request to the cheapest model that can still satisfy quality, latency, and reliability requirements. The system is designed for local `vLLM` deployments, hosted model providers, and multi-step agent workflows that need budget-aware escalation.

## Vision

RouteLLM acts like a control plane for inference:

- classify the request
- estimate cost and latency
- choose the best model
- validate the response
- escalate only when needed
- log every decision for audits and optimization

## Planned Capabilities

- policy-driven model routing
- cost estimation and budget enforcement
- confidence-gated early exit
- local `vLLM` and hosted provider adapters
- Prometheus metrics and OpenTelemetry traces
- replayable evaluation harnesses
- Grafana dashboards for cost and latency analysis

## Current Status

The repository is being built from the ground up. The first milestone is a working FastAPI router with model registry, policy engine, and route decision logging.

## Quick Start

```bash
python -m pip install -e ".[dev]"
uvicorn routellm.main:app --reload
```

Open:

- `http://localhost:8000/docs`
- `http://localhost:8000/v1/metrics`

By default, RouteLLM runs in explicit mock mode so local development and tests do not make
paid provider calls. To call real OpenAI-compatible endpoints, copy `.env.example` to `.env`
and configure:

```bash
ROUTELLM_INFERENCE_MODE=live
ROUTELLM_HOSTED_BASE_URL=https://api.openai.com/v1
ROUTELLM_HOSTED_MODEL=gpt-5-mini
OPENAI_API_KEY=your-api-key
```

Local vLLM servers use the same Chat Completions adapter and do not require an API key by
default. Their base URLs and upstream model IDs are configured with the
`ROUTELLM_LOCAL_SMALL_*` and `ROUTELLM_LOCAL_MEDIUM_*` variables in `.env.example`.

Live inference retries safe transient failures with bounded exponential backoff. If retries
are exhausted, RouteLLM moves to the next ranked model that still fits the request budget.
Rate limits, connection failures, and explicit upstream `5xx` responses are considered safe
to retry. Read/write timeouts and ambiguous network failures stop immediately because the
provider may already have generated the response. Configure this behavior with
`ROUTELLM_INFERENCE_MAX_RETRIES` and `ROUTELLM_INFERENCE_RETRY_BACKOFF_SECONDS`.

## OpenAI-Compatible Client API

Point an OpenAI-compatible client at RouteLLM's `/v1` base URL and use
`routellm-auto` as the model:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="unused",
)
completion = client.chat.completions.create(
    model="routellm-auto",
    messages=[{"role": "user", "content": "Explain this error"}],
)
print(completion.choices[0].message.content)
```

Use a RouteLLM model key such as `local-small`, or a configured upstream model ID, to pin
one model instead of routing automatically. Optional routing controls are accepted through
the following headers:

- `X-RouteLLM-Tenant-Id`
- `X-RouteLLM-Workflow-Id`
- `X-RouteLLM-Task-Type`
- `X-RouteLLM-Max-Budget-USD`
- `X-RouteLLM-Latency-SLO-MS`
- `X-Request-Id`

The endpoint supports standard text messages, JSON-object responses, common sampling
parameters, token limits, and SSE response framing. Streaming currently waits for the full
upstream response and then emits compatible chunks; token-by-token proxy streaming and tool
calling are not implemented yet.

## Model Registry

Models are loaded from `config/models.yaml`. Registry entries contain routing capabilities,
pricing, latency estimates, provider endpoints, and the environment-variable name that holds
the provider credential. `${VARIABLE:-default}` values are expanded when the file loads. A
model with `enabled: false` remains visible through the administration API but is excluded
from routing.

The model APIs support runtime administration and persist changes atomically:

- `GET /v1/models` and `GET /v1/models/{key}`
- `POST /v1/models`
- `PUT /v1/models/{key}`
- `DELETE /v1/models/{key}`
- `POST /v1/models/reload`

Set `ROUTELLM_MODEL_REGISTRY_WRITES_ENABLED=false` when registry mutations should be disabled.
Public deployments should keep writes disabled until API authentication is configured.

Native provider names currently supported by registry entries are `anthropic` and `gemini`,
in addition to `vllm` and generic OpenAI-compatible `hosted` endpoints. Anthropic entries use
an endpoint such as `https://api.anthropic.com/v1` and `ANTHROPIC_API_KEY`; Gemini entries use
`https://generativelanguage.googleapis.com/v1beta` and `GEMINI_API_KEY`.

The default registry also includes disabled Gemini 3.5 Flash and Grok 4.5 entries. Grok uses
xAI's OpenAI-compatible endpoint and `XAI_API_KEY`. To activate either model, first place a
new provider key in the ignored `.env` file, then change its registry entry to `enabled: true`
or update it through `PUT /v1/models/{key}`. Never commit provider keys to the registry.

To boot the local platform stack:

```bash
docker compose up
```

## Repository Structure

```text
src/
  routellm/
tests/
docs/
infra/
```

## License

MIT
