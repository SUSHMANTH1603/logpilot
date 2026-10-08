# LogPilot — Product Requirements Document

**Product:** LogPilot
**Working Title:** LogPilot: An Intelligent Observability and Root Cause Analysis Platform
**Document:** D01 — Product Requirements Document
**Status:** Draft for Architecture Review
**Version:** 0.1
**Primary Audience:** Development, AI/ML, Architecture, Research
**Target:** V1 Final-Year Project + Research-Ready Product Foundation

---

# 1. Product Vision

LogPilot is a developer-first observability and incident investigation platform that continuously analyzes application runtime behavior, repository context, Git changes, service relationships, and historical incidents to detect anomalies, correlate failures, identify probable root causes, and provide evidence-backed investigation guidance.

The primary goal is to reduce the time and effort developers and engineering teams spend manually connecting information across logs, source code, configuration, Git history, and previous incidents.

LogPilot should help answer:

> **What happened? Why did it probably happen? What evidence supports that conclusion? What should I investigate next?**

LogPilot does not replace human engineering judgment.

---

# 2. Product Positioning

LogPilot is an intelligent incident investigation layer that complements existing observability infrastructure.

Traditional observability systems primarily provide:

- log collection
- storage
- search
- dashboards
- metrics
- alerts
- traces

LogPilot adds:

- anomaly interpretation
- incident correlation
- repository-aware investigation
- Git-change correlation
- historical incident retrieval
- evidence-based root-cause ranking
- contextual explanations
- recommended investigation steps

LogPilot is not intended to replace systems such as Datadog, Splunk, Grafana, Elastic, or similar platforms.

---

# 3. Problem Statement

When an application fails, engineers frequently need to manually correlate information from multiple sources:

- runtime logs
- monitoring systems
- source code
- configuration
- dependencies
- deployment information
- Git history
- previous incidents
- documentation
- runbooks

The investigation process is therefore fragmented and highly dependent on human experience.

The core problem is:

> **Runtime signals contain evidence about failures, but that evidence is distributed across operational and development context that engineers must manually connect.**

LogPilot aims to automate this correlation while preserving evidence and uncertainty.

---

# 4. Target Users

## 4.1 Primary — Developers

Developers use LogPilot while working inside VS Code.

Primary needs:

- detect failures quickly
- understand incidents without switching between multiple tools
- find relevant source code
- understand probable root causes
- inspect recent code/configuration changes
- retrieve similar historical incidents
- receive actionable investigation guidance

## 4.2 Secondary — DevOps / SRE

Needs:

- incident visibility
- service impact
- anomaly information
- incident timelines
- historical patterns
- investigation evidence
- operational context

## 4.3 Tertiary — Engineering Teams

Needs:

- incident history
- recurring failure analysis
- reliability insights
- investigation records
- knowledge reuse

## 4.4 Future — Security / Operations

Security and operations workflows are future expansion areas and are not primary V1 workflows.

---

# 5. Product Interfaces

LogPilot has two first-class interfaces.

## 5.1 VS Code Extension

Primary developer interface.

Responsibilities include:

- project connection
- monitoring controls
- incident notifications
- incident investigation
- probable root-cause display
- evidence display
- relevant repository locations
- Git context
- recommendations
- manual investigation

## 5.2 Web Dashboard

Primary team/operations interface.

Responsibilities include:

- incident overview
- incident details
- live logs
- services
- repository information
- historical incidents
- search
- analytics
- configuration
- AI provider settings
- project management

The exact navigation and visual design remain TBD and will be defined during UX/design planning.

---

# 6. Primary User Journey

The primary developer workflow is:

1. Developer opens a repository in VS Code.
2. LogPilot detects the project.
3. Developer connects/selects a LogPilot project.
4. Developer starts monitoring.
5. Local LogPilot Agent discovers repository information.
6. Configured/discovered log sources begin streaming.
7. Logs are parsed and normalized.
8. LogPilot establishes or updates runtime baselines.
9. Anomalous behavior is detected.
10. Related anomalous events are correlated.
11. LogPilot determines whether the event group is a high-confidence incident or a potential incident.
12. Evidence is gathered.
13. Candidate root causes are generated and ranked.
14. Relevant repository, Git, historical, and documentation context is retrieved.
15. The LLM generates a structured, evidence-backed explanation.
16. The developer receives an incident notification.
17. The developer investigates using VS Code or the dashboard.
18. The incident is marked resolved or ignored.

