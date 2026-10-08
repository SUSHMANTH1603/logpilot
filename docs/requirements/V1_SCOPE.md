# LogPilot — V1 Scope & Acceptance Criteria

**Document ID:** D02
**Status:** Draft for approval
**Parent Document:** D01 — Product Requirements
**Project:** LogPilot — Intelligent Observability and Root Cause Analysis Platform

---

## 1. Purpose

D02 converts the approved D01 Product Requirements into a concrete V1 implementation scope.

It defines:

- what must be implemented in V1
- what should be implemented if capacity permits
- what is explicitly deferred
- implementation priorities
- feature dependencies
- end-to-end vertical slices
- measurable acceptance criteria
- demo-critical capabilities
- research-critical capabilities
- V1 Definition of Done

D02 does not introduce new product requirements. It constrains and prioritizes requirements already established in D01.

---

# 2. V1 Product Goal

V1 must demonstrate that LogPilot can take runtime log data from a supported application, detect abnormal behavior, create or propose an incident, gather relevant repository and Git evidence, retrieve supporting context, rank probable root causes, and present an evidence-backed explanation through the product interfaces.

The core V1 outcome is:

> **Given a realistic application failure, LogPilot should detect the abnormal behavior, correlate relevant events into an incident, identify evidence from runtime data and the repository, rank probable root causes, and explain the reasoning with explicit evidence.**

V1 is successful when this workflow works end-to-end on a reproducible demonstration environment and can also be evaluated experimentally.

---

# 3. V1 Priority Model

## P0 — Demo Critical

Required for the V1 product to be considered functional.

P0 capabilities must work end-to-end.

## P1 — Research Critical

Required to establish meaningful ML/RAG/RCA experiments and support the final-year research objective.

P1 capabilities must be implemented sufficiently to produce reproducible evaluation results.

## P2 — Product Polish

Useful for usability, extensibility, and production-readiness but not required for the first complete vertical slice.

P2 capabilities may be implemented after the core system is stable.

---

# 4. V1 Feature Matrix

