# RouteLLM Implementation Plan

## Current Direction

RouteLLM is being built as an open-source cost-aware router for LLM and agent workloads. The repository is focused on production-style primitives first:

- request analysis
- policy-based routing
- explainable model scoring
- persistent decision logs
- Prometheus metrics
- OpenTelemetry tracing bootstrap

## Near-Term Roadmap

### Milestone 1

- working FastAPI API
- in-memory model registry
- heuristic request analyzer
- policy engine
- candidate scoring
- route decision persistence

### Milestone 2

- provider adapter interface
- actual hosted provider integration
- local `vLLM` adapter
- budget reservation and settlement
- structured route reason codes

### Milestone 3

- LangGraph-based escalation workflow
- replay evaluation harness
- Grafana dashboards
- richer policy versioning
- tenant-level budget controls

## Design Principles

1. Prefer explainable routing over black-box automation.
2. Treat local inference as low-cost, not free.
3. Measure every decision with cost and latency telemetry.
4. Build for replay and auditability from the start.