---

# 7. Core Product Intelligence Model

LogPilot combines three primary intelligence sources.

## 7.1 Log Intelligence

Runtime behavior:

- errors
- warnings
- stack traces
- log templates
- event frequencies
- temporal patterns
- anomaly scores
- service behavior

## 7.2 Repository Intelligence

Development context:

- source code
- configuration
- dependencies
- project structure
- Docker configuration
- service relationships
- documentation
- Git history

## 7.3 Historical Intelligence

Organizational knowledge:

- previous incidents
- previous resolutions
- runbooks
- troubleshooting documentation
- known failure patterns

These sources are combined for incident investigation.

---

# 8. Core Product Workflow

The conceptual processing pipeline is:

Application
→ Log Source
→ Collection
→ Parsing
→ Normalization
→ Template Extraction
→ Feature Extraction
→ Anomaly Detection
→ Incident Correlation
→ Evidence Collection
→ Candidate Cause Ranking
→ Retrieval / RAG
→ LLM Explanation
→ Incident
→ VS Code / Dashboard

This represents the product workflow and does not prescribe every implementation detail.

---

# 9. Log Ingestion Requirements

## FR-LOG-001 — Manual Log Analysis

The system shall allow users to submit/paste logs for analysis without requiring continuous monitoring.

## FR-LOG-002 — Local File Monitoring

V1 shall support monitoring application log files through the local agent.

## FR-LOG-003 — Docker Log Monitoring

V1 shall support ingestion of logs from Docker-based applications.

## FR-LOG-004 — OpenTelemetry Integration

V1 shall provide an OpenTelemetry-compatible ingestion path.

## FR-LOG-005 — Adapter Architecture

Log sources shall be abstracted behind an ingestion adapter interface so future sources can be added without redesigning the processing pipeline.

Future candidates include:

- Kubernetes
- Loki
- ELK/Elastic
- CloudWatch
- Datadog
- other cloud/platform sources

These are not required for V1.

## FR-LOG-006 — Log Normalization

Different input formats shall be normalized into a canonical internal representation.

## FR-LOG-007 — Raw Data Preservation

Where appropriate, the original/raw log content shall be retained alongside normalized information for investigation and debugging.

---

# 10. Log Processing Requirements

## FR-PROC-001 — Parsing

The system shall parse supported structured and unstructured logs.

## FR-PROC-002 — Severity Extraction

The system shall identify severity levels where available.

## FR-PROC-003 — Timestamp Extraction

The system shall normalize timestamps.

## FR-PROC-004 — Service Identification

The system shall associate events with services where sufficient information exists.

## FR-PROC-005 — Template Extraction

Repeated log patterns should be represented as reusable log templates/features.

## FR-PROC-006 — Feature Extraction

The processing pipeline shall generate features useful for anomaly detection and incident correlation.

Candidate features include:

- error rate
- warning rate
- event rate
- latency
- unique error count
- template frequency
- service failure ratio

The final feature set is TBD and will be established during ML architecture design.

---

# 11. Anomaly Detection Requirements

## FR-ML-001 — Runtime Baseline

The system shall establish a baseline of normal application behavior where sufficient historical/runtime data exists.

## FR-ML-002 — Anomaly Detection

The system shall detect statistically or algorithmically unusual runtime behavior.

## FR-ML-003 — Anomaly Score

Detected anomalies shall have an associated score or confidence measure.

## FR-ML-004 — Model Abstraction

The anomaly detection subsystem shall allow models to be replaced or compared without redesigning the entire ingestion pipeline.

## FR-ML-005 — Baseline Model

A statistical baseline and Isolation Forest are intended as initial approaches.

The final model selection and feature configuration will be defined in D08.

---

# 12. Incident Detection and Correlation

An individual anomalous log event is not necessarily an incident.

LogPilot shall correlate related anomalies and events into meaningful investigation units.