| Capability | Priority | V1 Status | Notes |
|---|---|---|---|
| Project creation/isolation | P0 | Must | Project is primary V1 boundary |
| Authentication | P0 | Must | Initial authentication mechanism |
| Local repository discovery | P0 | Must | Required by developer workflow |
| Repository scanning | P0 | Must | Source/config/dependency structure |
| Git metadata collection | P0 | Must | Recent commits and changed files |
| Manual log input | P0 | Must | Simplest deterministic ingestion path |
| Local file log ingestion | P0 | Must | Primary local runtime source |
| Docker log ingestion | P0 | Should | Important realistic demo source |
| OpenTelemetry ingestion | P1 | Later in V1 | Add after core pipeline |
| Log parsing | P0 | Must | Structured and common unstructured logs |
| Log normalization | P0 | Must | Canonical internal representation |
| Log template extraction | P1 | Must | Needed for ML features |
| Feature extraction | P1 | Must | Time/window/error/template features |
| Statistical baseline | P1 | Must | Research baseline |
| Isolation Forest | P1 | Must | Initial ML anomaly model |
| Anomaly scoring | P0 | Must | Required by incident pipeline |
| Incident correlation | P0 | Must | Group related anomalous events |
| Automatic incident creation | P0 | Must | For high-confidence cases |
| Potential incident state | P0 | Must | For lower-confidence cases |
| Incident lifecycle | P0 | Must | Detected/investigating/resolved/ignored |
| Repository context extraction | P0 | Must | Source/config/dependency context |
| Git correlation | P0 | Must | Changed files/commits near incident |
| Historical incidents | P1 | Should | Initial historical retrieval |
| Dense retrieval | P1 | Must | Initial RAG capability |
| Metadata filtering | P1 | Must | Project/file/service constraints |
| Hybrid retrieval | P1 | Should | Dense + metadata/sparse retrieval |
| Reranking | P2 | Later | Research extension |
| RCA candidate generation | P0 | Must | Produce ranked probable causes |
| Evidence scoring | P0 | Must | Rank causes using evidence |
| LLM explanation | P0 | Must | Explain ranked RCA |
| Evidence attribution | P0 | Must | Explanation must reference evidence |
| Ollama integration | P0 | Must | Local/default LLM path |
| Cloud LLM abstraction | P2 | Later | Provider abstraction may be stubbed |
| VS Code incident view | P0 | Must | Core developer interface |
| VS Code investigation workflow | P0 | Must | Core demo path |
| Web dashboard | P0 | Must | Core team/operations interface |
| Incident timeline | P0 | Must | Required for investigation |
| Repository evidence view | P0 | Must | Required for RCA transparency |
| RCA explanation view | P0 | Must | Required for user evaluation |
| Local agent | P0 | Must | Required for VS Code workflow |
| Secret filtering/redaction | P0 | Must | Security requirement |
| `.logpilotignore` | P0 | Must | Repository/log filtering |
| Project authorization/isolation | P0 | Must | V1 security boundary |
| Audit logging | P1 | Should | Important for investigation |
| Rate limiting | P2 | Later | Add where required |
| OpenTelemetry for LogPilot itself | P1 | Should | Self-observability |
| Docker Compose deployment | P0 | Must | Reproducible local environment |
| CI pipeline | P0 | Must | Automated quality checks |
| Unit tests | P0 | Must | All core modules |
| Integration tests | P0 | Must | Critical data flows |
| End-to-end tests | P1 | Must | Golden demo workflow |
| ML evaluation harness | P1 | Must | Research requirement |
| Retrieval evaluation | P1 | Must | Research requirement |
| RCA evaluation | P1 | Must | Research requirement |
| MLflow experiment tracking | P2 | Later | Add once experiments stabilize |
| Multi-tenancy architecture | P1 | Must | Architecture-ready |
| Enterprise multi-tenancy | P2 | Later | Not V1 scope |
| Autonomous remediation | — | Excluded | Explicitly prohibited in V1 |
| Autonomous code modification | — | Excluded | Explicitly prohibited in V1 |
| Mobile application | — | Excluded | Not V1 |
| Slack/Teams integration | — | Excluded | Not V1 |
| Kubernetes-first deployment | — | Excluded | Not V1 |
| Custom foundation model | — | Excluded | Not V1 |

---

# 5. P0 — Core Product Scope

## 5.1 Project and Access

V1 must provide a project boundary so that logs, repository context, incidents, and retrieved information belong to the correct project.

### Acceptance Criteria

- A project can be created.
- A project has a stable identifier.
- Project-scoped data cannot be accidentally mixed with another project.
- Unauthorized access to another project's data is rejected.
- Core API endpoints enforce project authorization.

---

# 6. P0 — Repository Intelligence

LogPilot must understand enough of the repository to provide useful investigation context.

### V1 repository context

The system should identify:

- source files
- configuration files
- dependency manifests
- Docker configuration
- environment structure without exposing secrets
- project structure
- relevant service/module relationships where determinable

### Acceptance Criteria

Given a supported repository:

1. LogPilot can discover the repository.
2. It can identify relevant source/config/dependency files.
3. Excluded files are not indexed.
4. Secret-like files are filtered.
5. Repository metadata is associated with the correct project.
6. Relevant repository context can be retrieved during an investigation.

---

# 7. P0 — Git Intelligence

Git history is used as contextual evidence.

### V1 scope

- recent commits
- changed files
- commit timestamps
- commit messages
- relationship between changed files and repository context

### Acceptance Criteria

Given an incident occurring after a relevant code change:

- LogPilot can identify recent relevant commits.
- Changed files can be associated with repository evidence.
- Git evidence can be displayed in the incident investigation.
- Git evidence is treated as supporting evidence rather than proof of causality.

---

# 8. P0 — Log Ingestion

V1 supports:

1. manual log input
2. local log files

Docker ingestion is targeted immediately after the basic ingestion path is stable.

### Acceptance Criteria

The system can:

- accept logs
- validate incoming records
- associate logs with a project
- preserve timestamps
- preserve source metadata
- handle malformed records without crashing the ingestion pipeline
- report ingestion failures clearly

---

# 9. P0 — Log Processing

Incoming logs must be converted into a canonical internal representation.

### Processing stages

```text
Raw Log
   ↓
Parser
   ↓
Normalizer
   ↓
Template Extraction
   ↓
Feature Extraction
   ↓
Analysis
```

### Acceptance Criteria

For supported logs:

- timestamps are normalized
- severity is normalized where available
- service/source metadata is preserved
- message content is preserved safely
- structured fields are retained
- log templates can be extracted for supported patterns
- processing failures are observable
- normalized events can be queried by downstream components

---

# 10. P1 — Anomaly Detection

V1 must contain both a classical/statistical baseline and an initial ML model.

### Initial models

- statistical baseline
- Isolation Forest

The models must operate on reproducible feature representations.

### Acceptance Criteria

For a labelled/evaluable dataset:

- anomaly scores are generated
- predictions can be evaluated
- baseline metrics can be compared against Isolation Forest
- false positives and false negatives can be measured
- model/version/configuration information is recorded
- thresholds are configurable/calibratable rather than arbitrary constants

The anomaly detector must not depend on an LLM.

---

# 11. P0 — Incident Correlation

Anomalies must be grouped into meaningful incidents.

### V1 strategy

High-confidence anomalous event groups:

→ automatic incident

Lower/medium-confidence groups:

→ potential incident / human review

The decision must be based on deterministic/configurable incident logic and calibrated thresholds.

The LLM must not decide whether an incident exists.

### Acceptance Criteria

A valid incident:

- has a unique identifier
- belongs to one project
- has a lifecycle state
- references relevant events
- records detection information
- records confidence information
- can transition through the supported lifecycle
- preserves investigation evidence

---

# 12. Incident Lifecycle

V1 supports:

```text
DETECTED
   ↓
INVESTIGATING
   ↓
RESOLVED

DETECTED
   ↓
IGNORED
```

### Acceptance Criteria

- Incident state changes are persisted.
- Invalid transitions are rejected.
- Current incident state is visible through the UI.
- Investigation evidence remains available after resolution.

---

# 13. P0 — Root Cause Analysis

The RCA system must produce **ranked probable causes**, not an unsupported single answer.

### RCA pipeline

```text
Incident
   ↓
Evidence Collection
   ↓
Candidate Causes
   ↓
Evidence Scoring
   ↓
Ranked RCA Candidates
   ↓
LLM Explanation
```

Potential evidence sources:

- anomalous logs
- temporal relationships
- affected services
- repository context
- Git changes
- dependencies/configuration
- historical incidents where available

### Acceptance Criteria

For an evaluable incident:

- RCA produces one or more candidates.
- Candidates are ranked.
- Each candidate has supporting evidence.
- Evidence sources are identifiable.
- The system can distinguish evidence from generated explanation.
- RCA does not claim certainty when evidence is insufficient.

The preferred language is **"probable root cause"**, not "root cause confirmed."

---

# 14. P1 — Retrieval / RAG

V1 retrieval must support repository and investigation context.

### Initial retrieval strategy

```text
Query
 ↓
Dense Retrieval
 ↓
Metadata Filtering
 ↓
Relevant Context
```

Hybrid retrieval may be added after the basic dense retrieval pipeline is validated.

### Acceptance Criteria

- repository content can be indexed
- embeddings can be generated
- relevant chunks can be retrieved
- retrieval is project-scoped
- metadata filters can restrict retrieval
- retrieved evidence can be associated with RCA investigations
- retrieval results can be evaluated using Recall@K / MRR or equivalent metrics

---

# 15. P0 — LLM Explanation

The LLM is an explanation and synthesis layer, not the primary anomaly detector or incident decision-maker.

### Default V1 model path

Ollama/local model.

### Required behavior

The LLM receives structured evidence and produces:

- incident summary
- probable root cause
- supporting evidence
- relevant repository/Git context
- confidence/uncertainty
- recommended investigation steps

