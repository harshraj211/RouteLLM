# RouteLLM

RouteLLM is an open-source, local-first control plane for AI coding agents.

It helps Codex, Claude Cowork, Antigravity, and other MCP-capable hosts decide **how** to
handle a task: quick vs. deep work, what to verify, and which tools to use. The default
workflow uses the model already available in the user's agent subscription. No provider API
key is required.

## What It Does

```text
User task
  -> RouteLLM MCP tool classifies it locally
  -> returns an explainable execution policy
  -> active agent performs the work with its existing model entitlement
```

For example, a Python bug fix is classified as coding and receives `standard` mode, strict
verification, repository search, and test-runner guidance. A high-risk research request gets
`deep` mode and external-research guidance.

## What It Does Not Claim

RouteLLM does not silently switch the internal model used by Codex, Claude Cowork, or
Antigravity. MCP gives an agent tools; it does not give a tool authority over the host's
model picker or subscription. RouteLLM makes that boundary visible with
`model_control: host_managed` in every recommendation.

## Quick Start

```powershell
git clone https://github.com/harshraj211/RouteLLM.git
cd RouteLLM
python -m pip install -e .
```

Add RouteLLM to an MCP-capable host using the `routellm-mcp` command. For Codex:

```toml
[mcp_servers.routellm]
command = "routellm-mcp"
```

See [the agent-native setup guide](docs/AGENT_NATIVE_SETUP.md) for host guidance and an
example tool response.

## MCP Tools

- `route_task`: returns a local task policy without calling a provider API.
- `host_capabilities`: explains the supported integration boundary for a host.

Supported host labels are `codex`, `claude_cowork`, `antigravity`, and `generic_mcp`.

## Local-First Policy

The default router is deterministic and runs in-process. It does not transmit prompts to a
model provider, require API credentials, or estimate a paid provider bill. Its policy
includes:

- task intent
- task depth: `quick`, `standard`, or `deep`
- verification level
- suggested tool categories
- explainable reason codes

## Advanced Inference Proxy

The repository still includes the original FastAPI/OpenAI-compatible proxy, local vLLM
adapters, provider failover, budget enforcement, routing logs, and evaluation harness. Those
components are now optional advanced mode for users who deliberately run local models or
bring provider API credentials.

```powershell
uvicorn routellm.main:app --reload
```

The proxy defaults to mock mode. Review `.env.example` before enabling live inference.

## Development

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