## FR-INC-001 — Event Correlation

The system shall correlate related events using signals such as:

- temporal proximity
- service relationships
- semantic similarity
- request/trace context where available
- anomaly strength
- error relationships

## FR-INC-002 — Incident Creation

The system shall create an incident when the evidence exceeds a configurable/calibrated confidence threshold.

## FR-INC-003 — Potential Incident

Lower-confidence event groups shall be represented as potential incidents or equivalent investigation candidates rather than necessarily becoming confirmed incidents.

## FR-INC-004 — Hybrid Incident Strategy

V1 shall use a hybrid strategy:

- high-confidence events → automatic incident creation
- lower-confidence events → potential incident / human review

Thresholds shall not be hard-coded arbitrarily and will be calibrated through evaluation.

## FR-INC-005 — Incident Severity

Incidents shall have a severity classification.

The exact severity model and levels are TBD.

## FR-INC-006 — Incident Timeline

Each incident shall maintain a chronological timeline of relevant events and evidence.

---

# 13. Incident Lifecycle

The initial lifecycle shall support:

- DETECTED
- INVESTIGATING
- RESOLVED
- IGNORED

Conceptually:

DETECTED
→ INVESTIGATING
→ RESOLVED

or:

DETECTED
→ IGNORED

Additional states may be introduced if required by the final domain model.

---

# 14. Incident Details Requirements

An incident shall provide a consolidated investigation view.

At minimum, the incident view should expose:

- incident title/summary
- severity
- status
- start/end time
- affected services
- relevant logs/events
- timeline
- anomaly information
- probable root cause(s)
- confidence/score
- supporting evidence
- relevant repository files
- relevant Git changes
- similar historical incidents
- recommended investigation steps
- uncertainty information

---

# 15. Repository Intelligence Requirements

## FR-REPO-001 — Repository Discovery

The local agent shall be able to inspect a connected repository.

## FR-REPO-002 — Project Detection

The system should identify relevant languages/frameworks/dependencies where possible.

## FR-REPO-003 — Source Retrieval

The system shall be able to retrieve relevant source-code context for incident investigation.

## FR-REPO-004 — Configuration Retrieval

Configuration files shall be treated as a distinct and important source of evidence.

## FR-REPO-005 — Repository Metadata

Indexed repository information should retain metadata such as:

- repository
- project
- file path
- language
- symbol where available
- line range where available
- version/commit

## FR-REPO-006 — Repository Exclusions

The scanner shall support default and configurable exclusions.

Examples include:

- `.env*`
- `*.pem`
- `*.key`
- credential files
- secret files
- `node_modules/`
- `.git/`
- `dist/`
- `build/`

## FR-REPO-007 — Custom Ignore Rules

A configurable `.logpilotignore` mechanism shall be supported.

---

# 16. Git Intelligence Requirements

## FR-GIT-001 — Git Detection

The local agent shall detect Git repositories where available.

## FR-GIT-002 — Commit Context

The system shall collect relevant commit metadata.

## FR-GIT-003 — Changed Files

The system shall identify files changed by relevant commits.

## FR-GIT-004 — Incident Correlation

Recent changes may be surfaced as potential evidence during incident investigation.

## FR-GIT-005 — Evidence, Not Proof

Git correlation shall not automatically be treated as proof of causation.

The system must communicate it as a contributing/evidentiary signal.

---

# 17. Historical Intelligence Requirements

The system shall support retrieval of:

- historical incidents
- previous resolutions
- troubleshooting documentation
- runbooks
- relevant technical documentation

Historical information shall be used as contextual evidence rather than assumed truth.

---

# 18. Root Cause Analysis Requirements

RCA is a core intelligence capability.

## FR-RCA-001 — Candidate Causes

The system shall identify candidate root causes using available evidence.

## FR-RCA-002 — Evidence Ranking

Candidate causes shall be ranked using multiple evidence signals.

Potential signals include:

- temporal precedence
- anomaly strength
- dependency impact
- error correlation
- service relationships
- repository evidence
- Git correlation
- historical similarity

## FR-RCA-003 — Probable Root Cause

The system shall present the leading candidate as a **probable root cause**, not guaranteed truth.

