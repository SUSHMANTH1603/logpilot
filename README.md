# LogPilot

**LogPilot: An Intelligent Observability and Root Cause Analysis Platform**

LogPilot is a developer-first observability and incident investigation platform that continuously analyzes application runtime logs, repository context, Git changes, service relationships, and historical incidents to detect anomalies, correlate failures, identify probable root causes, and provide evidence-backed investigation guidance.

## What LogPilot Is

LogPilot is an intelligent incident investigation layer on top of observability data. It combines runtime anomaly detection, repository intelligence, and historical incident retrieval to provide evidence-based root cause analysis.

## What LogPilot Is Not

- A generic chatbot
- A simple RAG application
- A log viewer
- An LLM wrapper
- A replacement for Datadog / Splunk / Grafana
- An autonomous code modification system

## Interfaces

| Interface | Purpose |
|---|---|
| **VS Code Extension** | Primary developer workflow — monitoring, incident notifications, investigation, repository-aware explanations, probable root cause, evidence, recommended investigation steps |
| **Web Dashboard** | Incident management, live logs, services, repository information, historical incidents, search, analytics, settings, AI provider configuration |

## Architecture

```
VS Code Extension ──► Local LogPilot Agent ──► FastAPI Backend
                                                    │
                                          ┌─────────┼─────────┐
                                          │         │         │
                                     PostgreSQL   Redis    Qdrant
                                          │
                                    ┌─────┴──────────────────────────┐
                                    │                                │
                              Async Workers                    ML / Intelligence
                              (Ingestion,                      (Anomaly Detection,
                               Analysis,                       Incident Correlation,
                               Indexing)                       RCA, RAG, LLM Gateway)

Web Dashboard ──────────────────────► FastAPI Backend
```

For detailed architecture documentation, see [docs/architecture/SYSTEM_OVERVIEW.md](docs/architecture/SYSTEM_OVERVIEW.md).

## Repository Structure

```
logpilot/
├── apps/
│   ├── api/                    # FastAPI backend (modular monolith)
│   ├── web/                    # React/TypeScript web dashboard
│   └── vscode-extension/       # VS Code extension (TypeScript)
├── agent/
│   └── logpilot-agent/         # Local Python agent
├── packages/
│   ├── schemas/                # Canonical Pydantic schemas
│   └── client/                 # Generated API client(s)
├── workers/
│   ├── ingestion/              # Log ingestion workers
│   ├── analysis/               # Anomaly detection / feature extraction
│   └── indexing/               # Qdrant indexing / embedding workers
├── ml/
│   ├── anomaly/                # Anomaly detection models
│   ├── incident/               # Incident correlation
│   ├── retrieval/              # RAG / retrieval pipeline
│   ├── rca/                    # Root cause analysis engine
│   └── evaluation/             # Evaluation harness and metrics
├── datasets/                   # Curated/synthetic datasets for evaluation
├── experiments/                # MLflow experiments, notebooks, results
├── infrastructure/
│   ├── docker/                 # Dockerfiles per service
│   └── compose/                # Docker Compose configurations
├── docs/
│   ├── architecture/           # System architecture documentation
│   ├── adr/                    # Architectural Decision Records
│   ├── api/                    # API documentation
│   ├── research/               # Research questions and experiment designs
│   └── development/            # Development standards and guides
├── scripts/                    # Development and CI utility scripts
└── .github/
    └── workflows/              # GitHub Actions CI/CD
```

## Documentation

| Document | Description |
|---|---|
| [System Overview](docs/architecture/SYSTEM_OVERVIEW.md) | High-level architecture |
| [ADRs](docs/adr/) | Architectural Decision Records |
| [Development Standards](docs/development/DEVELOPMENT.md) | Engineering standards and conventions |
| [AI Workflow](docs/development/AI_WORKFLOW.md) | AI-assisted development process |
| [Definition of Done](docs/development/DEFINITION_OF_DONE.md) | Completion criteria |
| [Roadmap](docs/roadmap.md) | Development roadmap |
| [Research](docs/research/) | Research direction and experiment design |

## Tech Stack

| Layer | Technologies |
|---|---|
| VS Code Extension | TypeScript, VS Code Extension API |
| Local Agent | Python |
| Web Dashboard | React, TypeScript, TailwindCSS, shadcn/ui, Recharts, React Flow |
| Backend API | Python, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic |
| Storage | PostgreSQL, Redis, Qdrant |
| ML | scikit-learn, Sentence Transformers, Isolation Forest (initial) |
| AI | Ollama, cloud LLM provider abstraction |
| Observability | OpenTelemetry |
| Infrastructure | Docker, Docker Compose, GitHub Actions |
| Testing | Pytest, Vitest, Playwright |
| Evaluation | MLflow, custom evaluation harness |

## Getting Started

> **Note:** LogPilot is in the repository initialization phase. Application implementation has not yet begun. See the [Roadmap](docs/roadmap.md) for planned development phases.

## License

TBD

## Contributing

TBD — contribution guidelines will be established before the project accepts external contributions.
