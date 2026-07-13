# Agent-Native Setup

RouteLLM's default mode is a local MCP server. It makes a task policy decision without
calling OpenAI, Anthropic, Google, or any other paid inference API.

The server tells the active agent how deeply to work, what to verify, and which tools are
appropriate. The active host remains responsible for generating the answer with the model
available in that host.

## Install from source

```powershell
git clone https://github.com/harshraj211/RouteLLM.git
cd RouteLLM
python -m pip install -e .
```

This installs the `routellm-mcp` command. It runs over standard input/output, so users do
not start a web server and do not configure an API key for the default path.

## Codex

Add the following server entry to the Codex configuration used by the workspace or user:

```toml
[mcp_servers.routellm]
command = "routellm-mcp"
```

Restart Codex or begin a new task after changing MCP configuration. RouteLLM exposes two
tools:

- `route_task`: classifies a task and returns task mode, verification level, tool guidance,
  and the host boundary.
- `host_capabilities`: reports exactly what the host integration can and cannot control.

Codex decides whether to call the tool. RouteLLM cannot force Codex to change its selected
model from an MCP tool.

## Claude Cowork and Antigravity

Use the same `routellm-mcp` stdio command in any MCP configuration surface that those
products expose. Select the matching `host` parameter when calling `route_task`:

```text
codex | claude_cowork | antigravity | generic_mcp
```

Their ability to install MCP servers and switch models is controlled by each product's
version, plan, and workspace policy. RouteLLM therefore reports `model_control:
host_managed` instead of claiming unsupported automatic model switching.

## Example policy response

For `Fix a Python regression and add a test`, `route_task` returns a response shaped like:

```json
{
  "intent": "coding",
  "task_mode": "standard",
  "execution_target": "current_agent",
  "model_control": "host_managed",
  "verification_level": "strict",
  "suggested_tools": ["repository_search", "test_runner"],
  "reason_codes": ["LOCAL_DETERMINISTIC_CLASSIFICATION", "NO_PROVIDER_API_KEY_REQUIRED"]
}
```

The current agent should use this as execution guidance: inspect the repository, make the
change, and run tests. No paid model routing occurs in this default flow.

## Optional advanced mode

The existing FastAPI proxy and provider adapters remain in the repository for users who own
local inference hardware or intentionally bring API credentials. They are not needed for MCP
mode and are not installed or configured by these setup steps.