## FR-RCA-004 — Confidence/Score

The system shall expose a confidence or evidence score.

The interpretation/calibration of this score is TBD.

## FR-RCA-005 — Evidence Attribution

The system shall show evidence supporting the RCA where possible.

## FR-RCA-006 — Uncertainty

The system shall communicate uncertainty when evidence is weak, conflicting, or insufficient.

---

# 19. RAG Requirements

The retrieval subsystem shall provide contextual evidence to the RCA/LLM pipeline.

Knowledge sources include:

- repository
- configuration
- documentation
- historical incidents
- runbooks
- Git information

The retrieval architecture is expected to evolve through:

1. dense retrieval
2. metadata filtering
3. hybrid retrieval
4. reranking

Exact retrieval technologies, chunking strategy, embedding model and reranker are defined in D09.

---

# 20. LLM Requirements

## FR-LLM-001 — Provider Abstraction

The application shall not depend directly on a single LLM provider.

## FR-LLM-002 — Local Inference

V1 shall support Ollama/local inference.

## FR-LLM-003 — Cloud Inference

The architecture shall support a cloud LLM provider.

The initial cloud provider is TBD.

## FR-LLM-004 — Structured Output

LLM responses shall use structured output wherever possible.

## FR-LLM-005 — Evidence Grounding

The LLM shall receive selected evidence/context rather than unrestricted repository contents.

## FR-LLM-006 — No LLM-Only RCA

The LLM shall not be the sole mechanism determining root cause.

## FR-LLM-007 — Explanation

The LLM shall convert ranked evidence into an understandable incident explanation.

## FR-LLM-008 — Recommendations

The LLM may generate recommended investigation steps based on available evidence.

## FR-LLM-009 — No Autonomous Production Changes

V1 shall not autonomously modify production code, infrastructure, configuration, or systems.

---

# 21. VS Code Requirements

The VS Code extension shall support:

## FR-VSCODE-001

Connect/select a LogPilot project.

## FR-VSCODE-002

Start and stop monitoring.

## FR-VSCODE-003

Display incident notifications.

## FR-VSCODE-004

Open incident investigation views.

## FR-VSCODE-005

Display probable root cause and evidence.

## FR-VSCODE-006

Navigate to relevant repository files.

## FR-VSCODE-007

Display relevant Git context.

## FR-VSCODE-008

Display similar incidents.

## FR-VSCODE-009

Support manual investigation.

## FR-VSCODE-010

Display recommended investigation steps.

The exact extension UI structure is TBD.

---

# 22. Web Dashboard Requirements

The dashboard shall provide at least:

- overview
- incidents
- incident details
- live logs
- services
- repository context
- historical incidents
- search
- project settings
- AI provider configuration

The exact information architecture and visual design are TBD.

---

# 23. Local Agent Requirements

The local agent is responsible for local development-environment interaction.

Expected responsibilities:

- repository discovery
- repository scanning
- log collection
- local file watching
- Git metadata collection
- secret filtering
- communication with backend
- local Ollama integration where appropriate
- local configuration

Heavy centralized ML/business processing should remain in the backend/workers unless explicitly decided otherwise.

---

# 24. Security and Privacy Requirements

## SEC-001 — Secret Protection

The system shall attempt to prevent secrets from being sent to AI systems.

## SEC-002 — Repository Filtering

Sensitive and irrelevant repository files shall be excluded according to default and user-configurable rules.

## SEC-003 — Context Minimization

The system shall avoid sending an entire repository to an LLM by default.

## SEC-004 — Authentication

Authenticated access shall be required for protected backend resources.

The exact authentication implementation is TBD.

## SEC-005 — Authorization

Users shall only access projects/resources for which they have permission.

## SEC-006 — Project Isolation

V1 shall provide project-level data isolation.

## SEC-007 — Auditability

Security-sensitive operations should be auditable.

## SEC-008 — Secure Deployment

Production deployments shall use secure transport and secure secret/configuration management.

---

# 25. Multi-Tenancy Requirements

V1 shall support project-level isolation.

The architecture should remain compatible with future:

Organization
→ Teams
→ Projects
→ Repositories
→ Services

