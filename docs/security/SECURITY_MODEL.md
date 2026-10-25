# LogPilot — Security Model

**Document ID:** D11
**Status:** Draft for Architecture Review
**Parent Documents:** [D01 — Product Requirements Document](../requirements/PRD.md), [D02 — V1 Scope & Acceptance Criteria](../requirements/V1_SCOPE.md), [D03 — System Architecture Document](../architecture/SYSTEM_ARCHITECTURE.md), [D04 — Repository Architecture Document](../architecture/REPOSITORY_ARCHITECTURE.md), [D05 — Database & Domain Model Document](../architecture/DATABASE_DOMAIN_MODEL.md), [D06 — API Contracts & Interface Definitions](../api/API_CONTRACTS.md), [D07 — Event & Log Schema Specification](../architecture/EVENT_LOG_SCHEMA.md), [D08 — ML & RCA Architecture](../architecture/ML_RCA_ARCHITECTURE.md), [D09 — RAG Architecture](../architecture/RAG_ARCHITECTURE.md), [D10 — LLM Architecture](../architecture/LLM_ARCHITECTURE.md), [ADR-006](../adr/adr-006-repository-intelligence-and-secret-redaction.md), [ADR-007](../adr/adr-007-local-agent-architecture.md), [ADR-008](../adr/adr-008-multi-tenancy-strategy.md)
**Project:** LogPilot: An Intelligent Observability and Root Cause Analysis Platform

---

## 1. Purpose, Scope, Audience, and Security Objectives

### 1.1. Purpose
This document establishes the comprehensive, implementation-oriented Security Model for LogPilot. It defines the security boundaries, data classification rules, threat models, isolation safeguards, and failure modes across all software components: the local developer agent, API gateway, background workers, analytical machine learning engines, vector index, and Large Language Model (LLM) explanation pipeline.

Observability and root-cause analysis platforms represent uniquely high-value security targets:
1. They ingest runtime telemetry and stack traces that can inadvertently contain database credentials, user session tokens, and personal data.
2. They scan application repositories, Git commit diffs, and container definitions that expose proprietary business logic and internal architectural topology.
3. They integrate Large Language Models to synthesize forensic narratives, introducing novel generative failure modes such as prompt injection, secret exfiltration, and hallucinatory misdirection.

The LogPilot Security Model bridges these requirements by establishing concrete, auditable trust boundaries, least-privilege containment barriers, and defensive sanitization pipelines without relying on unverifiable security guarantees.

### 1.2. Scope
The scope of D11 encompasses the entire LogPilot platform as defined in [D01](../requirements/PRD.md) through [D10](../architecture/LLM_ARCHITECTURE.md):
- **Local Developer Workstation:** The Local Agent (`agent/logpilot-agent/`), VS Code Extension, local Git repository access, local log file reading, container log streams, and local Ollama inference ([ADR-007](../adr/adr-007-local-agent-architecture.md)).
- **Backend Application Core:** The FastAPI modular monolith (`apps/api`), Celery/Redis background task queues (`apps/workers`), domain packages (`packages/db`, `packages/ml`, `packages/rag`, `packages/llm`), and local/hosted service communication ([D04](../architecture/REPOSITORY_ARCHITECTURE.md)).
- **Persistence & Analytical Stores:** PostgreSQL (the sole authoritative relational store of record), Redis (in-memory queues and rolling feature buffers), and Qdrant (derived, sensitive, rebuildable retrieval index).
- **External Interfaces:** External log ingestion pipelines, developer REST APIs, and third-party hosted model provider gateways.

### 1.3. Audience
This specification is written for:
- **Backend & Platform Engineers:** Implementing API authentication middleware, database multi-tenant scoping, Celery task workers, and pre-ingress sanitization filters.
- **DevOps & Infrastructure Engineers:** Hardening PostgreSQL, Redis, Qdrant, Docker runtime configurations, and network isolation boundaries.
- **Security Auditors & Application Security Teams:** Evaluating LogPilot's threat surface, prompt-injection resilience, data privacy guarantees, and RBAC enforcement.
- **Extension & Agent Developers:** Building secure local filesystem adapters, `.logpilotignore` parsers, and IPC communication channels.

### 1.4. Security Objectives
The LogPilot platform enforces six primary security objectives:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       LOGPILOT CORE SECURITY OBJECTIVES                     │
├─────────────────────┬───────────────────────────────────────────────────────┤
│ Objective           │ Operational Definition                                │
├─────────────────────┼───────────────────────────────────────────────────────┤
│ 1. Relational       │ Zero cross-project data leakage. Access to all        │
│    Isolation        │ telemetry, evidence, candidates, and explanations is  │
│                     │ authoritatively constrained by validated project_id.  │
├─────────────────────┼───────────────────────────────────────────────────────┤
│ 2. Pre-Ingress      │ Prevent secrets, API keys, JWTs, and connection       │
│    Sanitization     │ strings from entering downstream vector stores or LLM │
│                     │ context windows via defense-in-depth masking.         │
├─────────────────────┼───────────────────────────────────────────────────────┤
│ 3. Untrusted Data   │ All logs, source code, commits, and diffs are treated │
│    Containment      │ as untrusted data; evidence can inform diagnostic     │
│                     │ synthesis but can never execute code or mutate state. │
├─────────────────────┼───────────────────────────────────────────────────────┤
│ 4. Least Privilege  │ Neither the local agent nor the generative LLM has    │
│    Execution        │ write access to production infrastructure, codebase   │
│                     │ files, or authoritative PostgreSQL lifecycle states.  │
├─────────────────────┼───────────────────────────────────────────────────────┤
│ 5. Analytical       │ Analytical ML models and generative LLMs produce      │
│    Honesty          │ assistive guidance, citing authentic evidence IDs     │
│                     │ without masquerading as autonomous truth authorities. │
├─────────────────────┼───────────────────────────────────────────────────────┤
│ 6. Graceful Fault   │ Security scanner, vector database, or LLM failures    │
│    Containment      │ fail safely without exposing sensitive data, crashing │
│                     │ the API, or corrupting underlying incident records.   │
└─────────────────────┴───────────────────────────────────────────────────────┘
```

---

## 2. Security Principles and Non-Goals

### 2.1. Foundational Security Principles
1. **Defense-in-Depth:** No single control (such as `.logpilotignore`, regex scrubbing, or prompt delimiters) is treated as a security panacea. Security emerges from layered, redundant controls operating at ingestion, retrieval, prompt assembly, and output validation.
2. **PostgreSQL as Sole Authority:** PostgreSQL is the single authoritative system of record for all user identities, project permissions, incident states, and audit trails ([D05](../architecture/DATABASE_DOMAIN_MODEL.md)). Vector stores (Qdrant) and caches (Redis) are derived, rebuildable retrieval and state caches and must never be trusted for authoritative authorization.
3. **Fail-Closed Authorization:** If project membership cannot be relationally verified, the system defaults to denial. API queries for non-existent or unauthorized resources return uniform HTTP `404 Not Found` to prevent project enumeration ([D06 § 4.3](../api/API_CONTRACTS.md)).
4. **Untrusted Evidence Boundary:** Telemetry records and repository artifacts are untrusted forensic inputs. They are strictly compartmentalized and parsed via deterministic schemas rather than executed.
5. **Human-in-the-Loop Assistive Oversight:** In strict adherence to [D02](../requirements/V1_SCOPE.md), LogPilot does not execute autonomous production remediation, automated Pull Request merges, or unmonitored server restarts. The system assists human engineers who maintain full operational agency.

### 2.2. Explicit Non-Goals
To prevent unrealistic expectations and maintain technical honesty, LogPilot explicitly declares the following non-goals:
- **Zero-Day Vulnerability Scanning:** LogPilot is an incident investigation platform, not an enterprise static application security testing (SAST) or dynamic analysis (DAST) scanner.
- **Guaranteed Universal Secret Redaction:** Regex and entropy masking dramatically reduce credential leakage, but no automated redaction system can mathematically guarantee detection of 100% of bespoke, encrypted, or novel token formats.
- **Complete Prompt-Injection Immunity:** Data delimiters and JSON schema constraints contain prompt injections within data channels, but LLM parsing engines remain inherently probabilistic. Complete mathematical immunity to prompt injection is an unsolved research problem and is explicitly not guaranteed.
- **Autonomous Infrastructure Remediation:** The platform will not modify infrastructure configurations, apply cloud IAM policies, or restart production services without human initiation.
- **Enterprise Identity Federation (V1):** SAML 2.0, Okta, and complex multi-region identity meshes are excluded from the V1 scope ([D02](../requirements/V1_SCOPE.md)) and remain tracked under downstream roadmap decisions.

---

## 3. Assets and Sensitive Data Classification

To establish appropriate technical safeguards, LogPilot categorizes all system data into five distinct sensitivity tiers:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LOGPILOT DATA CLASSIFICATION MATRIX                      │
├───────┬───────────────────────────────┬─────────────────────┬───────────────┤
│ Tier  │ Asset Description             │ Storage Location    │ Baseline      │
│       │                               │                     │ Controls      │
├───────┼───────────────────────────────┼─────────────────────┼───────────────┤
│ **1** │ **Authentication & Secrets**  │ PostgreSQL,         │ Hashed/Salted │
│ High  │ Password hashes, API keys,    │ Environment Vars    │ (Candidate    │
│ Risk  │ provider tokens, DB password  │                     │ algorithms),  │
│       │                               │                     │ TLS in transit│
├───────┼───────────────────────────────┼─────────────────────┼───────────────┤
│ **2** │ **Forensic Telemetry & Code** │ PostgreSQL, Redis,  │ Pre-ingress   │
│ High  │ Raw log payloads, stack traces,│ Qdrant, Developer   │ redaction,    │
│ Risk  │ source chunks, Git diffs      │ Workstation         │ project RBAC  │
├───────┼───────────────────────────────┼─────────────────────┼───────────────┤
│ **3** │ **Derived Intelligence**      │ PostgreSQL, Qdrant, │ Relational FK,│
│ Med   │ Normalized templates, vectors,│ Background Workers  │ tenant payload│
│ Risk  │ embeddings, anomaly scores    │                     │ filters       │
├───────┼───────────────────────────────┼─────────────────────┼───────────────┤
│ **4** │ **Synthesized Narratives**    │ PostgreSQL, API,    │ Schema checks,│
│ Med   │ RCA explanations, summaries,  │ UI / VS Code        │ citation IDs, │
│ Risk  │ recommended mitigation steps  │                     │ no raw secrets│
├───────┼───────────────────────────────┼─────────────────────┼───────────────┤
│ **5** │ **Operational & Audit Trails**│ PostgreSQL          │ Append-only   │
│ Low   │ User actions, login attempts, │ (`audit_records`)   │ application   │
│ Risk  │ API request timestamps        │                     │ pattern (D05) │
└───────┴───────────────────────────────┴─────────────────────┴───────────────┘
```

