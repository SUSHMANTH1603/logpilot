# Architectural Decision Records

This directory contains Architectural Decision Records (ADRs) for the LogPilot project.

## What is an ADR?

An ADR is a document that captures an important architectural decision along with its context and consequences. ADRs provide a historical record of why certain decisions were made.

## Format

Each ADR follows this structure:

- **Title**: Short descriptive title
- **Status**: Proposed | Accepted | Deprecated | Superseded
- **Date**: Date the decision was recorded
- **Context**: The situation and forces that led to this decision
- **Decision**: What was decided
- **Consequences**: The resulting effects — positive, negative, and neutral
- **Alternatives Considered**: Other options that were evaluated

## Index

| ADR | Title | Status |
|---|---|---|
| [ADR-001](adr-001-modular-monolith-architecture.md) | Modular Monolith Architecture | Accepted |
| [ADR-002](adr-002-llm-provider-abstraction.md) | LLM Provider Abstraction | Accepted |
| [ADR-003](adr-003-evidence-based-rca.md) | Evidence-Based RCA | Accepted |
| [ADR-004](adr-004-log-ingestion-adapter-pattern.md) | Log Ingestion Adapter Pattern | Accepted |
| [ADR-005](adr-005-storage-architecture.md) | Storage Architecture — PostgreSQL, Redis and Qdrant | Accepted |
| [ADR-006](adr-006-repository-intelligence-and-secret-redaction.md) | Repository Intelligence and Secret Redaction | Accepted |
| [ADR-007](adr-007-local-agent-architecture.md) | Local Agent Architecture | Accepted |
| [ADR-008](adr-008-multi-tenancy-strategy.md) | Multi-Tenancy Strategy | Accepted |
| [ADR-009](adr-009-rag-pipeline-architecture.md) | RAG Pipeline Architecture | Accepted |
| [ADR-010](adr-010-research-and-evaluation-framework.md) | Research and Evaluation Framework | Accepted |

## Creating New ADRs

1. Use the next sequential number: `adr-NNN-short-title.md`
2. Follow the format described above
3. Do not create an ADR until the decision has actually been made and discussed
4. Link the new ADR in this index
