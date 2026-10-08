# LogPilot — System Architecture Overview

## 1. Overview

LogPilot is an intelligent observability and incident investigation platform. It combines runtime log analysis, repository intelligence, historical incident retrieval, and evidence-based root cause analysis to help developers investigate production incidents.

This document describes the high-level system architecture as currently agreed. Implementation details that have not yet been finalized are marked as **TBD**.

## 2. System Components

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Developer Interfaces                              │
│                                                                             │
│   ┌──────────────────────┐          ┌──────────────────────┐                │
│   │   VS Code Extension  │          │    Web Dashboard     │                │
│   │   (TypeScript)       │          │    (React/TS)        │                │
│   └──────────┬───────────┘          └──────────┬───────────┘                │
│              │                                  │                           │
│              ▼                                  │                           │
│   ┌──────────────────────┐                      │                           │
│   │  Local LogPilot Agent│                      │                           │
│   │  (Python)            │                      │                           │
│   └──────────┬───────────┘                      │                           │
│              │                                  │                           │
└──────────────┼──────────────────────────────────┼───────────────────────────┘
               │                                  │
               ▼                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          FastAPI Backend                                     │
│                       (Modular Monolith)                                     │
│                                                                             │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│   │  Incident   │  │  Log        │  │  Repository  │  │  Settings / │      │
│   │  Management │  │  Management │  │  Intelligence│  │  Config     │      │
│   └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘      │
│                                                                             │
└────────┬──────────────┬──────────────┬──────────────┬───────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌──────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────────────────────┐
│  PostgreSQL  │ │   Redis    │ │   Qdrant   │ │      Async Workers           │
│  (System of  │ │  (Cache,   │ │ (Vector    │ │  ┌──────────┐ ┌──────────┐  │
│   Record)    │ │   Queues,  │ │  Retrieval,│ │  │Ingestion │ │Analysis  │  │
│              │ │   Ephemeral│ │  Indexing)  │ │  │Worker    │ │Worker    │  │
│              │ │   State)   │ │            │ │  └──────────┘ └──────────┘  │
└──────────────┘ └────────────┘ └────────────┘ │  ┌──────────┐              │
                                               │  │Indexing  │              │
                                               │  │Worker    │              │
                                               │  └──────────┘              │
                                               └──────────────────────────────┘
                                                          │
                                               ┌──────────┴──────────┐
                                               │                     │
                                               ▼                     ▼
                                      ┌──────────────┐     ┌──────────────┐
                                      │  ML / Intel  │     │ LLM Gateway  │
                                      │  Engine      │     │              │
                                      │  (Anomaly,   │     │  ┌────────┐  │
                                      │   Incident,  │     │  │ Ollama │  │
                                      │   RCA)       │     │  └────────┘  │
                                      └──────────────┘     │  ┌────────┐  │
                                                           │  │ Cloud  │  │
                                                           │  │ LLM    │  │
                                                           │  └────────┘  │
                                                           └──────────────┘
```

## 3. Component Responsibilities

### 3.1 VS Code Extension

- Primary developer interface
- Monitoring controls and incident notifications
- Incident investigation UI
- Repository-aware explanations and evidence display
- Probable root cause presentation
- Recommended investigation steps

The extension must **not** contain heavy ML or business logic. It communicates with the backend through the local agent.

### 3.2 Local LogPilot Agent

- Runs locally alongside the developer's environment
- Handles repository access, log collection, and Git information
- Performs local filtering and preprocessing
- Provides local inference integration (e.g., Ollama)
- Acts as the bridge between the VS Code extension and the backend

### 3.3 FastAPI Backend (Modular Monolith)

- Central API serving both the VS Code extension (via agent) and web dashboard
- Organized as a modular monolith — domain modules within a single deployable unit
- Handles incident management, log management, repository intelligence, and settings
- Coordinates with async workers for background processing
- Domain/business logic is shared between the API and workers to avoid duplication

See [ADR-001: Modular Monolith Architecture](../adr/adr-001-modular-monolith-architecture.md).

### 3.4 Async Workers

- Separate execution processes for long-running and background tasks
- **Ingestion Worker**: Log collection, parsing, normalization, template extraction
- **Analysis Worker**: Feature extraction, anomaly detection, incident correlation
- **Indexing Worker**: Vector embedding and Qdrant index management

Workers share domain logic with the API to avoid duplication.

### 3.5 Storage Layer

| Store | Role | Principle |
|---|---|---|
| **PostgreSQL** | System of record | Source of truth for all persistent data |
| **Redis** | Cache, queues, ephemeral state | Infrastructure — not a source of truth |
| **Qdrant** | Vector retrieval and indexing | Retrieval/indexing system — not a source of truth; rebuildable from PostgreSQL |

See [ADR-005: Storage Architecture](../adr/adr-005-storage-architecture.md).

### 3.6 ML / Intelligence Engine

- Anomaly detection (Isolation Forest initially; future: One-Class SVM, HDBSCAN, autoencoders)
- Incident correlation
- Root cause analysis (evidence-based, not LLM-only)
- RAG pipeline (dense retrieval initially; future: sparse/hybrid, reranking)

See [ADR-003: Evidence-Based RCA](../adr/adr-003-evidence-based-rca.md) and [ADR-009: RAG Pipeline Architecture](../adr/adr-009-rag-pipeline-architecture.md).

### 3.7 LLM Gateway

- Abstraction layer over LLM providers
- Supports local inference via Ollama and cloud LLM providers
- Produces structured outputs (not uncontrolled prose)
- The rest of the application is decoupled from any specific LLM provider

See [ADR-002: LLM Provider Abstraction](../adr/adr-002-llm-provider-abstraction.md).

### 3.8 Web Dashboard

- Incident management and investigation
- Live logs and service views
- Repository information
- Historical incidents and search
- Analytics
- Settings and AI provider configuration

## 4. Intelligence Pipeline

The intended end-to-end processing pipeline:

```
Application
    → Log Source
        → Collector
            → Parser
                → Normalizer
                    → Template Extraction
                        → Feature Extraction
                            → Anomaly Detection
                                → Incident Correlation
                                    → Evidence Collection
                                        → RCA Candidate Ranking
                                            → Retrieval / RAG
                                                → LLM Explanation
                                                    → Incident Result
                                                        → VS Code / Dashboard