The detailed organization/RBAC model is TBD.

---

# 26. Non-Functional Requirements

## NFR-001 — Reliability

Failures in individual processing stages should not unnecessarily bring down the entire platform.

## NFR-002 — Extensibility

New log sources, ML models, retrieval strategies and LLM providers should be addable without rewriting unrelated components.

## NFR-003 — Testability

Major components must have automated tests appropriate to their responsibility.

## NFR-004 — Observability

LogPilot itself shall expose operational telemetry such as:

- API latency
- worker latency
- ingestion latency
- processing latency
- retrieval latency
- LLM latency
- error rates
- queue health

## NFR-005 — Reproducibility

Development and evaluation environments should be reproducible.

## NFR-006 — Maintainability

The codebase shall use clear module boundaries, documented architectural decisions and defined engineering standards.

## NFR-007 — Security

Security shall be considered throughout development rather than added only before deployment.

## NFR-008 — Evaluation

ML and AI capabilities shall have measurable evaluation procedures.

## NFR-009 — Human Oversight

The system shall communicate uncertainty and avoid representing AI-generated RCA as guaranteed truth.

Specific numerical latency/availability/scalability targets are TBD and will be established after baseline implementation and measurement.

---

# 27. Testing Requirements

The product shall support multiple testing layers.

## Software

- unit tests
- integration tests
- API tests
- end-to-end tests

## ML

- dataset validation
- model evaluation
- regression tests

## Retrieval

- retrieval evaluation
- ranking evaluation

## LLM

- correctness
- relevance
- groundedness
- evidence attribution

## VS Code

- extension tests
- integration tests

## System

At least one complete controlled incident scenario shall eventually test:

application
→ logs
→ anomaly
→ incident
→ RCA
→ dashboard
→ VS Code

---

# 28. Research Requirements

Research must be considered from the beginning.

## Research Question

The primary research direction is:

> Can combining runtime anomaly signals, repository context, and historical incident retrieval improve automated root-cause identification compared with log-only approaches?

Potential experimental comparisons:

### Experiment A

Statistical baseline vs Isolation Forest.

### Experiment B

Dense vs sparse vs hybrid retrieval.

### Experiment C

Hybrid retrieval vs hybrid + reranking.

### Experiment D

Log-only RCA vs log + repository context.

### Experiment E

Log + repository vs log + repository + historical incidents.

### Experiment F

LLM without evidence vs evidence-grounded LLM.

Potential metrics:

- precision
- recall
- F1
- false-positive rate
- detection latency
- top-1 RCA accuracy
- top-3 RCA recall
- Recall@K
- MRR
- nDCG
- groundedness
- evidence attribution

The final research hypothesis, dataset construction and experimental methodology will be formalized in D12.

---

# 29. Research Reproducibility

For reproducibility, relevant experiments should preserve:

- dataset version
- model version
- model configuration
- embedding model
- retrieval configuration
- reranking configuration
- RCA configuration
- LLM/provider configuration
- prompts where applicable
- results
- evaluation metrics

The precise experiment-tracking implementation will be defined later.

---

# 30. V1 Scope

V1 is intended to provide a complete vertical product experience consisting of:

### Ingestion

- manual logs
- local files
- Docker
- OpenTelemetry

### Intelligence

- parsing
- normalization
- log templates
- runtime baselines
- anomaly detection
- incident correlation
- hybrid incident creation
- evidence collection
- probable RCA
- recommendations

### Context

- repository intelligence
- Git intelligence
- historical incident retrieval
- documentation/runbook retrieval

### AI

- embeddings
- retrieval
- evidence-based RCA
- Ollama
- cloud LLM abstraction
- structured outputs

### Interfaces

- VS Code extension
- web dashboard

### Engineering

- PostgreSQL
- Redis
- Qdrant
- Docker
- CI/CD
- automated testing
- observability
- evaluation framework

---

# 31. Explicit V1 Non-Goals

The following are explicitly outside V1 unless later approved:

