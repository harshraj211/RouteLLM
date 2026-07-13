# RouteLLM

**A local-first, OpenAI-compatible gateway that routes each request to the most suitable LLM.**

RouteLLM sits between an application and multiple language models. It analyzes the request,
filters models by capability, latency, credentials, and budget, ranks the eligible candidates,
and forwards the request to the best available option.

Local Ollama models are used by default, so RouteLLM can serve requests without per-token API
charges. OpenAI and Anthropic/Claude providers can be enabled through the interactive setup
wizard when cloud models are required.

## Highlights

- Local-first routing through Ollama's OpenAI-compatible API
- Automatic discovery of installed Ollama chat models
- Semantic routing for general Q&A, coding, math, research, extraction, legal, and creative tasks
- Optional OpenAI and Anthropic/Claude routing
- OpenAI-compatible `/v1/chat/completions` endpoint
- Simple terminal client: `routellm "your question"`
- Cost, latency, capability, health, and budget-aware candidate ranking
- Response evaluation, retry, failover, and escalation tracking
- Local analytics dashboard and Prometheus metrics
- Auditable routing decisions with estimated and actual usage

## How It Works

```text
Client, application, or agent
             |
             v
       RouteLLM gateway
             |
             +--> analyze intent and complexity
             +--> discover available models
             +--> apply capability, latency, credential, and budget policy
             +--> rank eligible candidates
             +--> execute, evaluate, and fail over when necessary
             |
             v
  Ollama / OpenAI / Anthropic
```

RouteLLM does not always select the largest model. A short general question can use a fast 3B
model, while a code-generation request can use a coder model. More capable or paid models are
considered only when they are enabled, available, and appropriate for the request.

## Prerequisites

- Python 3.12 or newer
- Git
- Ollama for local inference (recommended)
- An OpenAI or Anthropic API key only if that provider is enabled

Verify Python before continuing:

```powershell
python --version
```

On Windows, if `python` is unavailable but the Python launcher is installed, use `py` in place
of `python` in the commands below.

## Quick Start

### 1. Clone the repository

```powershell
git clone https://github.com/harshraj211/RouteLLM.git
cd RouteLLM
```

### 2. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install RouteLLM

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### 4. Install local models

Install [Ollama](https://ollama.com/) and pull the default models:

```powershell
ollama pull qwen2.5:3b
ollama pull qwen2.5-coder:7b
```

RouteLLM also discovers other installed Ollama chat models automatically. Check them with:

```powershell
ollama list
```

### 5. Configure providers

Run the interactive setup wizard:

```powershell
routellm setup
```

The wizard asks whether to enable:

- Ollama
- Anthropic/Claude API
- OpenAI API

API keys are entered without being echoed and are saved to the local `.env` file. The `.env`
file is ignored by Git and must never be committed or shared.

For an Ollama-only installation, accept the defaults:

```text
Enable Ollama? [Y/n]: Y
Enable Anthropic/Claude API? [y/N]: N
Enable OpenAI API? [y/N]: N
Ollama fast model [qwen2.5:3b]:
Ollama coder model [qwen2.5-coder:7b]:
```

### 6. Start the gateway

```powershell
python -m uvicorn routellm.main:app --reload
```

The local services are now available at:

| Service | URL |
| --- | --- |
| Gateway | `http://localhost:8000` |
| Interactive API documentation | `http://localhost:8000/docs` |
| Control Room dashboard | `http://localhost:8000/dashboard` |
| OpenAI-compatible API base | `http://localhost:8000/v1` |

Restart the gateway after changing `.env` or running `routellm setup` again.

## Command-Line Usage

With the virtual environment active and the gateway running:

```powershell
routellm "Explain Python decorators simply"
routellm "Write a Python function for binary search and add unit tests"
```

RouteLLM prints the selected model, latency, cost, and answer:

```text
Model: local-small (qwen2.5:3b)
Time: 1979 ms | Cost: $0.0

<model response>
```

List every model installed in Ollama:

```powershell
routellm models
```

Increase the response limit when a longer answer is needed:

```powershell
routellm --max-output-tokens 768 "Write a Python sorting module with tests"
```

If the virtual environment is not active, use the executable directly on Windows:

```powershell
.\.venv\Scripts\routellm.exe "Your question"
```

## API Usage

### Native routing endpoint

```powershell
$body = @{
    tenant_id = "demo"
    workflow_id = "terminal-test"
    task_type = "qa"
    messages = @(
        @{ role = "user"; content = "Write a Python binary search function with tests" }
    )
    max_budget_usd = 1
    latency_slo_ms = 300000
    max_output_tokens = 512
} | ConvertTo-Json -Depth 5

Invoke-RestMethod `
    -Method Post `
    -Uri "http://localhost:8000/v1/route" `
    -ContentType "application/json" `
    -Body $body
```

The response includes the selected model and provider, reason codes, token usage, latency,
cost, execution attempts, escalation path, and generated output.

### OpenAI-compatible endpoint

Install the OpenAI Python client if your application uses it:

```powershell
python -m pip install openai
```

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="local-not-used",
)

