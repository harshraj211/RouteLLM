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

RouteLLM will operate as a local-first inference gateway with an OpenAI-compatible HTTP API
as its primary integration surface. An MCP server remains an optional companion for task
guidance in compatible agent hosts.

The inference gateway will:

- classify the requested task locally and deterministically;
- route requests to configured local models before paid provider profiles;
- expose an OpenAI-compatible client endpoint;
- record selection, cost, latency, retries, and fallback decisions;
- require an explicit configuration change before a paid cloud model is eligible.

The default inference target is a local Ollama-compatible endpoint. This avoids per-token
provider API charges, while still making the local hardware cost visible to the user.

The MCP server returns `current_agent` task guidance and does not claim to switch the host
application's internal model. Codex, Claude Cowork, and similar subscription products remain
separate from the gateway unless they expose a supported custom-inference configuration.

## Consequences

Benefits:

- individual users can run the default gateway without provider API keys;
- simple requests can be served by local models instead of consuming cloud credits;
- routing decisions stay local, explainable, and testable;
- OpenAI-compatible applications can use one local gateway endpoint;
- advanced users can still opt into a local model runtime or provider-backed proxy later.

Trade-offs:

- RouteLLM cannot redirect a host application's internal subscription model through MCP;
- model-specific cost calculations are unavailable in the zero-key path;
- host integrations need clear, per-client setup guides rather than an assumption of feature
  parity.