### Acceptance Criteria

- LLM output is generated from supplied evidence.
- Evidence references are preserved.
- Unsupported claims are minimized.
- The system indicates when evidence is insufficient.
- LLM failures do not corrupt incident state.
- LLM latency/errors are observable.
- LLM provider can eventually be replaced without rewriting RCA logic.

---

# 16. P0 — VS Code Extension

The VS Code extension is a first-class V1 interface.

### Required workflow

```text
Open Repository
      ↓
Start LogPilot
      ↓
Monitor
      ↓
Incident Detected
      ↓
Open Incident
      ↓
Review Timeline
      ↓
Review Evidence
      ↓
Review Probable RCA
      ↓
Investigate / Resolve / Ignore
```

### Acceptance Criteria

A developer can:

- open LogPilot in VS Code
- connect/select a project
- start monitoring
- view detected incidents
- open an incident
- inspect relevant logs
- inspect repository evidence
- inspect Git evidence
- inspect RCA results
- inspect evidence-backed explanation
- update incident state

---

# 17. P0 — Web Dashboard

The dashboard provides the broader investigation and operations interface.

### Required V1 views

- project overview
- incident list
- incident details
- incident timeline
- log/event context
- repository evidence
- Git evidence
- RCA candidates
- explanation/evidence view

### Acceptance Criteria

The dashboard:

- displays project-scoped incidents
- updates incident state correctly
- shows investigation evidence
- displays ranked RCA candidates
- distinguishes raw evidence from generated explanation
- handles loading/error/empty states

---

# 18. P0 — Local Agent

The local agent bridges the developer environment and backend.

### Responsibilities

- repository discovery
- local file monitoring
- log collection
- Git metadata
- filtering/redaction
- backend communication

### Acceptance Criteria

- agent can identify the configured repository
- excluded files are respected
- secrets are not intentionally transmitted
- log events can reach the backend
- Git metadata can reach the backend
- communication failures are handled gracefully

---

# 19. P0 — Security

Security is part of the core product rather than a later feature.

V1 must include:

- authentication
- project authorization
- project isolation
- secret filtering
- repository exclusion rules
- `.logpilotignore`
- safe handling of LLM context
- secure error handling

### Default exclusions

```text
.env*
*.pem
*.key
credentials
secrets
node_modules/
.git/
dist/
build/
```

### Acceptance Criteria

- excluded files are not indexed
- obvious secrets are filtered/redacted
- unauthorized project access fails
- sensitive values are not intentionally included in LLM prompts
- security-sensitive failures are logged appropriately

---

# 20. P0 — Infrastructure

The complete V1 development environment must be reproducible.

Required infrastructure:

```text
PostgreSQL
Redis
Qdrant
FastAPI
Workers
Web
Local Agent
VS Code Extension
Ollama
```

Docker Compose is the initial reproducibility mechanism.

### Acceptance Criteria

A new developer following the documentation can:

1. clone the repository
2. configure required environment values
3. start the infrastructure
4. start the application
5. create/select a project
6. ingest logs
7. trigger detection
8. investigate an incident

without undocumented manual steps.

---

# 21. P0 — Testing

Required testing layers:

### Unit

Core logic including:

- parsers
- normalization
- feature extraction
- anomaly logic
- incident correlation
- RCA scoring
- security filtering

### Integration

At minimum:

- API/database
- ingestion/processing
- incident persistence
- retrieval
- LLM gateway

### End-to-End

At least one complete golden demo workflow.

---

# 22. P1 — Research Scope

Research-critical V1 must support controlled experiments.

Required experiments:

### Experiment A — Anomaly Detection

Compare:

- statistical baseline
- Isolation Forest

Metrics:

- precision
- recall
- F1
- false-positive rate

### Experiment B — Retrieval

Compare:

- dense retrieval
- hybrid retrieval where implemented

Metrics:

- Recall@K
- MRR
- nDCG where applicable

### Experiment C — Context Contribution

Compare RCA performance using:

