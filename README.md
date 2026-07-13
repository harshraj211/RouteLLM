# RouteLLM

RouteLLM is an open-source, local-first inference gateway for agent and LLM applications.

Point an OpenAI-compatible client at RouteLLM, use `routellm-auto`, and RouteLLM chooses the
least expensive model that satisfies the task policy. The default configuration routes to
local Ollama models, so simple and medium-complexity work uses no provider API credits.

## How It Saves Credits

```text
Application or agent runtime
  -> RouteLLM /v1/chat/completions
  -> local task analysis and cost-aware policy
  -> local Ollama model by default
  -> optional cloud fallback only when you enable it
```

Local inference is not physically free: it consumes the user's machine, power, and memory.
It is free of per-token provider API charges. The shipped registry disables cloud models by
default, so RouteLLM cannot accidentally spend OpenAI, Anthropic, Google, or xAI credits.

## Quick Start: Local Gateway

1. Install [Ollama](https://ollama.com/), then download the two default local models:

   ```powershell
   ollama pull qwen2.5:3b
   ollama pull qwen2.5-coder:7b
   ```

2. Install and configure RouteLLM:

   ```powershell
   git clone https://github.com/harshraj211/RouteLLM.git
   cd RouteLLM
   python -m pip install -e ".[dev]"
   Copy-Item .env.example .env
   ```

3. Start the local gateway:

   ```powershell
   uvicorn routellm.main:app --reload
   ```

4. Point an OpenAI-compatible application at `http://localhost:8000/v1`:

   ```python
   from openai import OpenAI

   client = OpenAI(base_url="http://localhost:8000/v1", api_key="local-not-used")
   response = client.chat.completions.create(
       model="routellm-auto",
       messages=[{"role": "user", "content": "Fix this Python function and add tests."}],
   )
   print(response.choices[0].message.content)
   ```

For that coding request, RouteLLM selects `qwen2.5-coder:7b` through the local Ollama API.
Use `http://localhost:8000/docs` to inspect the gateway API and `GET /v1/decisions` to audit
model choices and estimated/actual usage.

## Default Routing Policy

| Task type | Default model | Provider cost |
| --- | --- | --- |
| General Q&A, classification, summaries, creative text | `qwen2.5:3b` | $0 API cost |
| Code, structured output, math, research analysis, high-risk work | `qwen2.5-coder:7b` | $0 API cost |

The actual models and endpoints are configurable in [models.yaml](config/models.yaml). Use
the `ROUTELLM_OLLAMA_*` variables in `.env` if your machine has different local models.

## Optional Cloud Escalation

Cloud profiles are retained in [models.yaml](config/models.yaml) but ship with
`enabled: false`. To allow a paid provider as a fallback, deliberately:

1. Add its API key to the ignored `.env` file.
2. Change only that model's `enabled` value to `true`.
3. Set a per-request budget with `X-RouteLLM-Max-Budget-USD`.

This makes every paid path opt-in and auditable. RouteLLM tracks selection, estimated cost,
actual reported usage, latency, retries, and failover in its decision log.

## Codex, Claude, and Other Agents

The gateway can control inference only for clients that send their model requests through it.
Codex's own built-in subscription model cannot currently be redirected or switched by an MCP
tool. RouteLLM therefore provides an optional MCP task-policy companion, but that companion
does not save Codex subscription credits by itself.

Use the MCP server when you want local planning guidance in a compatible host:

```toml
[mcp_servers.routellm]
command = "routellm-mcp"
```

See [the agent-native setup guide](docs/AGENT_NATIVE_SETUP.md) for that optional integration.

## Verification

```powershell
python -m pytest
ruff check .
```

## Documentation

- [Agent-native MCP setup](docs/AGENT_NATIVE_SETUP.md)
- [Agent-native architecture decision](docs/adr/ADR-002-agent-native-control-plane.md)
- [Original implementation plan](docs/IMPLEMENTATION_PLAN.md)

## License

MIT
