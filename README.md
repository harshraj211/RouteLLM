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