### 3.1. Detailed Asset Inventory
1. **Raw Log Records & Batches:** Unprocessed text ingested via local files, HTTP POST, or Docker container stdout/stderr. Risk: Direct presence of developer debug tokens, database passwords, and user PII.
2. **Normalized Events & Log Templates:** Tokenized, clustered event templates produced by LogMine mining ([D07](../architecture/EVENT_LOG_SCHEMA.md)). Risk: Residual tokens in variable extraction slots.
3. **Repository Source Chunks & Configs:** Targeted code snippets extracted around stack trace frames (candidate heuristic: 50–100 lines; see [D09](../architecture/RAG_ARCHITECTURE.md)). Risk: Exposure of proprietary algorithms, architectural secrets, and hardcoded certificates.
4. **Git History & Diffs:** Commit metadata, author emails, commit messages, and patch diffs temporally associated with incident windows. Risk: Historical credential exposure or malicious prompt injection embedded in commit logs.
5. **Incident Evidence Snapshots (`IncidentEvidence`):** Point-in-time forensic snapshots linked to an active `Incident` ([D05](../architecture/DATABASE_DOMAIN_MODEL.md)). Risk: Retains historical telemetry snapshots that are subject to project retention policies rather than permanent retention promises ([D07 § 5.3](../architecture/EVENT_LOG_SCHEMA.md)).
6. **Vector Embeddings (Qdrant):** High-dimensional vector representations stored in Qdrant ([D09](../architecture/RAG_ARCHITECTURE.md)). Risk: **Embeddings are derived sensitive assets.** Vector inversion techniques can reconstruct partial source text; vector stores must not be treated as benign public caches. Index retention, deletion synchronization, rebuild triggers, and point lifecycle behavior remain unresolved decisions tracked under [TBD-SEC-13].
7. **Prompt Payloads:** Assembled context strings containing system instructions, metadata, and untrusted evidence sent to LLM runtimes. Risk: Accidental leakage across public internet APIs or third-party training pipelines.
8. **Model Explanation Artifacts (`RCAExplanation`):** Structured JSON outputs containing root-cause narratives, causal chains, and investigation recommendations ([D10](../architecture/LLM_ARCHITECTURE.md)). Risk: Hallucinated diagnostic advice, prompt injection reflection, or misleading remediation steps.
9. **Platform Credentials & Secrets:** PostgreSQL database passwords, Redis authentication tokens, Qdrant API keys, platform encryption keys, and hosted LLM API keys. Risk: Total platform compromise.
10. **Audit Records (`audit_records`):** Operational audit trail capturing security-sensitive actions in the `audit_records` table ([D05 § 8.18](../architecture/DATABASE_DOMAIN_MODEL.md)). Application database users lack UPDATE and DELETE privileges on this table ([D05 § 10.3](../architecture/DATABASE_DOMAIN_MODEL.md)). Risk: Accidental inclusion of sensitive query parameters.

---

## 4. System Components, Trust Boundaries, and Data-Flow Overview

### 4.1. System Components & Architecture Topology
In accordance with [D03](../architecture/SYSTEM_ARCHITECTURE.md) and [D04](../architecture/REPOSITORY_ARCHITECTURE.md), LogPilot is structured as a modular monolith accompanied by a lightweight developer agent and dedicated storage engines:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 LOGPILOT TRUST BOUNDARY MAP                                 │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│  [DEVELOPER WORKSTATION: TRUST ZONE 1]                                                      │
│  ┌─────────────────────────┐     IPC / HTTP (Loopback)   ┌───────────────────────────────┐  │
│  │    VS Code Extension    │ ◄─────────────────────────► │      Local Python Agent       │  │
│  └─────────────────────────┘                             │  • .logpilotignore Filter     │  │
│               │                                          │  • Git / Log File Reader      │  │
│               │                                          └───────────────────────────────┘  │
│               │ HTTPS / WSS (Auth Token / API Key)                       │                  │
│               ▼                                                          │ Local IPC / HTTP │
│  ════════════════════════════════════════════════════════════════════════╪═════════════════ │
│  [API & INGESTION PERIMETER: TRUST ZONE 2]                               │                  │
│  ┌────────────────────────────────────────────────────────┐              ▼                  │
│  │                    FastAPI Gateway                     │   ┌──────────────────────────┐  │
│  │ • TLS Termination & Rate Limiter                       │   │   Local Ollama Daemon    │  │
│  │ • Server-Side Auth & Project RBAC Middleware           │   │   (Workstation / On-Prem)│  │
│  │ • Pre-Ingress Secret Redaction Filter (ADR-006)        │   └──────────────────────────┘  │
│  └────────────────────────────────────────────────────────┘                                 │
│               │                                      │                                      │
│               │ Task Dispatch                        │ Direct Read / Write                  │
│               ▼                                      ▼                                      │
│  ══════════════════════════════════════════════════════════════════════════════════════════ │
│  [INTERNAL PLATFORM CORE: TRUST ZONE 3]                                                     │
│  ┌─────────────────────────┐                         ┌───────────────────────────────────┐  │
│  │     Celery Workers      │                         │            PostgreSQL             │  │
│  │ • Log Normalizer        │ ◄─────────────────────► │ • SOLE System of Record           │  │
│  │ • Anomaly Detector (ML) │   Relational Queries    │ • Row-Level Project Scoping       │  │
│  │ • Algorithmic RCA Engine│   & Persistence         │ • Auth & Audit Records            │  │
│  │ • LLM Gateway Client    │                         └───────────────────────────────────┘  │
│  └─────────────────────────┘                                         ▲                      │
│         │                  │                                         │ Rebuild Index        │
│         ▼                  ▼                                         │                      │
│  ┌──────────────┐   ┌──────────────────────────┐             ┌───────────────────────────┐  │
│  │ Redis Broker │   │ Hosted Cloud LLM Gateway │             │    Qdrant Vector Store    │  │
│  │ • Job Queues │   │ (Optional SaaS Provider) │             │ • Derived, Sensitive,     │  │
│  │ • Feature Win│   │ • Enterprise Terms Policy│             │   Rebuildable Index       │  │
│  └──────────────┘   └──────────────────────────┘             └───────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2. Defined Trust Boundaries
1. **Trust Boundary 1 (Developer Workstation $\rightarrow$ Local Agent):** The developer's workstation host environment. The agent executes with user privileges, accessing only approved project repository paths and local log files ([ADR-007](../adr/adr-007-local-agent-architecture.md)).
2. **Trust Boundary 2 (External Ingress / Clients $\rightarrow$ API Gateway):** The network perimeter. All inbound telemetry and client requests cross an untrusted network boundary requiring TLS encryption, input schema validation, rate limiting, and project-level authentication ([D06](../api/API_CONTRACTS.md)).
3. **Trust Boundary 3 (API Gateway $\rightarrow$ Internal Platform Storage):** The trusted internal application perimeter. Workers and API handlers interact with PostgreSQL, Redis, and Qdrant over internal networks, authenticating via credentials managed in environment variables.
4. **Trust Boundary 4 (Platform Core $\rightarrow$ Inference Providers):** The boundary separating LogPilot from generative inference engines. This crosses either to a local loopback daemon (Ollama) or an external third-party hosted cloud provider over outbound TLS ([ADR-002](../adr/adr-002-llm-provider-abstraction.md), [D10](../architecture/LLM_ARCHITECTURE.md)).

