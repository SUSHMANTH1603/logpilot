# ADR-001: Modular Monolith Architecture

**Status:** Accepted
**Date:** 2026-10-08

## Context

LogPilot requires a backend architecture that supports multiple concerns: API serving, log ingestion, anomaly detection, incident management, repository intelligence, RAG, RCA, and LLM integration.

The system needs to be maintainable by a small team, testable, and deployable without excessive operational complexity. At the same time, it must support clean module boundaries and avoid the tight coupling typical of naive monoliths.

## Decision

Use a **modular monolith** architecture for the backend.

The FastAPI application (`apps/api/`) is organized as a single deployable unit composed of well-defined domain modules with explicit boundaries. Domain logic is structured into modules that can be reasoned about independently.

Async workers (`workers/`) run as **separate execution processes** but share domain/business logic with the API. Domain logic must not be duplicated between the API and workers — shared logic resides in common packages or domain modules that both the API and workers import.

## Consequences

### Positive

- Simpler deployment and operational model compared to microservices
- Shared domain logic avoids inconsistency and duplication
- Module boundaries provide organizational clarity without distributed-systems complexity
- Easier to refactor, test, and debug
- If a module demonstrably needs to be extracted to a separate service in the future, the clean boundary makes that possible

### Negative

- Requires discipline to maintain module boundaries within a single codebase
- All modules share the same deployment lifecycle
- Scaling individual modules independently requires extraction to separate services

### Neutral

- Workers are separate processes (not in-process), which provides some execution isolation while sharing code

## Alternatives Considered

1. **Microservices from the start**: Rejected. Adds operational complexity (service mesh, distributed tracing, API contracts between services) without a demonstrated need. Violates the principle of not introducing microservices unless there is a demonstrated architectural reason.

2. **Pure monolith without module boundaries**: Rejected. Leads to tight coupling and makes future refactoring difficult.

3. **Modular monolith with option to extract**: Selected. Provides the benefits of both approaches and defers distribution complexity until it is justified.
