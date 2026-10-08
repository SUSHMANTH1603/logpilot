# ADR-004: Log Ingestion Adapter Pattern

**Status:** Accepted
**Date:** 2026-10-08

## Context

LogPilot must ingest logs from multiple sources. V1 targets four sources (manual input, local files, Docker logs, OpenTelemetry), but the architecture must support future adapters for Kubernetes, Loki, ELK, CloudWatch, Datadog, and other sources without requiring changes to the core ingestion pipeline.

Tightly coupling the ingestion pipeline to any specific log source would make it difficult and risky to add new sources.

## Decision

Use an **adapter abstraction** for log ingestion.

Each log source is implemented as an adapter that conforms to a common interface. The core ingestion pipeline (parsing, normalization, template extraction, feature extraction) operates on a normalized log representation regardless of the source.

```
Log Source Adapters              Core Pipeline
┌──────────────────┐
│ Manual Input     │──┐
├──────────────────┤  │
│ Local File       │──┤         ┌──────────────────────────────────┐
├──────────────────┤  ├────────►│ Parser → Normalizer → Template  │
│ Docker Logs      │──┤         │ Extraction → Feature Extraction │
├──────────────────┤  │         └──────────────────────────────────┘
│ OpenTelemetry    │──┘
├──────────────────┤
│ Future: K8s      │ (future)
│ Future: Loki     │ (future)
│ Future: ELK      │ (future)
│ Future: CW       │ (future)
│ Future: Datadog  │ (future)
└──────────────────┘
```

### V1 Adapters

1. **Manual input**: User pastes or uploads log content directly
2. **Local file logs**: Reads log files from the local filesystem
3. **Docker logs**: Collects logs from Docker containers
4. **OpenTelemetry**: Receives logs via OpenTelemetry protocol

### Adapter Contract

Each adapter must produce a normalized log representation that the core pipeline can process. The specific schema of the normalized representation is **TBD** — it will be defined as a Pydantic model in `packages/schemas/` during implementation.

## Consequences

### Positive

- Adding a new log source requires only implementing a new adapter, not modifying the core pipeline
- Each adapter can be developed and tested independently
- Clear separation between source-specific concerns and core processing

### Negative

- The normalized representation must be general enough to capture information from diverse sources, which may lead to some loss of source-specific detail
- Adapter interface design requires careful thought to avoid being too restrictive or too permissive

### Neutral

- The adapter discovery/registration mechanism (plugin system, configuration, etc.) is **TBD**
- Whether adapters run in the agent, the backend, or both depends on the source type and is an implementation decision

## Alternatives Considered

1. **Hardcoded source integrations**: Rejected. Each new source would require modifying core pipeline code, violating the open-closed principle.

2. **Generic webhook-only ingestion**: Rejected. Would push all source-specific logic to external systems and limit LogPilot's ability to actively collect logs.

3. **Adapter pattern with common interface**: Selected. Balances extensibility with implementation simplicity.