- autonomous production remediation
- autonomous code modification
- mobile applications
- browser extensions
- Slack/Teams integrations
- enterprise billing
- enterprise SSO
- multi-region deployment
- Kubernetes-first infrastructure
- large-scale Kafka/NATS infrastructure without demonstrated need
- dozens of log integrations
- custom foundation model training
- large-scale LLM fine-tuning
- multi-agent architecture
- replacement of established observability platforms

---

# 32. Product Principles

## Principle 1 — Evidence over Guessing

LogPilot should show why it reached a conclusion.

## Principle 2 — Probable, Not Certain

RCA should communicate uncertainty.

## Principle 3 — Human-in-the-Loop

The engineer remains responsible for the final decision.

## Principle 4 — Context Matters

Runtime logs alone are insufficient for high-quality investigation.

## Principle 5 — Privacy by Design

Repository and log data should be minimized and protected before AI processing.

## Principle 6 — Model-Agnostic Architecture

ML and LLM components should be replaceable.

## Principle 7 — Research-Ready Engineering

Important AI decisions should be measurable and reproducible.

## Principle 8 — Avoid Unnecessary Complexity

Technology should be introduced because it solves a demonstrated problem.

---

# 33. Golden Demo Acceptance Scenario

The primary end-to-end demonstration shall eventually support:

1. Start a deliberately faulty application.
2. Connect LogPilot.
3. Start monitoring.
4. Generate a controlled failure.
5. LogPilot observes the runtime behavior.
6. Anomaly detection identifies unusual behavior.
7. Related events are correlated.
8. A high-confidence incident is created.
9. Incident timeline is generated.
10. Probable root cause is ranked.
11. Relevant repository code/configuration is retrieved.
12. Relevant Git change is identified where applicable.
13. Similar historical incident is retrieved where available.
14. Evidence is presented.
15. LLM generates a grounded explanation.
16. Recommended investigation steps are shown.
17. Incident is visible in the dashboard.
18. Incident is accessible from VS Code.
19. Engineer can mark the incident resolved/ignored.

This scenario is the primary product integration target.

---

# 34. Success Criteria

V1 will be considered product-complete when the golden demo scenario works reliably on controlled test applications and the required functional, security, testing and evaluation requirements have been satisfied.

Numerical targets for:

- detection latency
- RCA accuracy
- retrieval quality
- false-positive rate
- system throughput
- availability

will be defined after baseline implementation and evaluation.

---

# 35. Future Direction

Potential future capabilities include:

- Kubernetes integration
- cloud log integrations
- Loki/Elastic integrations
- GitHub/GitLab integration
- collaboration integrations
- enterprise authentication
- RBAC
- advanced service topology
- automated remediation suggestions
- optional code patch generation
- production cloud deployment
- advanced incident analytics
- additional ML models
- advanced research experiments

These are not V1 requirements.

---

# 36. Open/TBD Items

The following intentionally remain undecided at the PRD stage:

- exact authentication mechanism
- exact cloud LLM provider
- exact embedding model
- exact reranker
- exact async worker framework
- exact anomaly feature set
- anomaly thresholds
- severity model
- RCA scoring formula
- database schema
- API endpoint design
- WebSocket contract
- repository chunking strategy
- Qdrant collection design
- exact dashboard information architecture
- exact VS Code UI
- numerical latency targets
- numerical availability targets
- evaluation dataset composition
- final research hypothesis
- deployment/cloud provider
- detailed organization/RBAC model

These decisions will be made in subsequent Phase 0 artifacts.

---

# 37. Requirements Traceability

The following requirement groups will be traced into later architecture and implementation artifacts:

| Requirement Area | Future Artifact |
|---|---|
| Product scope | D02 |
| System architecture | D03 |
| Repository structure | D04 |
| Domain/database | D05 |
| API contracts | D06 |
| Event/log schema | D07 |
| ML/RCA | D08 |
| Retrieval/RAG | D09 |
| LLM | D10 |
| Security | D11 |
| Evaluation/research | D12 |

No implementation should knowingly violate an approved requirement without an explicit architectural/product decision.

---

# 38. Document Status

This document represents the proposed **D01 product baseline**.

It becomes the authoritative product requirements document only after review and approval.

Subsequent architecture documents shall refine implementation details without silently changing product requirements.

Any requirement change after approval shall be documented through an appropriate change/decision process.
