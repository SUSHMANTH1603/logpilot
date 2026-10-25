# LogPilot — Repository Architecture Document

**Document ID:** D04  
**Status:** Draft for Architecture Review  
**Parent Documents:** [D01 — Product Requirements Document](file:///docs/requirements/PRD.md), [D02 — V1 Scope & Acceptance Criteria](file:///docs/requirements/V1_SCOPE.md), [D03 — System Architecture Document](file:///docs/architecture/SYSTEM_ARCHITECTURE.md)  
**Project:** LogPilot: An Intelligent Observability and Root Cause Analysis Platform  

---

## 1. Objective & Scope

The purpose of this document is to define a concrete, practical, and maintainable **monorepo repository architecture** for LogPilot. 

This repository architecture establishes:
- The physical organization of all applications, agents, workers, libraries, and machine learning components.
- Strict component boundaries and code ownership to prevent architectural degradation.
- Clear dependency rules and import invariants between frontend, backend, workers, and ML layers.
- Standards for configuration management, secret hygiene, testing tiers, and code quality workflows.
- A seamless runway for research experimentation and academic reproducibility without compromising production code cleanliness.

This document operationalizes the architectural decisions made in [D01](file:///docs/requirements/PRD.md), [D02](file:///docs/requirements/V1_SCOPE.md), and [D03](file:///docs/architecture/SYSTEM_ARCHITECTURE.md). It strictly avoids premature complexity and does not implement application functionality or generate premature scaffolding.

---

## 2. Approved Technology Direction

The repository architecture directly mirrors the approved V1 technology stack:

- **Backend Monolith:** Python 3.11+, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2.
- **Web Dashboard:** React, TypeScript, TailwindCSS, shadcn/ui, TanStack Query.
- **VS Code Extension:** TypeScript, VS Code Extension API (`@types/vscode`).
- **Local Agent:** Python 3.11+, `watchdog`, `GitPython`, HTTP client.
- **System of Record Database:** PostgreSQL 16+.
- **Queue / Ephemeral Cache:** Redis 7+.
- **Vector Search Index:** Qdrant v1.8+.
- **Machine Learning Subsystem:** `scikit-learn`, `numpy`, scientific Python stack.
- **Local LLM Execution:** Ollama via an abstract Gateway provider pattern.
- **Infrastructure:** Docker Compose (local and unified multi-container testing).
- **Testing Suites:** `pytest` (backend, workers, agent, ML), Vitest / React Testing Library (web), Playwright (end-to-end), VS Code Extension test framework.
- **CI / Automation:** GitHub Actions.

*Architecture Invariant:* The exact asynchronous worker execution framework (e.g., Celery vs. ARQ vs. Redis Streams / asyncio), embedding model, neural reranker, log template extraction miner, and default LLM model weights remain explicitly **TBD** and are not frozen in this document.

---

## 3. Repository Physical & Target Structure

LogPilot is structured as a unified monorepo. Below is the mapping between the physical directory tree initialized in the repository foundation and the target internal module layouts as implementation progresses:

```text
logpilot/
├── .github/
│   └── workflows/                      # GitHub Actions CI/CD workflows
├── agent/
│   └── logpilot-agent/                 # Developer machine agent daemon
│       ├── src/
│       │   └── logpilot_agent/         # Agent source (watchers, git, redaction, client)
│       └── tests/                      # Agent unit and integration tests
├── apps/
│   ├── api/                            # FastAPI backend modular monolith
│   │   ├── src/
│   │   │   └── logpilot_api/           # Core API, domain modules, database, integrations
│   │   └── tests/                      # Backend unit, integration, and contract tests
│   ├── vscode-extension/               # Visual Studio Code extension
│   │   ├── src/                        # Extension commands, tree views, diagnostics, webview
│   │   └── tests/                      # VS Code integration and extension tests
│   └── web/                            # Operational web dashboard
│       ├── src/                        # React components, pages, hooks, state, shadcn/ui
│       └── tests/                      # Web unit and component tests
├── datasets/                           # Benchmark & curated evaluation corpora (e.g., LogHub, synthetic)
│   ├── benchmarks/                     # Public reference log datasets
│   ├── synthetic/                      # Fault-injection log suites
│   └── README.md                       # Dataset provenance, license, and schema documentation
├── docs/
│   ├── adr/                            # Architectural Decision Records (ADR-001 through ADR-010)
│   ├── api/                            # API specifications and documentation notes
│   ├── architecture/                   # System and repository architecture (D03, D04)
│   ├── development/                    # Development standards, workflow, and Definition of Done
│   ├── research/                       # Research methodology and experiment specifications
│   ├── requirements/                   # Requirements and V1 scope (D01, D02)
│   └── roadmap.md                      # Strategic development roadmap
├── experiments/                        # Reproducible ML & research experiment configurations
│   ├── baselines/                      # Baseline experiment definitions and parameters
│   ├── results/                        # Generated metric outputs, ROC curves, CSVs (gitignored)
│   └── README.md                       # Experiment execution guide
├── infrastructure/
│   ├── compose/                        # Docker Compose deployment specifications
│   └── docker/                         # Service-specific Dockerfiles (api, web, workers, agent)
├── ml/                                 # Reusable ML algorithms, feature extractors, and scorers
│   ├── anomaly/                        # Log anomaly detection algorithms
│   ├── evaluation/                     # Metric evaluation harnesses (ROC-AUC, Hit@k, MRR)
│   ├── incident/                       # Incident correlation and clustering logic
│   ├── rca/                            # RCA candidate hypothesis ranking and scoring
│   └── retrieval/                      # Dense retrieval and semantic indexing logic
├── packages/
│   ├── client/                         # Generated TypeScript API client (OpenAPI-derived)
│   └── schemas/                        # Canonical shared schemas (minimal until concrete need)
├── scripts/                            # Development, database setup, and CI automation scripts
├── workers/                            # Asynchronous background execution processes
│   ├── analysis/                       # Anomaly detection & incident correlation worker entry points
│   ├── indexing/                       # Repository chunking & vector indexing worker entry points
│   └── ingestion/                      # Raw log parsing & template extraction worker entry points
├── .gitignore                          # Git file exclusion rules
├── .logpilotignore                     # Workspace secret and file scanner exclusion rules
└── README.md                           # Repository introduction and architectural navigation
```

*Note on Existing Directories:* The physical tree contains `.gitkeep` markers and directories initialized during the repository foundation. No existing files or folders are moved or renamed.

---

## 4. Component Boundaries & Ownership

To ensure architectural integrity, each directory in the monorepo has explicit responsibilities, owned boundaries, and non-owned exclusions.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          COMPONENT OWNERSHIP MATRIX                         │
├──────────────────────┬──────────────────────────────────────────────────────┤
│ Component            │ Core Ownership & Exclusions                          │
├──────────────────────┼──────────────────────────────────────────────────────┤
│ `apps/api`           │ OWNS: FastAPI app, routing, DI, authz, OpenAPI,      │
│                      │ transactional boundaries, domain orchestration.      │
│                      │ DOES NOT OWN: UI rendering, worker process loops,     │
│                      │ local file system watching.                          │
├──────────────────────┼──────────────────────────────────────────────────────┤
│ Backend Domain       │ OWNS: Core business rules, entities, state machines,  │
│ Modules              │ repository interfaces, scoring math, domain logic.   │
│                      │ DOES NOT OWN: HTTP requests/responses, CLI UI.       │
├──────────────────────┼──────────────────────────────────────────────────────┤
│ `workers/`           │ OWNS: Async job entry points, queue consumption,     │
│                      │ task execution, error reporting and retries.         │
│                      │ DOES NOT OWN: Custom domain rules (invokes API/core).│
├──────────────────────┼──────────────────────────────────────────────────────┤
│ `agent/`             │ OWNS: Client-side file tailing, Git diff harvesting, │
│                      │ secret redaction, `.logpilotignore` compliance.      │
│                      │ DOES NOT OWN: Global incident state, RCA calculation.│
├──────────────────────┼──────────────────────────────────────────────────────┤
│ `apps/web`           │ OWNS: React UI, triage screens, timeline charts,     │
│                      │ client-side state, user interaction workflows.       │
│                      │ DOES NOT OWN: Telemetry ingestion, auth policies.    │
├──────────────────────┼──────────────────────────────────────────────────────┤
│ `apps/vscode-`       │ OWNS: Extension commands, gutter decorations, tree   │
│ `extension`          │ views, editor diagnostics, webview panels.           │
│                      │ DOES NOT OWN: Direct database queries, ML scoring.   │
├──────────────────────┼──────────────────────────────────────────────────────┤
│ `packages/schemas`   │ OWNS: Technology-neutral canonical schemas (minimal).│
│                      │ DOES NOT OWN: Manual duplicate TypeScript types.     │
├──────────────────────┼──────────────────────────────────────────────────────┤
│ `packages/client`    │ OWNS: Generated TypeScript API client and models     │
│                      │ automatically produced from the OpenAPI schema.      │
│                      │ DOES NOT OWN: Hand-written endpoint wrappers.        │
├──────────────────────┼──────────────────────────────────────────────────────┤
│ `ml/`                │ OWNS: Pure algorithmic models, feature transformers, │
│                      │ evaluation metrics, test harnesses for Experiments.  │
│                      │ DOES NOT OWN: Database tables, web endpoints.        │
├──────────────────────┼──────────────────────────────────────────────────────┤
│ `infrastructure/`    │ OWNS: Dockerfiles, Docker Compose service topology,  │
│                      │ networking, volume configurations.                   │
│                      │ DOES NOT OWN: Application environment variables.     │
├──────────────────────┼──────────────────────────────────────────────────────┤
│ `datasets/`          │ OWNS: Curated benchmark log files and test manifests.│
│                      │ DOES NOT OWN: Production customer telemetry data.    │
├──────────────────────┼──────────────────────────────────────────────────────┤
│ `experiments/`       │ OWNS: Research parameter configs, experiment runs.   │
│                      │ DOES NOT OWN: Production deployment state.           │
└──────────────────────┴──────────────────────────────────────────────────────┘
```

### Detailed Component Boundaries

#### 1. `apps/api` (FastAPI Modular Monolith)
- **Primary Role:** The central nervous system and HTTP API boundary for LogPilot.
- **Responsibilities:**
  - FastAPI application bootstrapping and lifecycle management.
  - Route declaration, middleware registration (CORS, request logging, error handling).
  - Dependency injection wiring (database sessions, service instances, configuration).
  - Authentication verification (JWT bearer tokens, API keys) and project authorization.
  - OpenAPI specification generation and endpoint documentation.
  - Transaction boundary management (commit/rollback per request).
- **Prohibitions:** Must not collapse into a monolithic single file; must delegate business rules to domain modules; must not execute blocking, CPU-intensive vector calculations synchronously.

#### 2. Backend Domain / Application Modules (within `apps/api/src/logpilot_api/modules/`)
LogPilot organizes domain logic into self-contained logical modules within the modular monolith:
- `identity`: User accounts, authentication credentials, project role-based access.
- `projects`: Project workspaces, team memberships, project configuration.
- `repositories`: Code repository metadata, branch tracking, indexing status.
- `log_sources`: Telemetry emitters, ingestion tokens, source configurations.
- `events`: Ingested log events, normalization pipelines, template associations.
- `anomalies`: Anomaly scoring, statistical deviation signals, anomaly persistence.
- `incidents`: Correlated operational incidents, state machines, severity levels.
- `evidence`: Evidence graph linkages between incidents, logs, Git diffs, and code chunks.
- `rca`: Root cause hypothesis generation, multi-factor evidence scoring, candidate ranking.
- `retrieval`: Vector search orchestration, metadata filtering, context window budgeting.
- `llm_gateway`: Model-agnostic LLM provider integration, prompt formatting, JSON validation.
- `investigations`: Developer diagnostic sessions, annotations, resolution records.
- `audit`: Immutable audit logging for governance, security, and administrative actions.

*Rule:* Modules interact through defined Python interfaces and domain service calls, not via distributed HTTP or message brokers.

#### 3. `workers/` (Asynchronous Execution Processes)
- **Primary Role:** Background execution processes consuming tasks from Redis queues.
- **Organization:** Divided by functional responsibility:
  - `workers/ingestion/`: Consumes raw log batches, runs parsers, and extracts log templates.
  - `workers/analysis/`: Computes sliding-window feature vectors, scores anomalies, and correlates incidents.
  - `workers/indexing/`: Chunks repository files, calls embedding models, and upserts vectors to Qdrant.
- **Architecture Invariant:** Workers import and reuse the domain models, repositories, and services from `apps/api/src/logpilot_api/`. They **must not** reimplement domain rules, parsing algorithms, or database queries.

#### 4. `agent/logpilot-agent` (Developer Machine Daemon)
- **Primary Role:** Client-side background agent running locally on developer workstations.
- **Responsibilities:**
  - File watching (`watchdog`) of local application log files.
  - Git repository inspection (`git log`, diff extraction, commit metadata).
  - Pre-flight secret sanitization and filtering according to `.logpilotignore`.
  - Secure batch dispatch to the backend API over authenticated HTTPS.
- **Prohibitions:** Must not connect directly to PostgreSQL, Redis, or Qdrant; must not decide incident state or calculate RCA; backend remains the sole authoritative system of record.

#### 5. `apps/web` (Operational Web Dashboard)
- **Primary Role:** Browser-based incident command center for engineering teams.
- **Responsibilities:**
  - Panoramic log viewer and real-time log tailing.
  - Incident triage board, timeline visualization, and service dependency graphs.
  - Historical investigation drill-downs and audit log views.
  - System settings and AI provider configuration management.
- **Stack:** React, TypeScript, TailwindCSS, shadcn/ui.
- **Prohibitions:** Must not encode server-side business logic; all operations pass through the backend REST API.

#### 6. `apps/vscode-extension` (Developer IDE Extension)
- **Primary Role:** Native in-editor extension providing contextual observability to developers.
- **Responsibilities:**
  - Active incident alerts and notifications.
  - Editor gutter decorations on implicated source-code lines.
  - Diagnostic Webview panel rendering probable root causes and recommended fixes.
  - Direct jump-to-code navigation based on evidence citations.
- **Prohibitions:** Must not duplicate backend analytical logic; consumes data from the backend API or local agent.

#### 7. `packages/schemas` (Canonical Shared Schemas)
- **Primary Role:** Shared schema definition home.
- **Policy:** The backend Pydantic models in `apps/api` serve as the primary canonical schema source. `packages/schemas` remains minimal in V1 to prevent redundant schema duplication. Only technology-neutral schemas shared outside FastAPI (if any) are placed here.

#### 8. `packages/client` (Generated TypeScript API Client)
- **Primary Role:** Single shared TypeScript client consumed by `apps/web` and `apps/vscode-extension`.
- **Policy:** Strictly generated from the FastAPI OpenAPI schema. Never manually written or edited.

#### 9. `ml/` (Algorithms, Research & Evaluation)
- **Primary Role:** Algorithmic library containing statistical, machine learning, and retrieval components.
- **Organization:**
  - `ml/anomaly/`: Template frequency baselines and statistical anomaly detectors.
  - `ml/incident/`: Incident correlation and temporal debounce clustering.
  - `ml/retrieval/`: Semantic chunking strategies and dense similarity search logic.
  - `ml/rca/`: Heuristic candidate ranking and multi-source evidence scoring math.
  - `ml/evaluation/`: Benchmark runners, ROC-AUC calculators, Hit@k/MRR metrics.
- **Principle:** Algorithms implemented in `ml/` are pure and decoupled from web frameworks and database sessions. Both production workers and research experiment runners import the identical, versioned algorithmic logic.

#### 10. `datasets/` & `experiments/`
- `datasets/`: Stores curated synthetic incident traces and public benchmark references (e.g., LogHub). Raw secrets or multi-gigabyte files are never committed; test data uses tracked fixtures or download scripts.
- `experiments/`: Research experiment configurations, ablation study parameter files, and reproduction scripts for Experiments A–F.

---

## 5. Dependency Rules & Architecture Invariants

LogPilot strictly enforces unidirectional, non-circular dependency rules across monorepo packages.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ALLOWED DEPENDENCY FLOW                            │
│                                                                             │
│   ┌─────────────────────┐                   ┌───────────────────────────┐   │
│   │    apps/web (UI)    │                   │  apps/vscode-extension    │   │
│   └──────────┬──────────┘                   └─────────────┬─────────────┘   │
│              │ (TypeScript)                               │ (TypeScript)    │
│              ▼                                            ▼                 │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │               packages/client (Generated TypeScript API)            │   │
│   └──────────────────────────────────┬──────────────────────────────────┘   │
│                                      │ (Network HTTPS / REST)               │
│   ┌─────────────────────┐            │                                      │
│   │ agent/logpilot-agent│────────────┤                                      │
│   └─────────────────────┘            ▼                                      │
│                           ┌───────────────────────────┐                     │
│                           │         apps/api          │                     │
│                           │    (FastAPI Monolith)     │                     │
│                           └─────────────┬─────────────┘                     │
│                                         │                                   │
│                                         ▼                                   │
│                           ┌───────────────────────────┐                     │
│                           │   Domain Modules / Core   │                     │
│                           └──────┬─────────────────┬──┘                     │
│                                  │                 │                        │
│            ┌─────────────────────┘                 └──────────────────┐     │
│            ▼                                                          ▼     │
│   ┌─────────────────┐                                        ┌────────────┐ │
│   │    workers/     │                                        │    ml/     │ │
│   │ (Async Workers) │                                        │(Algorithms)│ │
│   └─────────────────┘                                        └────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Twelve Binding Dependency Invariants:

1. **Routers to Services Only:** API route handlers in `apps/api` delegate immediately to application/domain services. Routers must not execute complex domain calculations.
2. **Framework Decoupling:** Domain logic, entities, and services must never import FastAPI `Request`, `Response`, or `Depends` objects.
3. **Storage Client Abstraction:** Domain logic must interact with persistence through repository interfaces, not raw Redis connection pools or Qdrant client sockets.
4. **Controlled Persistence:** Direct SQL queries and SQLAlchemy models are restricted to repository/persistence packages; presentation and agent layers cannot access database sessions.
5. **No Worker Reimplementation:** Workers invoke shared domain services and models from `apps/api`; workers never copy-paste or duplicate API business rules.
6. **Agent Network Boundary:** The local agent communicates with LogPilot exclusively through documented HTTP/REST APIs. It must never import internal backend modules or database models.
7. **Client Layer Decoupling:** `apps/web` and `apps/vscode-extension` consume backend capabilities strictly through `packages/client` or direct REST contracts.
8. **Gateway Isolation:** RCA logic interacts with LLMs exclusively through the `LLMGateway` abstraction, never directly invoking Ollama or cloud provider SDKs.
9. **Pure ML Contracts:** Modules in `ml/` expose stable input/output interfaces (e.g., NumPy arrays, Pydantic data schemas) and must not depend on database or web models.
10. **Evidence Traceability:** Vector similarity search outputs from Qdrant must be linked to immutable database record IDs or source file paths.
11. **Isolated Testing:** Test suites must execute deterministically without requiring external cloud LLM API connectivity by default.
12. **Research Separation:** Experimental code in `experiments/` must not be imported into production paths in `apps/api` or `workers/`.

### Forbidden Dependency Directions:
- ❌ `apps/api` ➔ `apps/web` or `apps/vscode-extension` (Backend never depends on frontend).
- ❌ `ml/` ➔ `apps/api` (ML algorithms never depend on web endpoints or database tables).
- ❌ `agent/logpilot-agent` ➔ `apps/api` internal Python imports (Agent is decoupled from backend internals).
- ❌ `packages/schemas` ➔ `apps/api` (Shared packages must not create reverse dependencies).
- ❌ Domain Services ➔ Redis / Qdrant low-level driver calls (Must use abstraction ports).

---

## 6. Backend Internal Architecture (`apps/api`)

The backend follows a **Modular Monolith** pattern inside `apps/api/src/logpilot_api/`:

```text
apps/api/src/logpilot_api/
├── main.py                             # Application factory, lifespan events, middleware
├── core/                               # Core platform concerns
│   ├── config.py                       # Pydantic Settings and environment validation
│   ├── errors.py                       # Global error hierarchy and exception handlers
│   ├── logging.py                      # Structured JSON logging and correlation IDs
│   └── security.py                     # JWT token decoding, password hashing, API key verification
├── api/                                # HTTP presentation layer
│   ├── deps.py                         # FastAPI dependency injection providers
│   ├── router.py                       # Top-level API router aggregating module routes
│   └── v1/                             # Versioned route endpoints (/api/v1/...)
├── db/                                 # Relational database persistence
│   ├── base.py                         # SQLAlchemy declarative base and metadata
│   ├── session.py                      # Async database engine and sessionmaker
│   └── migrations/                     # Alembic migration scripts and env.py
├── modules/                            # Self-contained domain modules
│   ├── identity/                       # Users, credentials, permissions
│   ├── projects/                       # Projects, repositories, configurations
│   ├── logs/                           # Log sources, ingestion, normalization
│   ├── anomalies/                      # Anomaly detection results, scoring
│   ├── incidents/                      # Incident state machine, correlation
│   ├── evidence/                       # Evidence graph associations
│   ├── rca/                            # RCA candidate hypothesis generation and ranking
│   └── investigations/                 # Investigation notes, resolution audits
├── integrations/                       # External infrastructure adapters
│   ├── qdrant/                         # Qdrant client connection and collection management
│   ├── redis/                          # Redis client connection and queue publishers
│   └── llm/                            # LLM Gateway, Ollama client, Cloud adapters
└── observability/                      # Metrics, tracing hooks, OpenTelemetry integration
```

### Recommended Structure for Domain Modules

Domain modules within `modules/<domain>/` should follow a decoupled architectural pattern when appropriate, while maintaining clear responsibilities and explicit dependency boundaries:

- `models.py`: SQLAlchemy ORM database models representing persistent domain entities (used when the module owns database entities).
- `schemas.py`: Pydantic request, response, and internal domain data transfer models (used when the module defines validation or serialization contracts).
- `repository.py`: Data access object encapsulating database queries, mutations, and session interactions (used when the module requires specialized or non-trivial persistence logic).
- `service.py`: Pure domain business logic, state transitions, and workflow coordination (used to encapsulate operational rules independently of HTTP transport).
- `router.py`: FastAPI endpoint handlers mapping inbound HTTP routes to service calls (used when the module exposes public HTTP endpoints).

#### Pragmatic Structural Guidelines:
1. **Recommended Pattern, Not Rigid Mandate:** This layout is a recommended architectural guide rather than a compulsory boilerplate. Modules should only create files for responsibilities they genuinely possess.
2. **No Empty Placeholders:** Developers must not generate empty placeholder files, pass-through repositories, or vacuous abstraction layers solely to conform to a directory template.
3. **Transport and Domain Separation:** Where HTTP routing exists, `router.py` must remain cleanly separated from business rules and domain logic (`service.py`).
4. **Focused Modules:** For simpler domain components or utility modules that lack persistent entities or HTTP endpoints, consolidated files (e.g., a single focused service or schema definition) are completely acceptable.

---

## 7. Asynchronous Worker Architecture (`workers/`)

Workers execute asynchronous workloads decoupled from HTTP request loops:

```text
workers/
├── ingestion/                          # Raw log parsing and template extraction
│   ├── main.py                         # Worker process runner
│   ├── tasks.py                        # Batch ingestion tasks
│   └── handlers.py                     # Log parser and template miner dispatch
├── analysis/                           # Anomaly detection and incident clustering
│   ├── main.py                         # Worker process runner
│   ├── tasks.py                        # Feature extraction and anomaly detection tasks
│   └── correlator.py                   # Incident window clustering tasks
└── indexing/                           # Repository chunking and vector upserts
    ├── main.py                         # Worker process runner
    ├── tasks.py                        # Repository indexing tasks
    └── embeddings.py                   # Embedding generation and Qdrant upsert tasks
```

### Worker Design Invariants:
1. **Shared Domain Execution:** Worker tasks instantiate services from `logpilot_api.modules.*` to perform database updates.
2. **Idempotency Guarantee:** Every task payload carries a unique execution ID or natural idempotency key (e.g., `(project_id, source_id, log_batch_hash)`). Re-executing a task will not create duplicate log events or incidents.
3. **Dead-Letter Handling:** Tasks exceeding maximum retry counts ($N=3$) are routed to a dead-letter queue in Redis, accompanied by error metadata for operational inspection.
4. **Framework Agnosticism:** The worker layer is organized around task functions and handlers; the underlying execution engine remains an open choice (**TBD**).

---

## 8. Machine Learning & Research Structure (`ml/` & `experiments/`)

To preserve academic rigor and software quality, algorithmic research is decoupled from web transport layers:

```text
ml/
├── anomaly/                            # Anomaly detection algorithms
│   ├── base.py                         # BaseAnomalyDetector abstract interface
│   ├── statistical.py                  # Sliding-window statistical detectors
│   └── template_miner.py               # Log template mining abstraction
├── incident/                           # Incident correlation
│   ├── base.py                         # BaseIncidentCorrelator abstract interface
│   └── temporal.py                     # Temporal window debounce correlator
├── rca/                                # Root cause analysis scoring
│   ├── base.py                         # BaseRCAScorer abstract interface
│   └── heuristic.py                    # Multi-factor evidence ranking engine
├── retrieval/                          # Vector retrieval logic
│   ├── chunker.py                      # Source-code chunking algorithms
│   └── search.py                       # Dense similarity search logic
└── evaluation/                         # Evaluation harness
    ├── metrics.py                      # ROC-AUC, Precision, Recall, Hit@k, MRR
    └── runner.py                       # Experiment test suite execution harness
```

### Research Invariants:
1. **Single Source of Algorithmic Truth:** The algorithms evaluated in academic experiments (Experiments A–F) are the exact same code modules executed by production workers. Notebooks in `experiments/` call into `ml/` rather than implementing competing logic.
2. **Stateless Interfaces:** All ML components in `ml/` accept in-memory data structures (lists, arrays, Pydantic objects) and return pure outputs, making them effortlessly unit-testable without live databases.
3. **Explicit TBDs:** Exact feature dimensions, mathematical weights, similarity distance formulas, and scoring coefficients are formally deferred to [D08](file:///docs/architecture/ML_ARCHITECTURE.md) and [D09](file:///docs/architecture/RAG_ARCHITECTURE.md).

---

## 9. Configuration Management & Secret Hygiene

1. **Twelve-Factor Configuration:** Application configuration is loaded strictly from environment variables via Pydantic `Settings` classes (`apps/api/src/logpilot_api/core/config.py`).
2. **No Committed Secrets:**
   - Real API keys, passwords, database URLs, and cryptographic tokens are strictly forbidden in git.
   - `.env` files are ignored via `.gitignore`.
   - `.env.example` templates with documentation comments must be maintained for all services.
3. **Client-Side Redaction Enforcement:**
   - The local agent enforces `.logpilotignore` and hardcoded default blacklists (`.env*`, `*.pem`, `*.key`, `node_modules/`, `credentials`, `secrets`) before files or logs leave the host.
4. **Context Sanitization:** Telemetry logs and error responses must never expose raw connection strings, auth tokens, or unredacted secrets.

---

## 10. Testing Strategy & Test Placement

The monorepo organizes tests adjacent to their corresponding code components:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          TEST SUITE ORGANIZATION                            │
├───────────────────────────────┬─────────────────────────────────────────────┤
│ Directory                     │ Testing Scope & Responsibility              │
├───────────────────────────────┼─────────────────────────────────────────────┤
│ `apps/api/tests/unit/`        │ Fast unit tests for domain logic, schemas,  │
│                               │ utilities, and error mappings.              │
├───────────────────────────────┼─────────────────────────────────────────────┤
│ `apps/api/tests/integration/` │ Integration tests with PostgreSQL and Redis │
│                               │ test containers (API routes, repositories). │
├───────────────────────────────┼─────────────────────────────────────────────┤
│ `workers/*/tests/`            │ Worker task execution, retry handling, and  │
│                               │ task payload processing tests.              │
├───────────────────────────────┼─────────────────────────────────────────────┤
│ `agent/logpilot-agent/tests/` │ File tailing, Git diff harvesting, and      │
│                               │ secret redaction unit tests.                │
├───────────────────────────────┼─────────────────────────────────────────────┤
│ `apps/web/tests/`             │ React component rendering, user interaction,│
│                               │ and client state tests (Vitest).            │
├───────────────────────────────┼─────────────────────────────────────────────┤
│ `apps/vscode-extension/tests/`│ Extension activation, command execution, and│
│                               │ Webview message dispatch tests.             │
├───────────────────────────────┼─────────────────────────────────────────────┤
│ `ml/tests/`                   │ Algorithmic correctness, determinism, and   │
│                               │ mathematical metric calculation tests.      │
├───────────────────────────────┼─────────────────────────────────────────────┤
│ `tests/e2e/` (future)         │ Playwright end-to-end tests for the complete│
│                               │ Golden Demo workflow.                       │
└───────────────────────────────┴─────────────────────────────────────────────┘
```

### Testing Principles:
- **Fast Feedback:** Unit test suites must run in seconds without external network dependencies.
- **Mocked External Calls:** Tests involving the LLM Gateway default to deterministic mock providers; no live cloud LLM API is called during normal CI.
- **Research Evaluation Separation:** The scientific evaluation harness (`ml/evaluation/`) is run on demand for research benchmarks, separate from fast pull-request CI checks.

---

## 11. Code Quality & Development Workflow

### Tooling Standards:
- **Python:**
  - **Linter & Formatter:** `Ruff` (standardized on 100-character line length, PEP 8, isort rules).
  - **Type Checker:** `mypy` in strict mode.
  - **Test Runner:** `pytest` with `pytest-asyncio`.
- **TypeScript:**
  - **Linter:** `ESLint` with TypeScript ESLint recommended rules.
  - **Formatter:** `Prettier`.
  - **Type Checker:** `tsc --noEmit`.
  - **Test Runner:** `Vitest`.
- **API Client Generation:**
  - Fast script generating TypeScript types and client in `packages/client` from FastAPI's OpenAPI JSON export.
  - Drift checking runs in CI to verify that TypeScript client types match backend schemas.

### Git Conventions:
- **Branching Model:** Feature development occurs on `feature/<name>` branches branching from and merging into `develop`. `main` remains protected for verified milestones.
- **Commit Format:** Strict adherence to [Conventional Commits](https://www.conventionalcommits.org/):
  - `feat(api): add incident correlation endpoint`
  - `fix(agent): handle truncated log lines safely`
  - `docs(arch): update repository architecture`
  - `test(ml): add unit test for sliding window metrics`

---

## 12. Prohibitions Against Premature Complexity

To keep LogPilot maintainable and delivery-focused, the following anti-patterns are explicitly **prohibited**:

1. **No Microservices:** The backend must remain a Modular Monolith in V1. Splitting modules into independent microservices with HTTP/gRPC boundaries is forbidden without empirical performance evidence.
2. **No Micro-Packages:** Do not create separate `packages/` directories for trivial single-file helpers.
3. **No Duplicate API Schemas:** Do not manually create or maintain TypeScript interfaces that mirror FastAPI models; use the OpenAPI generator.
4. **No Reimplemented Logic:** Workers must call domain services; writing duplicate business rules in worker scripts is prohibited.
5. **No Coupled ML Persistence:** ML algorithms must not execute direct database queries or web requests.
6. **No Uncontrolled Artifact Commits:** Model weights, multi-megabyte log dumps, and SQLite scratch files must never be committed to git.
7. **No Speculative Abstractions:** Do not create generic plugin systems or distributed event brokers until concrete requirements demand them.

---

## 13. Explicit Implementation TBDs

The following implementation selections remain explicitly **TBD** and are deferred to downstream design documents:

1. **Exact Worker Framework:** Celery vs. ARQ vs. Redis Streams / asyncio workers (*Deferred to D05 / Implementation*).
2. **Exact Embedding Model:** Specific dense embedding model (*Deferred to D08 / D09*).
3. **Exact Neural Reranker:** Specific cross-encoder model for V2 experiments (*Deferred to D09 / D12*).
4. **Exact Log Template Extraction Algorithm:** Specific algorithm implementation (e.g., Drain3, Spell, or AEL) (*Deferred to D07 / D08*).
5. **Exact Default Local LLM:** Specific quantized open-source model weights (*Deferred to D10*).
6. **Exact CI Runner Topology:** Cloud runner sizing and matrix caching optimizations (*Deferred to Implementation*).

---

## 14. Relationship to Downstream Design Documents

This document (**D04**) defines the physical and organizational boundaries of the codebase. It delegates detailed specifications to:

- **D05 — Database & Domain Model:** Full relational schemas, tables, indices, and SQLAlchemy ORM entities.
- **D06 — API Contracts:** OpenAPI routes, request/response models, and error envelopes.
- **D07 — Event & Telemetry Schemas:** Log normalization contracts and template schemas.
- **D08 — ML Architecture:** Mathematical feature formulations, baseline detectors, and scoring equations.
- **D09 — RAG Architecture:** Chunking boundaries, Qdrant collection schemas, and context assembly formulas.
- **D10 — LLM Architecture:** Prompt templates, JSON mode validators, and provider failover logic.
- **D11 — Security Model:** Threat analysis, cryptographic key storage, and entropy algorithms.
- **D12 — Evaluation & Research:** Experimental protocols, benchmark configurations, and evaluation metrics.