---

## 5. Threat Model and Attacker Assumptions

### 5.1. Attacker Personas and Capabilities
To ensure realistic coverage, LogPilot defines five distinct threat actors:

1. **Attacker Persona A (Unauthenticated External Attacker):**
   - *Position:* External internet or enterprise network.
   - *Capabilities:* Can send arbitrary network traffic to public-facing API endpoints, attempt brute-force authentication, forge headers, inject malformed JSON payloads, and launch volumetric DoS attacks.
   - *Assumptions:* Possesses no valid user credentials, API keys, or database access.
2. **Attacker Persona B (Malicious / Compromised Project Contributor):**
   - *Position:* Authenticated developer within Project A.
   - *Capabilities:* Can push code to repositories, commit crafted log messages, trigger anomalies, and submit manual logs.
   - *Assumptions:* Possesses valid project role in Project A, but attempts to read Project B's telemetry, escalate privileges to `OWNER`, or inject prompt exploits into the shared LLM pipeline.
3. **Attacker Persona C (Authenticated Low-Privilege User):**
   - *Position:* Authenticated user with `VIEWER` role in Project A.
   - *Capabilities:* Can view authorized dashboards and incident explanations.
   - *Assumptions:* Attempts to perform unauthorized state-mutating actions (e.g., triggering expensive RCA explanations, modifying project settings, deleting incidents).
4. **Attacker Persona D (Compromised Third-Party Dependency or Model Provider):**
   - *Position:* Upstream open-source library, vector database plugin, or external hosted LLM provider.
   - *Capabilities:* Can return malformed payloads, attempt prompt injection reflection, experience server outages, or retain prompt text for model training.
   - *Assumptions:* Cannot directly compromise the host operating system if isolated within container boundaries.
5. **Attacker Persona E (Accidental Insider / Operational Error):**
   - *Position:* Legitimate developer or operator.
   - *Capabilities:* Accidental inclusion of `.env` files in git commits, inadvertent deployment of debug logs containing production secrets, or misconfiguration of project access tokens.

---

## 6. Threat Scenarios and Abuse Cases

The following structured threat matrix catalogues the principal attack vectors, their severity, existing documented mitigations, and residual risks:

| Threat ID | Asset & Trust Boundary | Attacker Persona | Attack Path & Mechanism | Potential Impact | Existing Architectural Mitigations | Residual Risk & Required Decisions | Related Documents |
|---|---|---|---|---|---|---|---|
| **THREAT-01** | Cross-Project Telemetry Access (Boundary 2/3) | Persona B (Malicious Contributor) | Attacker passes forged `project_id` UUID in REST URL or queries raw database records. | Data breach; Project A user views proprietary telemetry of Project B. | Mandatory server-side project authorization middleware; relational DB scoping ([D05](../architecture/DATABASE_DOMAIN_MODEL.md), [D06](../api/API_CONTRACTS.md)). | Implementation error in custom queries bypassing relational scoping. Tracked in [TBD-SEC-02]. | [D05](../architecture/DATABASE_DOMAIN_MODEL.md), [D06](../api/API_CONTRACTS.md) |
| **THREAT-02** | Vector Store Tenant Bleed (Boundary 3) | Persona B (Malicious Contributor) | Querying Qdrant embeddings without project filter, retrieving semantic chunks across projects. | Cross-tenant source code and forensic context leakage via RAG. | Mandatory payload filtering on every vector search: `project_id == active_project` ([D09](../architecture/RAG_ARCHITECTURE.md)). | Qdrant configuration error or filter omission in experimental queries. Index lifecycle tracked in [TBD-SEC-13]. | [D09](../architecture/RAG_ARCHITECTURE.md) |
| **THREAT-03** | Unauthorized Role Escalation (Boundary 2) | Persona C (Low-Privilege User) | Non-owner issues `POST` or `PUT` to administrative membership endpoints. | Unauthorized assignment of `OWNER` role; policy tampering. | Server-side authorization requiring `OWNER` role for membership and project configuration mutations ([D06 § 3.2, § 7.2](../api/API_CONTRACTS.md)). | Fine-grained operation-level permission scopes beyond baseline D06 matrix remain unresolved. Tracked in [TBD-SEC-02]. | [D05](../architecture/DATABASE_DOMAIN_MODEL.md), [D06](../api/API_CONTRACTS.md) |
| **THREAT-04** | Hardcoded Secret Leakage via Logs (Boundary 1/2) | Persona E (Accidental Operator) | Application logs unmasked database passwords or JWT tokens during exception bursts. | Credential harvesting; downstream storage of plaintext secrets. | Pre-ingress secret redaction filters ([D07](../architecture/EVENT_LOG_SCHEMA.md), [ADR-006](../adr/adr-006-repository-intelligence-and-secret-redaction.md)). | Bespoke token formats, base64-encoded secrets, or novel credentials bypass candidate pattern banks. Tracked in [TBD-SEC-03]. | [D07](../architecture/EVENT_LOG_SCHEMA.md), [ADR-006](../adr/adr-006-repository-intelligence-and-secret-redaction.md) |
| **THREAT-05** | Repository Scanning Credential Leakage (Boundary 1) | Persona E (Accidental Operator) | Local agent scans developer workspace containing uncommitted `.env` files or SSH private keys. | Private keys ingested into RAG vector index and transmitted to LLM. | Built-in exclusion lists (`.env*`, `*.pem`, `id_rsa*`) and project `.logpilotignore` ([ADR-006](../adr/adr-006-repository-intelligence-and-secret-redaction.md)). | Developer misnames secret file or disables ignore checks; active scanner false-negatives. Tracked in [TBD-SEC-03]. | [ADR-006](../adr/adr-006-repository-intelligence-and-secret-redaction.md), [ADR-007](../adr/adr-007-local-agent-architecture.md) |
| **THREAT-06** | Direct & Indirect Prompt Injection (Boundary 4) | Persona A / Persona B | Attacker embeds adversarial instructions in HTTP log headers, error strings, or Git commit messages. | Model ignores system role; emits misleading diagnosis, executes unauthorized tool calls, or leaks context. | Tiered prompt framing; untrusted data delimiters; strict JSON schema enforcement; zero tool calling privileges ([D10](../architecture/LLM_ARCHITECTURE.md)). | Delimiters and schemas reduce attack surface but do not provide mathematical immunity against subtle narrative biasing. Tracked in [TBD-SEC-09]. | [D10](../architecture/LLM_ARCHITECTURE.md) |
| **THREAT-07** | Hallucinated / Fabricated RCA Citations (Boundary 4) | Persona D (Model Provider) | Stochastic LLM fabricates non-existent root-cause candidates or invents phantom evidence UUIDs. | Developer takes destructive actions based on false diagnostic claims. | Post-generation citation allowlist validation; strict grounding invariant ([D10](../architecture/LLM_ARCHITECTURE.md)). | Sophisticated hallucinations that cite authentic UUIDs but make unsupported claims. Tracked in [TBD-SEC-09]. | [D08](../architecture/ML_RCA_ARCHITECTURE.md), [D10](../architecture/LLM_ARCHITECTURE.md) |
| **THREAT-08** | Ingestion Parser & Memory Exhaustion (Boundary 2) | Persona A (External Attacker) | Attacker transmits oversized log batches or deeply nested JSON structures to ingestion API. | Worker thread starvation; memory exhaustion (OOM crash); Denial of Service. | Candidate payload size limits; streaming parser validation; Celery task queue isolation ([D06](../api/API_CONTRACTS.md), [D07](../architecture/EVENT_LOG_SCHEMA.md)). | Concrete operational payload ceilings and rate limits remain unresolved. Tracked in [TBD-SEC-04], [TBD-SEC-07]. | [D06](../api/API_CONTRACTS.md), [D07](../architecture/EVENT_LOG_SCHEMA.md) |
| **THREAT-09** | Replay & Telemetry Forgery (Boundary 2) | Persona B (Malicious Contributor) | Attacker replays valid historical log payloads with modified timestamps or forged service names. | False anomaly spikes; synthetic incident generation; triage pollution. | Source metadata validation; mandatory `project_id` association; server-assigned ingestion timestamps ([D07](../architecture/EVENT_LOG_SCHEMA.md)). | Lack of cryptographic log signing allows local network actors to forge source tags. Tracked in [TBD-SEC-01]. | [D07](../architecture/EVENT_LOG_SCHEMA.md) |
| **THREAT-10** | Unencrypted Internal Network Interception (Boundary 3) | Persona A (Network Tap) | Attacker taps internal Docker or host network traffic between API and Redis/PostgreSQL. | Plaintext telemetry and credential interception in transit. | Candidate network isolation and TLS encryption recommendations ([D03](../architecture/SYSTEM_ARCHITECTURE.md)). | Development/testing environments may use plaintext internal networking. Tracked in [TBD-SEC-05]. | [D03](../architecture/SYSTEM_ARCHITECTURE.md) |
| **THREAT-11** | Hosted LLM Provider Data Snooping (Boundary 4) | Persona D (Cloud Provider) | Telemetry and code snippets transmitted to external SaaS LLM used for public model training. | Intellectual property loss; non-compliance with data privacy mandates. | Architectural support for privacy-preserving local Ollama inference; configurable cloud provider abstraction ([D10](../architecture/LLM_ARCHITECTURE.md)). | Using hosted cloud APIs without verified zero-retention enterprise agreements. Tracked in [TBD-SEC-09]. | [ADR-002](../adr/adr-002-llm-provider-abstraction.md), [D10](../architecture/LLM_ARCHITECTURE.md) |
| **THREAT-12** | Audit Record Tampering (Boundary 3) | Persona B / Insider | Malicious actor attempts to delete or alter `audit_records` to conceal unauthorized triage actions. | Loss of forensic accountability; compromised compliance. | Application-level append-only enforcement; application database user lacks UPDATE and DELETE privileges ([D05 § 10.3](../architecture/DATABASE_DOMAIN_MODEL.md)). | Database administrator with raw PostgreSQL access can modify rows without hardware WORM or cryptographic hash chains. Tracked in [TBD-SEC-08]. | [D05](../architecture/DATABASE_DOMAIN_MODEL.md) |