```

See [ADR-004: Log Ingestion Adapter Pattern](../adr/adr-004-log-ingestion-adapter-pattern.md) for ingestion design.

## 5. Log Ingestion

V1 log sources:
1. Manual log input
2. Local file logs
3. Docker logs
4. OpenTelemetry

Future adapter targets: Kubernetes, Loki, ELK, CloudWatch, Datadog, and others.

An adapter abstraction decouples ingestion from any specific source.

## 6. Schema and API Contract Strategy

- **Canonical schemas** are defined as Python/Pydantic models in `packages/schemas/`
- FastAPI generates the OpenAPI specification from these models
- TypeScript types and API clients for the web dashboard and VS Code extension are **generated** from the OpenAPI spec
- API contracts are **not** manually duplicated across languages

```
Pydantic Models → FastAPI/OpenAPI → Generated TypeScript Types/Client → Web + Extension
```

Implementation of the generation pipeline is **TBD**.

## 7. Multi-Tenancy

V1 supports **project-level isolation**.

The architecture is designed to be future-ready for:

```
Organization → Teams → Projects → Repositories → Services
```

Major resources should be designed so that `organization_id` / `project_id` can be introduced consistently.

See [ADR-008: Multi-Tenancy Strategy](../adr/adr-008-multi-tenancy-strategy.md).

## 8. Security Considerations

Security is a first-class requirement:

- Authentication and authorization
- Project isolation
- Secret redaction before AI processing
- Repository filtering via `.logpilotignore` and built-in rules
- Safe LLM context construction (never send entire repositories by default)
- Audit logging
- Secure configuration management
- Encryption in transit (in deployment)
- Rate limiting where appropriate
- No autonomous code/configuration modification in V1

See [ADR-006: Repository Intelligence and Secret Redaction](../adr/adr-006-repository-intelligence-and-secret-redaction.md).

## 9. Observability

The system's own observability uses OpenTelemetry for tracing, metrics, and logging.

Implementation details are **TBD**.

## 10. Deployment

Target deployment infrastructure:
- Docker containers per service
- Docker Compose for local development and single-node deployment
- GitHub Actions for CI/CD

Production deployment strategy beyond Docker Compose is **TBD**.

## 11. Key Architectural Decisions

All major architectural decisions are recorded as ADRs in [docs/adr/](../adr/).

| ADR | Decision |
|---|---|
| [ADR-001](../adr/adr-001-modular-monolith-architecture.md) | Modular Monolith Architecture |
| [ADR-002](../adr/adr-002-llm-provider-abstraction.md) | LLM Provider Abstraction |
| [ADR-003](../adr/adr-003-evidence-based-rca.md) | Evidence-Based RCA |
| [ADR-004](../adr/adr-004-log-ingestion-adapter-pattern.md) | Log Ingestion Adapter Pattern |
| [ADR-005](../adr/adr-005-storage-architecture.md) | Storage Architecture |
| [ADR-006](../adr/adr-006-repository-intelligence-and-secret-redaction.md) | Repository Intelligence and Secret Redaction |
| [ADR-007](../adr/adr-007-local-agent-architecture.md) | Local Agent Architecture |
| [ADR-008](../adr/adr-008-multi-tenancy-strategy.md) | Multi-Tenancy Strategy |
| [ADR-009](../adr/adr-009-rag-pipeline-architecture.md) | RAG Pipeline Architecture |
| [ADR-010](../adr/adr-010-research-and-evaluation-framework.md) | Research and Evaluation Framework |