response = client.chat.completions.create(
    model="routellm-auto",
    messages=[
        {"role": "user", "content": "Explain binary search with an example."}
    ],
)

print(response.choices[0].message.content)
```

## Routing Behavior

The default local profiles are optimized for two common workload classes:

| Request | Typical local choice | Why |
| --- | --- | --- |
| Short questions, classification, summaries | `qwen2.5:3b` | Faster and lighter |
| Code generation, structured output, complex analysis | `qwen2.5-coder:7b` | Stronger coding and reasoning capability |

Additional Ollama chat models are discovered and added to the candidate set automatically.
RouteLLM infers initial capability hints from model names; explicit profiles in
[`config/models.yaml`](config/models.yaml) remain the best way to provide accurate capabilities,
context limits, and task affinities.

Cloud profiles use ranked specialist preferences when enabled:

| Intent | Preferred cloud specialist |
| --- | --- |
| Coding and repository work | OpenAI Codex profile |
| Research and source comparison | Gemini profile |
| Legal or contract review | Claude profile |
| Creative writing | Claude profile |
| Math and deep reasoning | Premium reasoning profile |
| Current news and trends | Grok profile |

Preferences are not hard locks. Credentials, model health, request budget, capabilities,
latency targets, and fallback availability are evaluated before execution.

## Configuration

Common environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `ROUTELLM_INFERENCE_MODE` | `mock` | Use `live` for real provider calls |
| `ROUTELLM_ENABLE_CLOUD_MODELS` | `false` | Allow configured cloud profiles |
| `ROUTELLM_OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama API endpoint |
| `ROUTELLM_OLLAMA_FAST_MODEL` | `qwen2.5:3b` | Preferred lightweight local model |
| `ROUTELLM_OLLAMA_CODER_MODEL` | `qwen2.5-coder:7b` | Preferred local coding model |
| `ROUTELLM_OLLAMA_INFERENCE_TIMEOUT_SECONDS` | `300` | Local inference timeout |
| `ROUTELLM_INFERENCE_MAX_RETRIES` | `1` | Retry count for retryable failures |
| `ROUTELLM_MODEL_REGISTRY_PATH` | `config/models.yaml` | Model profile registry |
| `OPENAI_API_KEY` | unset | OpenAI credential |
| `ANTHROPIC_API_KEY` | unset | Anthropic credential |

See [`.env.example`](.env.example) for the complete example configuration.

## Observability and Control Room

Open `http://localhost:8000/dashboard` to view:

- Request volume and local-route share
- Model usage and recent decisions
- Estimated cloud-baseline spend and savings
- Latency and escalation activity

Useful endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /v1/healthz` | Gateway health |
| `GET /v1/runtime/ollama` | Ollama reachability and installed models |
| `GET /v1/models` | Configured model profiles |
| `GET /v1/models/health` | Model health summary |
| `GET /v1/decisions` | Routing decision history |
| `GET /v1/analytics/summary` | Usage and savings summary |
| `GET /v1/analytics/decisions` | Analytics decision data |
| `GET /v1/metrics` | Prometheus metrics |
| `POST /v1/replay/compare-default` | Compare routing with the cloud baseline |

## Agent and MCP Integration

RouteLLM can control inference only when an application sends its model requests through the
RouteLLM gateway. It cannot replace or switch the built-in subscription model inside Codex,
Claude Cowork, or another hosted agent interface.

An optional MCP task-policy companion is available for compatible hosts:

```toml
[mcp_servers.routellm]
command = "routellm-mcp"
```

See [the agent-native setup guide](docs/AGENT_NATIVE_SETUP.md) for details.

## Development and Verification

Run the test suite and static checks from the repository root:

```powershell
python -m pytest
ruff check src tests
```

Run the API locally:

```powershell
python -m uvicorn routellm.main:app --reload
```

## Security Notes

- Never commit `.env`, API keys, or provider credentials.
- Rotate a key immediately if it appears in a terminal recording, screenshot, issue, or commit.
- Local inference has no provider token charge, but it consumes local compute, memory, and power.
- Cloud models can incur real charges; use request budgets and review routing decisions.
- Run RouteLLM behind authentication and TLS before exposing it outside a trusted local network.

## Current Limitations

- Capability metadata for automatically discovered Ollama models is inferred from model names.
- Local response speed depends heavily on model size, hardware, and whether the model is loaded.
- Provider credentials are stored in the local `.env` file by the current setup wizard.
- RouteLLM routes API traffic; it does not change models inside third-party desktop subscriptions.

## Documentation

- [Agent-native MCP setup](docs/AGENT_NATIVE_SETUP.md)
- [Agent-native architecture decision](docs/adr/ADR-002-agent-native-control-plane.md)
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md)

## License

This project is licensed under the MIT License.