1. log-only
2. log + repository
3. log + repository + history

### Experiment D — Evidence Grounding

Compare:

1. LLM without structured evidence
2. evidence-grounded LLM

Evaluate:

- correctness
- relevance
- groundedness
- evidence attribution

### Experiment E — RCA Performance

Measure:

- top-1 accuracy
- top-3 recall

### Experiment F — Retrieval/RCA Extension

Where implemented, evaluate reranking and/or additional retrieval strategies as an extension experiment.

---

# 23. Research Reproducibility

Each experiment must record enough information to reproduce results.

Track:

- dataset version
- feature configuration
- model
- model version
- embedding model
- retrieval configuration
- RCA configuration
- LLM configuration
- evaluation metrics
- experiment timestamp
- relevant code/config version

MLflow is optional for early implementation and may be introduced during the experiment phase.

---

# 24. Golden Demo Vertical Slice

The following scenario defines the primary V1 demonstration.

### Scenario

A supported application experiences a known failure after a code/configuration change.

### Expected flow

1. Developer opens the repository.
2. Developer starts LogPilot.
3. Local agent discovers the repository.
4. LogPilot begins receiving logs.
5. Logs are parsed and normalized.
6. Feature extraction occurs.
7. An anomaly is detected.
8. Related anomalous events are correlated.
9. A high-confidence incident is created.
10. Incident timeline is generated.
11. Repository context is collected.
12. Recent Git changes are identified.
13. Relevant repository evidence is retrieved.
14. RCA candidates are generated and ranked.
15. Evidence is attached to candidates.
16. LLM generates an evidence-backed explanation.
17. Developer views the incident in VS Code.
18. Developer can inspect the same incident in the dashboard.
19. Developer resolves or ignores the incident.

This is the **minimum complete product story**.

---

# 25. V1 Demo Success Criteria

The golden demo is considered successful if:

- the failure is reproducible
- logs reach LogPilot
- anomalous behavior is detected
- an incident is generated or proposed appropriately
- relevant events are correlated
- repository evidence is retrieved
- Git evidence is surfaced when relevant
- at least one meaningful RCA candidate is produced
- supporting evidence is visible
- the LLM explanation reflects the supplied evidence
- the same incident is visible through both primary interfaces
- the workflow can be repeated reliably

---

# 26. Explicit V1 Exclusions

The following are outside V1:

- autonomous production remediation
- autonomous code modification
- automatic deployment changes
- mobile applications
- browser extensions
- Slack/Teams integrations
- enterprise SSO
- billing/subscriptions
- multi-region deployment
- Kubernetes-first architecture
- large-scale distributed microservice architecture
- Kafka/NATS unless later justified
- dozens of log integrations
- custom foundation model training
- large-scale LLM fine-tuning
- multi-agent architecture
- autonomous incident response
- replacing existing observability platforms

These exclusions may be revisited through a future scope decision but must not enter V1 implicitly.

---

# 27. Feature Dependencies

The implementation dependency chain is:

```text
Project / Auth
      ↓
Infrastructure
      ↓
Schemas / API
      ↓
Local Agent
      ↓
Log Ingestion
      ↓
Log Processing
      ↓
Feature Extraction
      ↓
Anomaly Detection
      ↓
Incident Correlation
      ↓
Repository Intelligence
      ↓
Git Intelligence
      ↓
Retrieval
      ↓
RCA
      ↓
LLM Explanation
      ↓
VS Code + Dashboard
      ↓
E2E Evaluation
```

Infrastructure, schemas, security, and testing are cross-cutting concerns.

---

# 28. Implementation Order

The recommended order is:

## Phase 1 — Foundation

- project configuration
- environment configuration
- canonical schemas
- database foundation
- API foundation
- authentication/authorization
- testing foundation
- CI

## Phase 2 — Runtime Data

- local agent foundation
- manual ingestion
- local file ingestion
- parser
- normalizer
- event persistence

## Phase 3 — Detection

- feature extraction
- statistical baseline
- Isolation Forest
- anomaly scoring
- incident correlation
- incident lifecycle

