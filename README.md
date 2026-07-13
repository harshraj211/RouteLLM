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

The current milestone provides a working FastAPI router with semantic request analysis, a
model registry, capability-aware ranking, budget enforcement, provider failover, and route
decision logging.

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

### Semantic auto-routing

For `routellm-auto`, RouteLLM infers an intent from the declared task type and message text.
Current intents include general QA, coding, math, research, legal, extraction, creative
writing, summarization, and classification. It then:

1. filters candidates using latency, risk, response-format, and capability requirements;
2. scores the remaining models using task affinity, capability coverage, quality, health,
   latency, complexity, and estimated cost;
3. records an explainable reason such as `SEMANTIC_INTENT_CODING` in the route decision.

Each registry model can declare `capabilities` and `task_affinities`. Affinity values range
from `0.0` to `1.0`; larger values make a model more likely to handle that intent while the
budget and latency constraints remain in force. The initial intent classifier is deterministic
and keyword-based, making its routing decisions fast and testable without another model call.

The default external provider profiles currently route specialized prompts as follows:

- coding and repository work: OpenAI GPT-5.3 Codex
- research and long-context analysis: Gemini 3.5 Flash
- nuanced creative writing and legal analysis: Claude Sonnet 5
- other configured workloads and failover: Grok 4.5 and the general OpenAI model

These are API model targets. Codex, Claude Cowork, and provider chat applications themselves
cannot be called as inference endpoints. The `/v1/route` response exposes both
`selected_model` and `selected_provider`, along with a provider reason code.

## Model Registry

Models are loaded from `config/models.yaml`. Registry entries contain routing capabilities,
per-intent affinities, pricing, latency estimates, provider endpoints, and the
environment-variable name that holds the provider credential. `${VARIABLE:-default}` values
are expanded when the file loads. A model with `enabled: false` remains visible through the
administration API but is excluded from routing.

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

The default registry includes Gemini 3.5 Flash, Claude Sonnet 5, OpenAI GPT-5.3 Codex, and
Grok 4.5. In live mode, a credentialed model is automatically excluded from routing when its
named environment variable is missing. Add provider keys only to the ignored `.env` file;
never commit keys to the registry. Mock mode keeps all enabled models available so provider
selection can be tested without making paid calls.

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