---

## 7. Authentication and Authorization Boundaries

### 7.1. Authentication Architecture
In accordance with [D05](../architecture/DATABASE_DOMAIN_MODEL.md) and [D06](../api/API_CONTRACTS.md), LogPilot supports dual authentication mechanisms:

1. **User Session Authentication:**
   - Used by Web Dashboard and VS Code Extension users.
   - Transmitted via standard HTTP Header: `Authorization: Bearer <session_or_jwt_token>`.
   - Maps directly to an authenticated `User.id` in PostgreSQL.
2. **API Key Authentication (Ingestion & Telemetry Shippers):**
   - Used by automated ingestion pipelines, CI/CD runners, and local background daemons.
   - Transmitted via header: `X-LogPilot-Source-Key: <key>` in accordance with [D06 § 3.1](../api/API_CONTRACTS.md).
   - Keys are associated with a specific source or project context. While D05 defines domain entities like `log_sources`, dedicated database table definitions for API keys and tokens are not frozen in D05 and remain subject to detailed implementation design.
   - **Storage Requirement:** API keys must **never be stored in plaintext**. The database must store only cryptographic hashes. Exact key lifecycle, storage schema, rotation, and revocation propagation latency remain tracked under [TBD-SEC-01].

### 7.2. Project Membership & Baseline RBAC Roles
In strict alignment with [D05 § 8.3](../architecture/DATABASE_DOMAIN_MODEL.md) and [D06 § 3.2](../api/API_CONTRACTS.md), authorization is scoped to `ProjectMembership` with three approved baseline roles: `OWNER`, `ENGINEER`, and `VIEWER`.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   LOGPILOT BASELINE ACCESS MATRIX (D06 § 3.2)               │
├──────────────────────────────┬─────────────┬─────────────┬──────────────────┤
│ Operation / Action           │ OWNER       │ ENGINEER    │ VIEWER           │
├──────────────────────────────┼─────────────┼─────────────┼──────────────────┤
│ Manage Memberships & Roles   │ Authorized  │ Denied      │ Denied           │
│ Update Project Configuration │ Authorized  │ Denied      │ Denied           │
│ Configure / Revoke API Keys  │ Authorized  │ Denied      │ Denied           │
│ Ingest Telemetry & Logs      │ Authorized  │ Authorized  │ Denied           │
│ Mutate Incident Lifecycle    │ Authorized  │ Authorized  │ Denied           │
│ Trigger RCA Explanation      │ Authorized  │ Authorized  │ Denied           │
│ Read Incidents & RCA Results │ Authorized  │ Authorized  │ Authorized       │
│ Read Project Audit Records   │ Authorized  │ Denied*     │ Denied           │
└──────────────────────────────┴─────────────┴─────────────┴──────────────────┘
```
*\*Note: In accordance with D06 § 7.2 and § 7.8, project-management and configuration endpoints are reserved to `OWNER`. In D06 § 7.9, retrieving audit records requires `ENGINEER` or `OWNER` authorization. (Although D06 § 3.2 mentions `VIEWER` reading audit logs informally, the authoritative endpoint contract in § 7.9 restricts access to `ENGINEER` or `OWNER`). Fine-grained operation-level permission scopes and role refinements are tracked under [TBD-SEC-02].*

### 7.3. Authorization Invariants
1. **Server-Side Authorization Authority:** Frontend UI visibility toggles provide user convenience only. The backend API gateway is the **sole authoritative enforcement point**. Every endpoint independently validates caller identity and project permissions.
2. **Project Membership Required:** Actions within `/api/v1/projects/{project_id}/...` require the authenticated user to hold an active `ProjectMembership` in that specific project ([D06 § 3.2](../api/API_CONTRACTS.md)).
3. **No Self-Escalation:** `ENGINEER` and `VIEWER` roles cannot grant permissions to themselves, modify their own project roles, or assign the `OWNER` role. Project membership and role mutations strictly require `OWNER` authorization.
4. **Uniform Rejection Semantics:** When a caller attempts to access a project or resource they are not authorized to view, the API returns **`404 Not Found`** rather than `403 Forbidden` whenever revealing resource existence would leak private organizational information ([D06 § 4.3](../api/API_CONTRACTS.md)).

---

## 8. Project/Tenant Isolation and Relational Ownership Enforcement

### 8.1. Relational Scoping Invariants
In accordance with [ADR-008](../adr/adr-008-multi-tenancy-strategy.md) and [D05](../architecture/DATABASE_DOMAIN_MODEL.md), LogPilot enforces strict **project-level data isolation**:

$$\forall \text{ queries } Q, \quad Q \implies \text{WHERE } \text{resource.project\_id} = \text{session.active\_project\_id}$$

1. **Mandatory Relational Scoping:** Every query executed by the API or background workers against `log_events`, `anomaly_signals`, `incidents`, `incident_evidence`, `rca_candidates`, and `rca_explanations` **must explicitly filter by `project_id`**.
2. **Foreign Key Integrity Validation:** Cross-project foreign key references are forbidden. Creating an `IncidentEvidence` linking an `incident_id` in Project A to a `log_event_id` in Project B must be rejected transactionally at the database layer.
3. **Derived Vector Store Isolation:** Vector searches in Qdrant must execute with a mandatory payload filter ensuring vector points from other projects are inaccessible ([D09](../architecture/RAG_ARCHITECTURE.md)). Qdrant operates as a derived, sensitive, rebuildable retrieval index, not an authoritative store.

### 8.2. Isolation Enforcement Across Platform Tiers

```mermaid
flowchart TD
    Client["Client Request (REST / WS)"] --> Gateway["API Gateway (Auth & Scoping)"]
    Gateway --> CheckAuth{"Valid Session &<br/>Project Member?"}
    CheckAuth -- No --> Deny["HTTP 401 / 404 (Reject)"]
    CheckAuth -- Yes --> Extract["Extract project_id"]

    subgraph StorageIsolation["Strict Isolation Layer"]
        Extract --> PG["PostgreSQL Query<br/>(WHERE project_id = :pid)"]
        Extract --> Qdrant["Qdrant Vector Search<br/>(must: [{key: 'project_id', match: :pid}])"]
        Extract --> Workers["Worker Task Dispatch<br/>(Payload contains validated project_id)"]
    end