## Phase 4 — Context

- repository discovery
- repository scanning
- Git intelligence
- filtering/redaction

## Phase 5 — Investigation Intelligence

- embeddings
- Qdrant indexing
- retrieval
- evidence collection
- RCA ranking
- Ollama integration
- grounded explanation

## Phase 6 — Interfaces

- VS Code incident workflow
- dashboard
- timeline
- evidence visualization
- RCA visualization

## Phase 7 — Validation

- integration tests
- E2E tests
- golden demo
- research experiments
- evaluation
- deployment documentation

---

# 29. Definition of Done — V1

V1 is not considered complete merely because the application runs.

A V1 feature is considered done when applicable:

- implementation exists
- tests exist
- error handling exists
- security considerations are addressed
- API/schema contracts are defined
- documentation is updated
- acceptance criteria pass
- observability exists where appropriate
- no known critical regression exists

The complete V1 is done when:

1. Golden demo passes.
2. P0 acceptance criteria pass.
3. Critical security requirements pass.
4. Core unit/integration tests pass.
5. End-to-end workflow passes.
6. Docker-based setup is reproducible.
7. CI passes.
8. Research-critical capabilities can produce evaluation results.
9. Evidence-backed RCA is demonstrable.
10. VS Code and web dashboard both support the core investigation workflow.
11. No V1 exclusion has been implemented accidentally as core scope.
12. Documentation is sufficient for another developer to reproduce the system.

---

# 30. Scope Control Rules

To prevent uncontrolled scope expansion:

1. New features must map to an approved D01 requirement.
2. Features not required by D01 or D02 require an explicit scope decision.
3. Architecture complexity must be justified by a concrete requirement.
4. New infrastructure must not be introduced merely because it is popular.
5. Research experiments must not destabilize the production path.
6. Experimental implementations should be isolated from the stable product path.
7. P2 work must not delay completion of P0.
8. V1 exclusions remain excluded unless explicitly reconsidered.
9. Antigravity and Claude must not infer new product requirements.
10. Major architecture changes require an ADR.

---

# 31. Traceability

D02 remains subordinate to D01.

The major future design documents are:

- D03 — System Architecture
- D04 — Repository Architecture
- D05 — Database / Domain Model
- D06 — API Contracts
- D07 — Event / Log Schema
- D08 — ML Architecture
- D09 — RAG Architecture
- D10 — LLM Architecture
- D11 — Security Model
- D12 — Evaluation / Research

D02 defines scope and acceptance criteria; these documents define implementation architecture and technical design.

---

# 32. Open / TBD Items

The following remain intentionally open unless explicitly resolved by later design documents:

- exact authentication implementation
- exact worker framework
- exact embedding model
- exact reranking approach
- exact anomaly feature set
- exact anomaly thresholds
- exact incident correlation algorithm
- exact RCA scoring formulation
- exact LLM model
- exact cloud LLM provider implementation
- exact retrieval index structure
- exact OpenTelemetry integration details
- exact generated TypeScript client implementation
- exact deployment topology
- exact ML experiment tracking implementation

These must not be silently resolved by implementation agents.

---

# 33. D02 Approval Criteria

D02 is ready for approval when:

- V1 scope is understandable without D01
- P0/P1/P2 priorities are clear
- V1 exclusions are explicit
- golden demo is reproducible as a requirement
- acceptance criteria are measurable
- research scope is identifiable
- implementation dependencies are clear
- no new product requirements have been introduced
- unresolved architectural choices remain explicitly TBD

---

# 34. Final V1 Definition

The V1 product is:

> **A developer-first intelligent observability system that detects anomalous runtime behavior, correlates events into incidents, combines runtime data with repository and Git context, retrieves supporting evidence, ranks probable root causes, and produces evidence-backed investigation guidance through VS Code and a web dashboard.**

V1 is **not** an autonomous remediation platform and is **not** intended to replace established observability systems.

Its core value is:

> **From "something is wrong" → to "here is what probably caused it, why we think so, and the evidence supporting that conclusion."**
