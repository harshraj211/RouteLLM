# ADR-002: Agent-Native Control Plane

## Status

Accepted

## Context

RouteLLM originally operated as an OpenAI-compatible inference proxy. It selected among
provider API models and then made the inference call. That model requires users to hold API
credentials and pay provider usage charges.

The primary audience is now individual developers who already use an agent product such as
Codex, Claude Cowork, or Antigravity. They should not need to configure separate provider
API keys just to receive task-aware routing guidance.

MCP is a tool protocol, not a universal model-switching protocol. An MCP server cannot
silently replace the model selected inside a host application. The host agent must choose to
call a routing tool, and the host controls whether it can change its own model or reasoning
settings.

## Decision

RouteLLM will become an agent-native control plane with an MCP server as its primary
integration surface.

The MCP server will:

- classify the requested task locally and deterministically;
- return an explainable execution policy for the active agent;
- recommend a task mode, verification level, and optional local-model fallback;
- expose no credential requirement for its default path;
- record the platform capability boundary in every recommendation.

The default execution target is `current_agent`. This means Codex, Claude Cowork, or
Antigravity performs the task using the model and entitlement already available in that
application. RouteLLM guides the work but does not claim to switch the host application's
model.

The existing HTTP inference proxy remains available as an optional advanced deployment mode.
It is no longer the default product story or the only way to use RouteLLM.

## Consequences

Benefits:

- individual users can install and use the default workflow without API keys;
- routing decisions stay local, explainable, and testable;
- one server can be configured in any MCP-capable agent host;
- advanced users can still opt into a local model runtime or provider-backed proxy later.

Trade-offs:

- RouteLLM cannot force a host application to switch its own subscription model;
- model-specific cost calculations are unavailable in the zero-key path;
- host integrations need clear, per-client setup guides rather than an assumption of feature
  parity.
