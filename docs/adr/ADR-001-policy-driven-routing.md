# ADR-001: Start With Policy-Driven Routing

## Status

Accepted

## Context

The first version of RouteLLM needs to be easy to understand, debug, and benchmark. A learned routing policy would add complexity before the system has enough production data.

## Decision

RouteLLM will start with explicit policy filters and a weighted heuristic scorer.

## Consequences

- easier interview and OSS adoption story
- simpler observability
- faster iteration on routing behavior
- future migration path toward adaptive policies once replay data exists