```

---

## 9. Local Agent Security, Filesystem Boundaries, `.logpilotignore`, and Git Collection

### 9.1. Local Agent Threat Model & Least Privilege
The LogPilot local Python agent (`agent/logpilot-agent/`) runs within the developer's workstation host environment ([ADR-007](../adr/adr-007-local-agent-architecture.md)). To prevent workstation compromise:
1. **User-Space Execution:** The agent executes strictly under standard user privileges. It requires zero administrative (`sudo` / `SYSTEM`) permissions.
2. **Loopback Binding (Candidate Control):** As a recommended candidate security control, the agent's local server should bind strictly to loopback interfaces (`127.0.0.1` or named pipes) rather than public interfaces (`0.0.0.0`). The exact IPC protocol and binding strategy remain an unresolved decision in [ADR-007](../adr/adr-007-local-agent-architecture.md) and are tracked under [TBD-SEC-12].
3. **Bounded Filesystem Scope:** The agent is restricted to the explicitly opened repository root directory. Directory traversal outside the project root (e.g., resolving symlinks to system directories) is strictly prohibited.

### 9.2. Defensive Exclusion Architecture: `.logpilotignore`
Repository scanning introduces severe credential exposure risks ([ADR-006](../adr/adr-006-repository-intelligence-and-secret-redaction.md)). The local agent enforces a mandatory two-tier exclusion architecture:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     DEFENSIVE REPOSITORY EXCLUSION TIERS                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  [TIER 1: MANDATORY BUILT-IN SYSTEM EXCLUSIONS (NON-OVERRIDABLE)]                 │
│  • Credentials / Secrets: .env, .env.*, *.pem, *.key, *.crt, *.p12,         │
│    *.pfx, *.jks, credentials*, secrets*, id_rsa*, id_ed25519*, *.gpg       │
│  • VCS Internals: .git/                                                     │
│  • Dependencies & Virtualenvs: node_modules/, .venv/, venv/, env/, vendor/  │
│  • Build Artifacts & Binaries: dist/, build/, out/, target/, *.exe, *.dll   │
│  • Large Machine Learning Assets: *.h5, *.pkl, *.pt, *.onnx, *.bin          │
├─────────────────────────────────────────────────────────────────────────────┤
│  [TIER 2: PROJECT-SPECIFIC CONFIGURABLE EXCLUSIONS]                         │
│  • .logpilotignore file checked into the root of the target repository      │
│  • Follows .gitignore pattern syntax (path matching, globbing)             │
│  • Overrides nothing in Tier 1; can only add ADDITIONAL exclusion paths     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.3. Git Collection Security Rules
- **No Full Repository Dumps:** The agent never transmits entire repository histories or raw `.git` databases over the network.
- **Temporally Correlated Diffs Only:** Git inspections are restricted to recent commits and diffs temporally surrounding an active incident window (e.g., commits within $\pm 2$ hours of detected anomaly onset).
- **Patch Sanitization:** Diff hunks and commit messages pass through the pre-ingress secret redaction scanner prior to serialization.

---

## 10. Ingestion Validation, Size Limits, Normalization, and Redaction

### 10.1. Ingestion Boundary Validation
Telemetry ingress represents the primary entry point for untrusted external data ([D07](../architecture/EVENT_LOG_SCHEMA.md)). The API gateway and ingestion workers enforce strict validation gates:
1. **Payload Schema Validation:** Ingested payloads must conform strictly to Pydantic models enforcing structural typing, UTF-8 character encoding, and required metadata fields (`service`, `timestamp`, `message`).
2. **Batch & Payload Size Limits (Candidate Controls):** To prevent resource exhaustion attacks, candidate baseline limits are proposed:
   - Candidate maximum raw HTTP request body size: 5 MB envelope (provisional; see [TBD-SEC-04]).
   - Candidate maximum batch event count: 1,000 log events per request.
   - Candidate maximum single log message length: 16 KB (events exceeding this limit are cleanly truncated with `[... TRUNCATED DUE TO SIZE ...]`).
   - *Final operational thresholds will be calibrated during implementation benchmarking.*
3. **Encoding Sanitization:** Payloads containing non-UTF-8 sequences, raw binary null bytes, or malformed unicode are sanitized or rejected at ingress.

### 10.2. Pre-Ingress Secret Redaction Pipeline
In accordance with [ADR-006](../adr/adr-006-repository-intelligence-and-secret-redaction.md) and [D07 § 5.2](../architecture/EVENT_LOG_SCHEMA.md), secret scrubbing is a mandatory defense-in-depth requirement occurring **before** context is stored in vector indices or transmitted to any LLM runtime:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│             CANDIDATE PRE-INGRESS SECRET REDACTION TECHNIQUES               │
├──────────────────┬──────────────────────────────────────────────────────────┤
│ Detection Method │ Target Token Pattern                                     │
├──────────────────┼──────────────────────────────────────────────────────────┤
│ Candidate        │ AWS Access Keys (`AKIA[0-9A-Z]{16}`)                     │
│ Signature Regex  │ Private RSA / OpenSSH Keys (`-----BEGIN.*PRIVATE KEY`)   │
│ Banks            │ JSON Web Tokens (`ey[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+...`)│
│                  │ Database URIs (`postgres://user:pass@host:5432/db`)      │
│                  │ Generic Bearer Tokens (`Bearer [A-Za-z0-9-._~+/]+=*`)   │
├──────────────────┼──────────────────────────────────────────────────────────┤
│ Shannon Entropy  │ High-entropy alphanumeric strings ($H \ge 4.5$) in      │
│ Scoring (Cand.)  │ assignment contexts (e.g., `api_key = "..."`)            │
├──────────────────┼──────────────────────────────────────────────────────────┤
│ Masking Token    │ Replaces detected secrets with irreversible format token:│
│ Replacement      │ `[REDACTED_SECRET:<PATTERN_TYPE>]`                       │
└──────────────────┴──────────────────────────────────────────────────────────┘
```

*Residual Risk Acknowledgment:* Pattern-based and entropy-based scanners mitigate known credential exposure but **cannot guarantee detection of every secret**. Novel token structures, base64-encoded secrets, or credentials embedded in non-standard log formatting carry residual leakage risk. ADR-006 explicitly records that the specific secret detection library/algorithm is unresolved; exact engine selection is tracked under [TBD-SEC-03].

---

## 11. Secrets Management and Data Minimization

### 11.1. Platform Secrets Management
1. **No Hardcoded Secrets:** No cryptographic keys, database passwords, or third-party API tokens are committed to source control.
2. **Environment Configuration:** Secrets are supplied to containers and worker runtimes strictly via environment variables or secret files injected at launch ([D04](../architecture/REPOSITORY_ARCHITECTURE.md)).
3. **Candidate Password Hashing:** User passwords must be stored exclusively as one-way cryptographic hashes. Industry-standard memory-hard algorithms (such as Argon2id or bcrypt with cost factor $\ge 12$) represent candidate implementations; the exact algorithm and parameter tuning are tracked under [TBD-SEC-01].
4. **Third-Party Provider Tokens:** Hosted LLM provider keys (e.g., OpenAI, Anthropic) are managed centrally in server configuration and never transmitted to or accessible by client extensions.

### 11.2. Data Minimization Controls
1. **Targeted Code Context:** LogPilot never ingests or vectors full repositories ([ADR-006](../adr/adr-006-repository-intelligence-and-secret-redaction.md)). Code extraction utilizes bounded chunks (candidate heuristic: 50–100 lines surrounding an active stack trace frame; see [D09](../architecture/RAG_ARCHITECTURE.md), [D10](../architecture/LLM_ARCHITECTURE.md)).
2. **Log Burst Deduplication & Sampling:** High-volume repetitive error spikes are clustered via Drain3/LogMine templates ([D07](../architecture/EVENT_LOG_SCHEMA.md), [D08](../architecture/ML_RCA_ARCHITECTURE.md)). LogPilot transmits template identifiers and frequency counts to diagnostic tools rather than streaming thousands of redundant log strings.
3. **Incident Snapshot Scope:** Telemetry snapshots attached to `IncidentEvidence` are scoped to the active incident correlation window. In accordance with [D07 § 5.3](../architecture/EVENT_LOG_SCHEMA.md), evidence snapshots are subject to project retention policies and do not carry an architectural guarantee of permanent retention.

---

## 12. Prompt-Injection Defense and Treatment of Evidence as Untrusted Data

### 12.1. Threat Formulation: Observability Injection Vectors
In an observability platform, external attackers cannot interact directly with the LLM prompt, but they can trigger application behavior that causes **indirect prompt injection** via six passive telemetry vectors ([D10 § 8.1](../architecture/LLM_ARCHITECTURE.md)):
1. Malicious log messages (e.g., injecting override instructions into HTTP user-agent headers).
2. Exception stack trace strings containing crafted query parameters.
3. Code comments embedded in scanned repository files.
4. Craftily authored Git commit messages and pull request titles.
5. Injected historical post-mortem incident notes.
6. Malicious container tags or OpenTelemetry metadata attributes.

### 12.2. Multi-Layered Injection Defense Architecture
LogPilot neutralizes prompt-injection exploits through a five-layer least-privilege defense model ([D10 § 8.2](../architecture/LLM_ARCHITECTURE.md)):

```mermaid
flowchart TD
    UntrustedData["Untrusted Forensic Context<br/>(Logs, Traces, Diffs, Code)"] --> Layer1["Layer 1: Pre-Ingress Sanitization<br/>(Regex / Entropy Redaction)"]
    Layer1 --> Layer2["Layer 2: Structural Data Isolation<br/>(Quarantined in Tier 3 XML Delimiters)"]
    Layer2 --> Layer3["Layer 3: Least Privilege Execution<br/>(No Shell / No Tool Privileges)"]
    Layer3 --> Layer4["Layer 4: Deterministic JSON Schema<br/>(Strict JSON Mode Enforced)"]
    Layer4 --> Layer5["Layer 5: Post-Generation Validation<br/>(Citation Allowlist & Script Scanning)"]
    Layer5 --> Persist["Authoritative PostgreSQL DB<br/>(Verified Explanation Record)"]
```

### 12.3. Core Defense Rules and Invariants
1. **Strict Instruction Isolation:** Telemetry data is never concatenated into the Tier 1 trusted system instruction block. It is quarantined strictly within Tier 3 XML data delimiters (`<evidence_item id="...">...</evidence_item>`).
2. **Zero Tool Privileges:** The model possesses **zero tool-calling, function-calling, shell execution, or database write privileges**. Even if an adversarial prompt successfully overrides the model's text persona, it cannot invoke external commands or alter database state.
3. **Structured JSON Mode:** Inference forces JSON mode. Unconstrained markdown scripting, HTML payload execution, and raw shell script generation are rejected by Pydantic schema validation ([D10 § 6.1](../architecture/LLM_ARCHITECTURE.md)).
4. **No Delimiter Immunity Panaceas:** LogPilot recognizes that **prompt delimiters and local execution do NOT guarantee complete mathematical immunity from prompt injection**. Security relies on blast-radius containment: preventing the model from having authority to execute code, reorder RCA rankings, or mutate authoritative incident lifecycle records.

---

## 13. LLM/Provider Security, Data Handling, and Failure Behavior

### 13.1. Provider Abstraction and Security Posture
LogPilot abstracts LLM inference behind a provider-neutral gateway interface ([ADR-002](../adr/adr-002-llm-provider-abstraction.md), [D10](../architecture/LLM_ARCHITECTURE.md)):

| Dimension | Local Execution (Ollama) | Hosted Cloud Provider |
|---|---|---|
| **Network Perimeter** | Local Loopback / Private Subnet (Topology-Dependent) | Outbound TLS to SaaS API |
| **Inference Prompt Transmission** | No transmission of prompts to external model providers under verified genuinely local inference* | Encrypted Payload Transit (TLS 1.3) |
| **Model Provider Retention** | No external model-provider retention of prompts under verified local inference; host/platform logging may apply* | Dependent on Provider Agreement / SLA |
| **Model Training Exposure** | No external model-provider training exposure from locally processed prompts, subject to verified topology and configuration* | Enterprise Zero-Data-Retention (ZDR) Terms Required |
| **Operational Cost** | Dedicated Hardware Compute (Fixed) | Per-Token Metered OpEx |
| **Target Deployment** | Privacy-Preserving / Self-Hosted Workspaces | Scalable Cloud Deployment |

*\*Deployment Topology & Configuration Note: In a verified deployment topology where inference runs genuinely locally (e.g., self-hosted Ollama on loopback or private host), inference prompts and retrieved code context are not transmitted to an external model provider, mitigating third-party retraining exposure and external vendor data retention. However, running a local model does not by itself guarantee that the overall platform deployment has no external network traffic, telemetry, system logging, or data retention. Platform-level isolation remains conditional on the verified deployment topology, host-level logging policies, network controls, and firewall rules. LogPilot maintains an approved architectural preference for privacy-preserving local inference while ensuring operational security claims remain strictly conditional on verified deployment configurations.*

### 13.2. Hosted Provider Requirements
If configured to utilize an external cloud LLM provider (e.g., OpenAI, Anthropic), the following technical constraints apply:
- **Enterprise Data Protection Policy:** Deployments should verify that organizational agreements prohibit the vendor from using transmitted prompts, diffs, or logs for foundation model retraining. LogPilot cannot independently audit external cloud infrastructure; data protection remains conditional on provider compliance and verified enterprise terms.
- **Pre-Ingress Scrubbing Mandatory:** Pre-ingress secret scrubbing must execute prior to payload serialization; raw telemetry must not transit unmasked to external APIs.
- **Provider Policy Status:** The formal selection and approval of hosted cloud vendors remains tracked under [TBD-SEC-09].

### 13.3. Failure Containment & The Non-Destructive Invariant
In strict accordance with [D10 § 10.4](../architecture/LLM_ARCHITECTURE.md):
$$\text{LLM Failure (Timeout / Crash / Corruption)} \centernot\implies \text{Incident State Corruption}$$

1. **Non-Destructive Invariant:** An LLM inference timeout (e.g., candidate 30s threshold), provider crash, or malformed JSON completion **MUST NEVER** delete, overwrite, or corrupt the underlying `Incident`, its linked `IncidentEvidence`, or the calculated `RCACandidate` ranking order.
2. **Graceful Degradation:** When generative synthesis fails, the operation concludes with `status: "FAILED"` or `"TIMEOUT"`. The UI cleanly falls back to displaying canonical algorithmic RCA rankings and raw forensic evidence citations computed by the ML engine ([D08](../architecture/ML_RCA_ARCHITECTURE.md)).

---

## 14. API, Worker, Database, Queue, Vector-Store, and Inter-Process Security

### 14.1. Network Perimeter & Inter-Process Communication
1. **TLS Encryption (Recommended Baseline):** External client communications (REST API and WebSockets) should terminate over TLS 1.3 (or TLS 1.2 minimum) in production deployments.
2. **Container Network Isolation (Candidate Control):** As a recommended deployment practice, PostgreSQL, Redis, and Qdrant containers should reside within an isolated internal Docker bridge network, avoiding public host port bindings.
3. **Redis Task Broker Security:** Celery worker communication over Redis should require authentication passwords and utilize separate logical databases or prefixes for job queues versus caching.

### 14.2. Database & Vector Store Hardening
1. **PostgreSQL Parameterized Queries:** All database interactions via SQLAlchemy / SQLModel utilize strict parameterized queries. String concatenation of user input into raw SQL statements is strictly prohibited.
2. **Least Privilege Database Roles (Candidate Recommendation):** Application connection strings should connect as an unprivileged service role (`logpilot_app`), lacking `SUPERUSER` or `CREATEDB` permissions.
3. **Qdrant Vector Isolation:** Qdrant collections enforce mandatory `project_id` payload indexes. Vector search queries must include deterministic project filter clauses ([D09](../architecture/RAG_ARCHITECTURE.md)).

---

## 15. Transport, Storage, Backups, Retention, and Deletion Considerations

### 15.1. Cryptographic Protection in Transit and at Rest
- **Data in Transit:** TLS encryption is recommended across all client-to-API and API-to-hosted-provider connections.
- **Data at Rest:** Database volumes and vector store directories should leverage filesystem-level encryption (e.g., LUKS, AWS EBS encryption, or dm-crypt). Exact platform-level database column encryption remains an open implementation decision tracked under [TBD-SEC-05].

### 15.2. Data Retention & Deletion Architecture
In accordance with [D05 § 8](../architecture/DATABASE_DOMAIN_MODEL.md) and [D07 § 5.3](../architecture/EVENT_LOG_SCHEMA.md), forensic telemetry cannot be retained indefinitely:
1. **No Permanent Evidence Promise:** Stored log events, anomaly records, and `IncidentEvidence` snapshots do not carry an architectural promise of permanent retention. They are subject to project-level data retention policies.
2. **Cascading Project Deletion (Proposed Lifecycle Policy):** In accordance with [D05](../architecture/DATABASE_DOMAIN_MODEL.md), deleting a `Project` triggers relational cascades across PostgreSQL tables. Cross-store synchronized cleanup (purging corresponding points in Qdrant and feature keys in Redis) represents a proposed lifecycle policy whose exact synchronization mechanism and failure-recovery semantics are tracked under [TBD-SEC-06] and [TBD-SEC-13].
3. **Policy Formalization:** Exact default retention periods (e.g., 30-day raw log TTL, 90-day incident snapshot TTL) remain tracked under [TBD-SEC-06].

---

## 16. Audit Logging, Monitoring, Security-Relevant Events, and Privacy

### 16.1. Audit Logging Architecture
LogPilot tracks security-relevant events in the `audit_records` table (`AuditRecord` domain entity in [D05 § 8.18](../architecture/DATABASE_DOMAIN_MODEL.md)). The following security-relevant events generate audit records:
- User authentication events (successful logins, failed attempts, token revocations).
- Project membership modifications (member invitations, role updates, member removals).
- API key lifecycle events (generation, modification, revocation).
- Project configuration updates (redaction rules, service bindings, ignore lists).
- Diagnostic explanation invocations (`POST .../rca/explain`).
- Manual incident lifecycle modifications (resolving, ignoring, updating severity).

### 16.2. Audit Storage Model & Tamper Resistance
1. **Append-Only Application Model:** In accordance with [D05 § 8.18, § 14](../architecture/DATABASE_DOMAIN_MODEL.md), the application database user lacks `UPDATE` and `DELETE` privileges on `audit_records`, establishing an application-level append-only guarantee.
2. **Distinction from Hardware WORM:** This application-level permission constraint must be clearly distinguished from database-enforced immutability, cryptographic tamper evidence, or hardware write-once-read-many (WORM) storage. Advanced tamper-evident architectures (such as cryptographic hash-chaining or external SIEM forwarding) remain open options tracked under [TBD-SEC-08].
3. **Zero Secret Logging:** Audit entries must **never record plaintext passwords, bearer tokens, or raw secrets**.
4. **Parameter Sanitization:** Ingestion URLs and request query parameters recorded in audit tables must have sensitive authentication parameters scrubbed.
5. **Audit Record Access Controls:** In accordance with [D06 § 7.9](../api/API_CONTRACTS.md), audit record retrieval endpoints require `ENGINEER` or `OWNER` authorization. Unauthenticated or unauthorized callers (including `VIEWER` or cross-project users) are rejected with `401 Unauthorized` or `403 Forbidden`. (Evaluating whether compliance audit log inspection should be restricted exclusively to `OWNER` or a dedicated auditor role is tracked under [TBD-SEC-02]).

---

## 17. Security Testing Strategy and Abuse-Case Acceptance Scenarios

To ensure continuous verification of the Security Model, LogPilot establishes automated abuse-case testing across eight critical scenarios:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                  SECURITY ABUSE-CASE ACCEPTANCE SCENARIOS                   │
├───────┬───────────────────────────────┬─────────────────────────────────────┤
│ ID    │ Test Scenario Description     │ Expected Verifiable Behavior        │
├───────┼───────────────────────────────┼─────────────────────────────────────┤
│ **1** │ **Cross-Project Access**      │ API returns HTTP 404 Not Found; zero│
│       │ User A requests Project B ID  │ cross-tenant data returned.         │
├───────┼───────────────────────────────┼─────────────────────────────────────┤
│ **2** │ **Vector Tenant Bleed**       │ Qdrant query with Project A filter  │
│       │ Search embeddings for B       │ returns exactly 0 Project B vectors.│
├───────┼───────────────────────────────┼─────────────────────────────────────┤
│ **3** │ **Unauthorized Role Change**  │ API rejects with HTTP 403 Forbidden;│
│       │ ENGINEER attempts role grant  │ target member role remains unchanged│
├───────┼───────────────────────────────┼─────────────────────────────────────┤
│ **4** │ **Log Ingress Secret Redact** │ Output text contains masked tokens; │
│       │ Ingest synthetic AWS keys     │ zero plaintext keys enter DB/vector.│
├───────┼───────────────────────────────┼─────────────────────────────────────┤
│ **5** │ **Workspace Ignore Defense**  │ Local agent scan excludes files;    │
│       │ Place uncommitted .env in repo│ zero keys transmitted to API.       │
├───────┼───────────────────────────────┼─────────────────────────────────────┤
│ **6** │ **Indirect Prompt Injection** │ System ignores override instructions│
│       │ Ingest log with prompt exploit│ emits valid schema, no shell calls. │
├───────┼───────────────────────────────┼─────────────────────────────────────┤
│ **7** │ **Citation Allowlist Check**  │ Validation pipeline rejects invalid │
│       │ Model invents fake UUID       │ IDs; explanation flags violation.   │
├───────┼───────────────────────────────┼─────────────────────────────────────┤
│ **8** │ **Provider Timeout Isolation**│ Operation marks status TIMEOUT;     │
│       │ Sever LLM network connection  │ incident & RCA candidates uncorrupt.│
└───────┴───────────────────────────────┴─────────────────────────────────────┘
```

---

## 18. Incident Response and Security Failure Handling

When a platform security anomaly or failure occurs, LogPilot applies fail-safe containment protocols:
1. **Redaction Failure Handling (Proposed Control):** If the pre-ingress regex scanner encounters an unhandled exception or catastrophic backtracking, the ingestion worker is proposed to quarantine the raw batch rather than permitting unredacted telemetry downstream. Detailed quarantine and alerting procedures remain tracked under [TBD-SEC-03] and [TBD-SEC-11].
2. **API Key Revocation Latency (Candidate Target):** Revoking an API key via `DELETE .../api-keys/{key_id}` should promptly terminate active sessions. While rapid revocation ($\le 5\text{s}$) is a desirable operational target, the exact propagation latency across distributed worker caches remains an unresolved decision tracked under [TBD-SEC-01].
3. **Prompt Injection Alerting (Proposed Control):** Detected prompt injection attempts are proposed to log an operational alert in `audit_records` and abort explanation synthesis, displaying an administrative warning in the triage UI.
4. **Platform Vulnerability Reporting:** Security vulnerabilities should be handled through coordinated disclosure, with formal response SLAs established in [TBD-SEC-11].

---

## 19. Security Invariants and Explicit Non-Guarantees

### 19.1. Mandatory Architectural Invariants
Every system implementation conforming to LogPilot D11 must strictly preserve these 12 invariants:
1. **Authoritative System of Record:** PostgreSQL is the sole authoritative store of record for all state; Qdrant is a derived, sensitive, rebuildable retrieval index.
2. **Server-Side Project Authorization:** Project-level RBAC is authoritatively enforced on the backend, not merely via frontend filtering.
3. **No Cross-Project Access:** Forged or mismatched project UUIDs never grant cross-project access to telemetry, evidence, or explanations.
4. **Untrusted Evidence Classification:** All logs, stack traces, code snippets, Git diffs, and LLM completions are classified as untrusted data.
5. **No Instruction Override:** Retrieved evidence can inform diagnostic synthesis, but can never override trusted system instructions.
6. **Unmodified Algorithmic Rankings:** The LLM cannot create, reorder, replace, or invert canonical `RCACandidate` rankings computed by the ML engine.
7. **No Autonomous State Mutation:** The LLM cannot modify incident lifecycle states (`DETECTED`, `INVESTIGATING`, `RESOLVED`, `IGNORED`).
8. **Citation Allowlist Enforcement:** Every evidence reference produced by an LLM must exist in the prompt's authorized citation allowlist.
9. **Derived Sensitive Vector Status:** Qdrant embeddings and payloads are classified as derived sensitive assets and must enforce project filtering. Qdrant retention and lifecycle policies remain TBD.
10. **Evidence Retention Subordination:** Incident evidence snapshots remain subject to project-level authorization and retention/deletion policies; snapshots do not promise permanent retention.
11. **Non-Destructive Generative Failure:** Provider crashes, malformed completions, or timeouts must never corrupt underlying incident records.
12. **No Shell or Tool Execution Privileges:** Generative models operate with no shell execution, tool calling, or operating system modification privileges.

### 19.2. Explicit Non-Guarantees
To prevent misleading security representations, LogPilot explicitly declares:
- **No Guarantee of 100% Secret Redaction:** Heuristic and regex masking reduce exposure significantly, but cannot mathematically guarantee detection of every secret.
- **No Guarantee of Complete Injection Immunity:** Data framing and schema enforcement contain attacks, but cannot guarantee that models will never exhibit subtle diagnostic bias.
- **No Guarantee of Infallible Causal Attribution:** LLM explanations are assistive diagnostic syntheses, not mathematical or physical proofs of causation.
- **No Guarantee of Overall Deployment Isolation:** In a verified genuinely local deployment, local inference (e.g., Ollama) avoids transmitting inference prompts to external model providers, but this does not by itself guarantee that the overall deployment has no external network traffic, telemetry, logging, or retention, nor does it secure the local host against malware or root-level compromise.

---

## 20. TBD Register and Traceability

To maintain technical honesty and prevent premature specification freezing, unresolved security design decisions are formally cataloged in the TBD register below:

| TBD ID | Topic / Decision | Options Under Consideration | Evidence / Analysis Needed to Resolve | Owning Document / Target Phase |
|---|---|---|---|---|
| **TBD-SEC-01** | **Authentication, Token Lifecycle & Password Hashing** | Stateless signed JWTs, stateful server-side sessions, or hybrid Redis-backed session tokens; Argon2id vs. bcrypt password hashing; revocation propagation latency targets. | Evaluation of revocation latency, session invalidation overhead, and VS Code extension token storage security. | Implementation Phase |
| **TBD-SEC-02** | **Granular Operation Permission Matrix** | Baseline 3-role static model (`OWNER`, `ENGINEER`, `VIEWER` from [D06 § 3.2](../api/API_CONTRACTS.md)) vs. fine-grained permission scopes (e.g., `incident:read`, `rca:write`). | API complexity trade-off vs. enterprise RBAC requirements. | Implementation Phase |
| **TBD-SEC-03** | **Secret Redaction Engine & Quarantine Policy** | Pre-compiled Python regex banks vs. established scanning libraries (e.g., TruffleHog, Gitleaks wrappers, or Microsoft Presidio); batch quarantine failure behavior. | Ingestion throughput overhead (lines/sec) vs. false-positive and false-negative benchmark accuracy. | Implementation Phase / Planned [D12](../architecture/EVALUATION_FRAMEWORK.md) |
| **TBD-SEC-04** | **Ingestion Payload & File Size Ceilings** | Candidate 5MB HTTP body envelope vs. streaming chunked ingestion caps; 16KB vs. 32KB per-log truncations. | Ingestion memory footprint under burst traffic on reference 8GB RAM host. | Implementation Phase |
| **TBD-SEC-05** | **Encryption-at-Rest & Network Hardening** | Storage volume-level encryption (LUKS/dm-crypt) vs. application-layer column encryption (SQLAlchemy-Utils/pgcrypto); mTLS for internal containers. | Query latency impact on PostgreSQL time-series indexing vs. threat model requirements. | Infrastructure / Deployment Phase |
| **TBD-SEC-06** | **Telemetry & Snapshot Retention Policy** | Automated time-to-live (e.g., 30-day raw logs, 90-day evidence snapshots) vs. manual administrator purging. | Storage capacity consumption modeling across sustained 500 lines/sec ingestion. | Implementation Phase |
| **TBD-SEC-07** | **Rate Limiting & DoS Quotas** | Fixed-window token bucket vs. sliding-window Redis rate limiter; per-IP vs. per-API-key quotas. | Burst tolerance for continuous application telemetry vs. DoS defense. | Implementation Phase |
| **TBD-SEC-08** | **Audit Storage Architecture & WORM Archiving** | Relational append-only table (`audit_records` in [D05](../architecture/DATABASE_DOMAIN_MODEL.md)) vs. cryptographically signed hash-chained logs or external SIEM/Syslog forwarding. | Compliance and non-repudiation audit requirements vs. operational simplicity. | Phase 2 / Enterprise Roadmap |
| **TBD-SEC-09** | **Hosted Cloud LLM Provider Policy** | OpenAI (GPT-4o), Anthropic (Claude 3.5 Sonnet), DeepSeek-V3, Local-Only (Ollama). | Enterprise data protection agreements, SOC 2 compliance, and zero-training retention validation. | Implementation Phase |
| **TBD-SEC-10** | **Dependency & Vulnerability Scanning Policy** | Automated GitHub Dependabot / pip-audit CI integration vs. container-level Trivy/Grype image scanning. | CI/CD pipeline latency overhead vs. vulnerability alerting SLA. | Implementation Phase |
| **TBD-SEC-11** | **Security Incident Response & Disclosure SLA** | Standard 90-day coordinated disclosure policy vs. rapid hotfix protocol (24h critical, 7d high). | Operational resource availability and release deployment engineering. | Operational Governance |
| **TBD-SEC-12** | **Local Agent IPC Protocol & Binding Strategy** | Loopback HTTP server (`127.0.0.1`), local WebSocket, or OS-native named pipes/domain sockets ([ADR-007](../adr/adr-007-local-agent-architecture.md)). | Inter-process latency, cross-platform compatibility (Windows/Linux/macOS), and local process isolation. | Implementation Phase |
| **TBD-SEC-13** | **Qdrant Index Lifecycle & Rebuild Synchronization** | Event-driven point deletion on project delete vs. background index reconciliation worker; cold-start re-indexing triggers. | Index consistency overhead vs. point deletion latency. | Implementation Phase |

---

## 21. Cross-Document Traceability and Security Review Checklist

### 21.1. Upstream and Downstream Document Alignment
The Security Model (**D11**) maintains comprehensive alignment across the LogPilot architectural corpus:

- **[D01 — Product Requirements Document](../requirements/PRD.md):** Formalizes NFR-007 (Security throughout development), FR-HIST-001 (Historical evidence as context, not truth), and organizational hierarchy scoping.
- **[D02 — V1 Scope & Acceptance Criteria](../requirements/V1_SCOPE.md):** Upholds V1 boundaries by explicitly excluding autonomous production remediation, unconstrained code execution, and enterprise SSO federation.
- **[D03 — System Architecture Document](../architecture/SYSTEM_ARCHITECTURE.md):** Enforces container network isolation, gateway perimeters, and modular component boundaries.
- **[D04 — Repository Architecture Document](../architecture/REPOSITORY_ARCHITECTURE.md):** Governs secrets management via environment configurations and modular package isolation (`packages/db`, `packages/llm`).
- **[D05 — Database & Domain Model Document](../architecture/DATABASE_DOMAIN_MODEL.md):** Enforces PostgreSQL relational scoping via `project_id`, `audit_records` append-only application patterns, baseline roles (`OWNER`, `ENGINEER`, `VIEWER`), and point-in-time evidence retention.
- **[D06 — API Contracts & Interface Definitions](../api/API_CONTRACTS.md):** Implements server-side RBAC, uniform `404 Not Found` rejection semantics, and project-scoped endpoint routing.
- **[D07 — Event & Log Schema Specification](../architecture/EVENT_LOG_SCHEMA.md):** Standardizes pre-ingress secret redaction, Shannon entropy analysis, and input size constraints.
- **[D08 — ML & RCA Architecture](../architecture/ML_RCA_ARCHITECTURE.md):** Guarantees that analytical ML engines and heuristic rankers remain bounded, preventing LLMs from altering canonical rankings.
- **[D09 — RAG Architecture](../architecture/RAG_ARCHITECTURE.md):** Enforces mandatory `project_id` payload filtering in Qdrant and treats code chunks as derived sensitive assets.
- **[D10 — LLM Architecture](../architecture/LLM_ARCHITECTURE.md):** Implements multi-tier prompt isolation, least-privilege zero-tool execution, citation allowlist checks, and non-destructive failure handling.
- **[ADR-006](../adr/adr-006-repository-intelligence-and-secret-redaction.md):** Integrates `.logpilotignore` and built-in exclusion lists as the baseline defense-in-depth model for repository intelligence.
- **[ADR-007](../adr/adr-007-local-agent-architecture.md):** Confines the local agent to loopback communication, user-space execution, and repository root filesystem boundaries.
- **[ADR-008](../adr/adr-008-multi-tenancy-strategy.md):** Operationalizes project-level data isolation as the primary multi-tenancy model for V1.
- **[D12 — Evaluation & Research Framework](../architecture/EVALUATION_FRAMEWORK.md) (Planned):** Will provide automated benchmark verification for secret redaction precision/recall ([TBD-SEC-03]) and prompt-injection resilience.

### 21.2. Architecture Security Review Checklist
Before promoting downstream implementations to production, reviewers must verify:

- [ ] **Relational Scoping:** Every PostgreSQL query and repository method incorporates an explicit `WHERE project_id = :project_id` filter.
- [ ] **Vector Payload Filtering:** Every Qdrant retrieval query includes a mandatory `project_id` payload filter clause.
- [ ] **Pre-Ingress Masking:** Automated test suites verify that synthetic credential patterns (AWS, JWT, DB URIs) are masked before entering storage or prompts.
- [ ] **Workspace Exclusion:** The local agent demonstrably skips `.env*`, `*.pem`, `id_rsa*`, and all `.logpilotignore` patterns during scanning.
- [ ] **Loopback Confinement:** The local agent server binds strictly to loopback interfaces and rejects remote network connections.
- [ ] **No Tool LLM Calling:** Inference gateway code contains no tool-calling, function-calling, or shell execution APIs.
- [ ] **Citation Allowlist Validation:** Post-generation schema validation strips or flags any evidence ID not present in the prompt context.
- [ ] **Generative Failure Isolation:** Simulated LLM provider timeouts leave underlying incidents, evidence, and RCA candidates uncorrupted.
- [ ] **Audit Trail Record Creation:** Security-critical actions (role changes, key revocations, explanation requests) generate append-only `audit_records` ([D05 § 8.18, § 14]).
- [ ] **Plaintext Secret Exclusion:** Configuration files, logs, and database backups are proven free of plaintext passwords and bearer tokens.
