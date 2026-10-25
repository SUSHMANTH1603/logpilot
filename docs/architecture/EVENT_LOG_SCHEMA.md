# LogPilot — Event & Log Schema Specification

**Document ID:** D07  
**Status:** Draft for Architecture Review  
**Parent Documents:** [D01 — Product Requirements Document](file:///docs/requirements/PRD.md), [D02 — V1 Scope & Acceptance Criteria](file:///docs/requirements/V1_SCOPE.md), [D03 — System Architecture Document](file:///docs/architecture/SYSTEM_ARCHITECTURE.md), [D04 — Repository Architecture Document](file:///docs/architecture/REPOSITORY_ARCHITECTURE.md), [D05 — Database & Domain Model Document](file:///docs/architecture/DATABASE_DOMAIN_MODEL.md), [D06 — API Contracts & Interface Definitions](file:///docs/api/API_CONTRACTS.md)  
**Project:** LogPilot: An Intelligent Observability and Root Cause Analysis Platform  

---

## 1. Purpose and Design Principles

### 1.1. Role of the Event & Log Schema in LogPilot
The LogPilot platform bridges heterogeneous runtime observability signals with static software repository intelligence to achieve automated, evidence-grounded Root Cause Analysis (RCA). Central to this mission is the **Canonical Event & Log Schema**. 

In modern cloud environments, telemetry arrives in widely divergent representations: unstructured syslog text, multi-line exception stack traces, structured JSON payloads, Docker daemon JSON wraps, and OpenTelemetry (OTel) structured spans. Ingesting these streams directly into analytical, statistical, and language-model subsystems would introduce tight coupling, brittle parsing logic, and security vulnerabilities across the modular monolith.

The schema established in this document acts as the universal internal contract between:
- **Telemetry Ingestion Adapters:** Ingesting raw logs from files, containers, collectors, and developer environments.
- **Normalization & Sanitization Pipelines:** Filtering secrets, parsing dates, standardizing severities, and extracting structured attributes.
- **Template Mining Subsystems:** Extracting structural signatures by wildcarding volatile parameters.
- **Anomaly Detection & Feature Extractors:** Computing rolling metric vectors and frequency deviations.
- **Incident Correlators & Evidence Builders:** Associating causal events with code changes and assembling forensic diagnostic bundles.
- **Retrieval & RAG Context Indexers:** Generating deterministic embeddings and lexical search tokens for LLM root cause synthesis.

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                            LOGPILOT TELEMETRY REFINEMENT LADDER                             │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                             │
│  [ Raw Collector Input ]  ──► Unsanitized text, JSON streams, syslog frames, Docker logs    │
│            │                                                                                │
│            ▼                                                                                │
│  [ Normalized LogEvent ]  ──► Typed, sanitized, UTC-normalized, project-scoped event record │
│            │                                                                                │
│            ├────────────────────────────────┬────────────────────────────────┐              │
│            ▼                                ▼                                ▼              │
│  [ Derived LogTemplate ]         [ AnomalySignal ]                [ IncidentEvent ]         │
│  Structural pattern with         Statistical/ML feature           Associative join record   │
│  wildcarded parameters           deviation across windows         linking event to incident │
│            │                                │                                │              │
│            └────────────────────────────────┴────────────────────────────────┘              │
│                                             │                                               │
│                                             ▼                                               │
│                                   [ IncidentEvidence ]                                      │
│                                   Captured evidence snapshot & source                       │
│                                   citation for heuristic RCA & LLM                          │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 1.2. Telemetry Entity Taxonomy
To prevent conceptual ambiguity across services and documentation, LogPilot establishes strict definitions distinguishing telemetry stages:

1. **Raw Collector Input:** Unparsed, source-specific payloads received at the ingestion boundary (e.g., standard input, Docker JSON log envelopes, raw HTTP bodies). May contain syntax variations, malformed timestamps, or unredacted secrets.
2. **Normalized LogEvent:** A validated, strongly typed, UTC-normalized, and secret-redacted representation of a single log occurrence. Persisted authoritatively in PostgreSQL as `log_events`.
3. **Derived LogTemplate:** An aggregated structural pattern derived from one or more `LogEvent` records by template mining (e.g., masking UUIDs, IP addresses, and numbers into `<*>`). Stored in `log_templates` to enable high-cardinality aggregation and template-frequency anomaly detection.
4. **AnomalySignal:** A mathematical, statistical, or rule-based deviation detected across a window of events or template occurrences (e.g., sudden error spike, novel template occurrence). Stored in `anomaly_signals`.
5. **IncidentEvent:** A domain join entity linking an authoritative `LogEvent` to an `Incident`, qualifying its specific investigative role (`TRIGGER`, `EVIDENCE`, or `CORRELATED_CONTEXT`).
6. **IncidentEvidence:** A forensic evidence record linking an incident to supporting diagnostic artifacts, preserving provenance. In accordance with [D05](file:///docs/architecture/DATABASE_DOMAIN_MODEL.md), it captures both a reference pointer (`source_ref`) to the originating source entity (e.g., `LogEvent.id`, Git commit SHA, or code chunk) and a captured diagnostic snapshot (`evidence_payload`) of the relevant snippet at the time of linkage. Retention, deletion, and lifecycle rules for evidence records are governed by incident management policies rather than blanket eternal preservation.

### 1.3. Core Schema Design Principles
The schema adheres to seven architectural design principles:

1. **Source & Collector Agnosticism:** The normalized schema decouples core analytical engines from any specific log shipper, collector, or vendor format. An event emitted by a Python file logger, a Go container stderr stream, or an OpenTelemetry collector normalizes to the exact same contract.
2. **Explicit Provenance:** Every event retains clear, verifiable lineage pointing back to its originating project, source entity (`log_source_id`), and ingestion batch (`ingestion_run_id`).
3. **Dual Timestamp Semantics:** The schema strictly separates the *observed event timestamp* (when the originating application generated the log) from the *ingestion timestamp* (when LogPilot accepted the record).
4. **Pre-Persistence Redaction & Defense-in-Depth:** In accordance with [ADR-006](file:///docs/adr/adr-006-repository-intelligence-and-secret-redaction.md), secret scanning and sensitive value masking occur *before* events are written to the database or vector index.
5. **Multi-Tenant Isolation Invariant:** In accordance with [D05](file:///docs/architecture/DATABASE_DOMAIN_MODEL.md), all log events require a mandatory `project_id`. Identifiers and foreign keys are never trusted across project boundaries.
6. **Additive Forward & Backward Compatibility:** The schema permits additive optional fields without breaking existing analytical workers or serialization pipelines.
7. **Predictable Failure Semantics:** Malformed, oversized, or unparseable inputs must fail predictably with explicit error tracking, never silently fabricating or dropping diagnostic information.

---

## 2. Data Flow and Boundary Specifications

### 2.1. Ingestion & Normalization Processing Pipeline
The transition from raw external telemetry to persistent system state follows a deterministic six-stage lifecycle:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                TELEMETRY PROCESSING PIPELINE                                │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                             │
│  [ Stage 1: Ingestion Gateway ]                                                             │
│  - Receives HTTP batch payload (`POST /api/v1/projects/{project_id}/log-sources/{id}/ingest`)│
│  - Verifies bearer token or `X-LogPilot-Source-Key`                                         │
│  - Enforces payload size limits (e.g., 5 MB per batch)                                      │
│  - Enqueues batch asynchronously to Redis queue; returns `202 Accepted`                     │
│                                │                                                            │
│                                ▼                                                            │
│  [ Stage 2: Validation & Framing ]                                                          │
│  - Validates JSON payload envelope against Pydantic ingestion batch contract                │
│  - Unpacks records or splits multi-line text into discrete candidate event frames           │
│  - Rejects completely malformed payloads; tracks run errors in `ingestion_runs`             │
│                                │                                                            │
│                                ▼                                                            │
│  [ Stage 3: Normalization ]                                                                 │
│  - Parses timestamp to UTC ISO 8601; evaluates clock skew                                   │
│  - Maps heterogeneous severity levels to canonical taxonomy (`DEBUG`..`CRITICAL`)           │
│  - Extracts service, host, process, and tracing context into `attributes`                   │
│                                │                                                            │
│                                ▼                                                            │
│  [ Stage 4: Secret Redaction & Sanitization ]                                               │
│  - Executes regex & entropy filters against `message` and attribute values                 │
│  - Masks sensitive tokens, connection strings, credentials, and PII with `[REDACTED]`      │
│  - Generates deterministic `event_hash` for deduplication                                  │
│                                │                                                            │
│                                ▼                                                            │
│  [ Stage 5: Template Mining & Feature Extraction ]                                          │
│  - Matches or extracts structural `LogTemplate` via parameter wildcarding                   │
│  - Assigns `template_id` (cached in Redis or resolved via PostgreSQL)                       │
│  - Updates ephemeral feature counters in Redis for rolling window anomaly detection         │
│                                │                                                            │
│                                ▼                                                            │
│  [ Stage 6: Persistence & Correlation Dispatch ]                                            │
│  - Batch inserts normalized records into PostgreSQL `log_events`                            │
│  - Updates `ingestion_runs` progress counters (`events_processed`, `errors_count`)          │
│  - Dispatches anomaly detection worker and potential incident correlators                   │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

*Architectural Boundary Note:* While Stage 1 through Stage 6 reflect the approved system processing direction, the exact pipeline execution architecture (monolithic task chaining vs. decomposed Celery/Arq workers) remains an open implementation detail deferred to [D08 — ML & RCA Architecture](file:///docs/architecture/ML_RCA_ARCHITECTURE.md).

### 2.2. Entity Boundary & Responsibility Separation
To prevent domain leakage and schema bloat, fields are assigned strictly to their authoritative entity:

| Domain Entity | Ownership & Boundaries | Explicit Exclusions (What Does NOT Belong Here) |
|---|---|---|
| **Incoming Source Payload** | Transport envelope, raw string lines or client JSON dictionaries, source authentication token. | Persistent database IDs, server ingestion timestamps, template IDs. |
| **Normalized `LogEvent`** | Canonical timestamp, canonical level, sanitized message (`message_raw`), extracted structured `attributes`, `event_hash`, `log_source_id`, `project_id`. | Anomaly scores, incident assignment, RCA confidence metrics, raw unredacted source buffers. |
| **`LogTemplate`** | Parameter-wildcarded pattern (`pattern_raw`), deterministic pattern hash (`template_hash`), aggregate counts (`occurrence_count`), temporal bounds (`first_seen_at`, `last_seen_at`). | Individual log event messages, instance-specific variable parameters (IPs, UUIDs), tenant credentials. |
| **`AnomalySignal`** | Computed anomaly score, anomaly type (`SPIKE`, `NEW_TEMPLATE`, `PATTERN_SHIFT`), analysis time window (`window_start`, `window_end`), statistical feature vector snapshot. | Complete copies of raw log events, full stack traces, incident status. |
| **`IncidentEvent`** | Associative linkage (`incident_id` ↔ `log_event_id`), assigned event role (`TRIGGER`, `EVIDENCE`, `CORRELATED_CONTEXT`), linkage timestamp. | Duplicated log message text, log attributes, anomaly calculation internals. |
| **`IncidentEvidence`** | Captured diagnostic snapshot (`evidence_payload`) paired with source reference pointer (`source_ref` $\rightarrow$ `LogEvent.id`, `commit_sha`, etc.) assembled to support an RCA hypothesis. | Unfiltered raw telemetry streams, dynamic metric counters, database transaction logs. |
| **Retrieval / Qdrant Metadata** | Dense vector embedding, sanitized text snippet, payload filter attributes (`project_id`, `log_source_id`, `timestamp`, `level`). Strictly a derived retrieval index. | Authoritative system-of-record state, relational foreign keys, unredacted source files. |

---

## 3. Canonical Normalized Log-Event Contract

The canonical normalized log event represents the single, authoritative data structure consumed across LogPilot's analytical engines.

### 3.1. Field Reference Specification

The table below defines the canonical event contract, distinguishing logical conceptual types from proposed physical PostgreSQL column representations and wire serialization formats.

| Field Name | Logical Type | Proposed Physical Type | Required / Nullable | Validation & Proposed Guardrails | Provenance / Derivation | Security Classification & Handling |
|---|---|---|---|---|---|---|
| `id` | Identifier | `UUID` | Required / Non-Null | RFC 4122 v4 identifier generated by the ingestion pipeline. | Generated by Ingestion Pipeline. | Internal Operational Identifier. Safe. |
| `project_id` | Identifier | `UUID` | Required / Non-Null | Valid UUID. Foreign key to `projects.id`. Verified against authenticated caller scope. | Authenticated Request URL & Token. | Multi-Tenant Partition Key. Safe. |
| `log_source_id` | Identifier | `UUID` | Required / Non-Null | Valid UUID. Foreign key to `log_sources.id`. Must belong to same `project_id`. | Ingestion Route Path & Source Auth. | Operational Lineage Pointer. Safe. |
| `timestamp` | UTC Timestamp | `TIMESTAMPTZ` | Required / Non-Null | ISO 8601 UTC timestamp. Logical microsecond resolution. Evaluated for clock skew. | Extracted from raw log; falls back to ingestion time if absent. | Public Operational Telemetry. Safe. |
| `ingested_at` | UTC Timestamp | `TIMESTAMPTZ` | Required / Non-Null | ISO 8601 UTC timestamp recorded by server upon batch receipt. | LogPilot Server Clock. | System Audit Timestamp. Safe. |
| `level` | Enumeration | `VARCHAR(20)` | Required / Non-Null | Canonical set: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Case-normalized. | Normalized from source severity tokens. | Operational Telemetry. Safe. |
| `message_raw` | Text String | `TEXT` | Required / Non-Null | Sanitized log message text. Proposed default ceiling: 64 KB (characters exceeding limit truncated with `...[TRUNCATED]`). | Extracted log body after secret redaction. | High Risk: Sanitized via Active Redaction. |
| `attributes` | Structured Map | `JSONB` | Required / Non-Null | Key-value dictionary. Proposed default guardrails: max 32 KB serialized, max 3 nesting levels. Keys: `[a-z0-9_.-]{1,64}`. | Extracted structured metadata, trace IDs, source context. | Medium Risk: Sanitized via Active Redaction. |
| `template_id` | Identifier | `UUID` | Optional / Nullable | Foreign key to `log_templates.id`. Assigned when pattern matches or generates a template. | Template Mining Engine. | Internal Relational Pointer. Safe. |
| `event_hash` | Hash String | `VARCHAR(64)` | Required / Non-Null | Hexadecimal digest computed during normalization for idempotency/deduplication. Exact formula TBD. | Computed at Normalization Stage. | Deduplication Fingerprint. Safe. |
| `schema_version`| Version String| `VARCHAR(16)` | Required / Non-Null | Semantic schema specification format: proposed initial `"1.0"`. Identifies serialized contract version. | Ingestion Pipeline Contract. | System Metadata. Safe. |

*Note on Proposed Guardrails:* The 64 KB message size ceiling, 32 KB attribute payload bound, and 3-level nesting limit are proposed operational defaults designed to prevent memory exhaustion in ingestion workers. They represent recommended baseline guardrails rather than immutable architectural limits, and may be tuned during implementation benchmarking.

### 3.2. Project Isolation & Access Boundary Invariant
In strict alignment with [D05](file:///docs/architecture/DATABASE_DOMAIN_MODEL.md) and [D06](file:///docs/api/API_CONTRACTS.md):
- `project_id` is an authoritative multi-tenant partition key.
- The presence of `project_id` in a payload is **never** accepted as proof of client authorization. The active project context is verified server-side through cryptographic token signatures and database membership validation prior to inserting or reading log records.
- Database uniqueness and integrity constraints guarantee multi-tenant scoping:
  ```sql
  -- Proposed candidate unique constraint (provisional; subject to deduplication & partitioning design)
  CONSTRAINT uq_log_events_dedup UNIQUE (project_id, log_source_id, event_hash, timestamp)
  ```
  *Status:* The exact uniqueness constraint and conflict-handling strategy are provisional and designated as TBD pending physical database design and partitioning evaluations.

---

## 4. Raw Input versus Normalized Event

### 4.1. Supported Raw Input Modalities
LogPilot adapters accept three fundamental raw input formats:

1. **Structured JSON Logs:** Native JSON objects emitted by modern structured loggers (e.g., Python `structlog`, Go `zap`, Node.js `pino`, or OTel JSON).
   - *Parsing:* Direct key extraction mapping standard JSON fields (`msg`, `time`, `level`) to canonical equivalents, preserving remainder keys in `attributes`.
2. **Plain-Text Single-Line Logs:** Traditional syslog or unstructured print outputs (e.g., `2026-10-25 16:04:12 [ERROR] Database disconnected`).
   - *Parsing:* Regex or heuristic extraction of leading timestamp, severity token, and logger name. The remainder of the line forms `message_raw`.
3. **Multi-Line Exception Traces:** Stack traces, panic dumps, or indented blocks originating from runtime crashes.
   - *Assembly:* Ingestion buffers frame the root line (header) and attach subsequent indented lines (`at ...`, `File ...`) into a single multi-line `message_raw` record.

### 4.2. Raw Payload Retention & Deletion Policy
- **Authoritative Telemetry State:** In PostgreSQL, LogPilot persists the **normalized and redacted** event in `log_events.message_raw`.
- **Raw Collector Buffer Retention (TBD):** Whether complete, byte-for-byte unredacted incoming source packets should be archived in cold object storage (e.g., MinIO or S3) is designated as **TBD**. For V1, LogPilot **does not retain unredacted raw source payloads** in permanent relational storage to guarantee compliance with data protection policies and eliminate secret leakage risks.
- **Diagnostic Retention Limits:** If ephemeral ingestion buffers are enabled for pipeline troubleshooting, they must inherit the project's configured retention window (default 14 days) and must never be exposed via public API queries.

### 4.3. Malformed Records & Partial Parsing Representation
When incoming log records deviate from expected formats:
- If a timestamp or level cannot be extracted, the record is **not discarded**. It is converted into a valid canonical event by assigning a fallback severity (`INFO`), using the ingestion receipt time as `timestamp`, and recording normalization notices in `attributes._normalization_notes`.
- If an input line is completely unparseable or exceeds maximum byte boundaries, it is accounted for in `ingestion_runs.errors_count` without aborting the entire batch.
- **Zero Content Fabrication:** Normalizers must never invent synthetic diagnostic messages. The original text (post-redaction) is always preserved in `message_raw`.

### 4.4. Secret Containment in Secondary Artifacts
To prevent accidental secret leakage:
- Unredacted input text must never be echoed into error responses, database exception logs, system traces, or worker task parameters.
- Debug logging inside ingestion workers must strictly operate on redacted records or emit only metadata metrics (`event_count`, `byte_size`, `source_id`).

---

## 5. Severity, Timestamps, and Normalization Rules

### 5.1. Severity Mapping Taxonomy
LogPilot normalizes heterogeneous vendor severities into a five-level canonical taxonomy.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SEVERITY MAPPING TAXONOMY                          │
├─────────────────────┬──────────────────────────┬────────────────────────────┤
│ Canonical Severity  │ Source Token Variations  │ Operational Semantics      │
├─────────────────────┼──────────────────────────┼────────────────────────────┤
│ `DEBUG`             │ TRACE, VERBOSE, FINE,    │ Granular diagnostic trace. │
│                     │ FINER, FINEST, DEBUG     │ Excluded from default RCA. │
├─────────────────────┼──────────────────────────┼────────────────────────────┤
│ `INFO`              │ INFO, NOTICE, STATUS,    │ Normal operational event.  │
│                     │ INFORMATIONAL, LOG       │ Baselined for volume.      │
├─────────────────────┼──────────────────────────┼────────────────────────────┤
│ `WARNING`           │ WARN, WARNING, ALERT,    │ Degraded condition, retry, │
│                     │ CAUTION                  │ recoverable failure.       │
├─────────────────────┼──────────────────────────┼────────────────────────────┤
│ `ERROR`             │ ERR, ERROR, EXCEPTION,   │ Unhandled runtime fault,   │
│                     │ SEVERE, FAIL, FAILURE    │ request failure. RCA seed. │
├─────────────────────┼──────────────────────────┼────────────────────────────┤
│ `CRITICAL`          │ FATAL, CRIT, CRITICAL,   │ Process panic, system crash│
│                     │ EMERGENCY, PANIC, CAT    │ immediate incident trigger.│
└─────────────────────┴──────────────────────────┴────────────────────────────┘
```

#### Mapping Rules & Unknown Severities:
1. **Case-Insensitive Normalization:** Source severity strings are stripped, trimmed, and evaluated case-insensitively (e.g., `"warn"`, `"Warning"`, and `"WARN"` map to `WARNING`).
2. **Numeric Syslog Severity Mapping:** RFC 5424 numerical severities map deterministically: `0-1` $\rightarrow$ `CRITICAL`, `2-3` $\rightarrow$ `ERROR`, `4` $\rightarrow$ `WARNING`, `5-6` $\rightarrow$ `INFO`, `7` $\rightarrow$ `DEBUG`.
3. **Unknown or Vendor-Specific Levels:** Unrecognized levels (e.g., `"AUDIT"`, `"CUSTOM_3"`) map to default `INFO`. The original token is preserved in `attributes.original_level` to guarantee lossless semantic preservation.

### 5.2. Timestamp Normalization & Semantics

#### 1. Dual Timestamp Invariant
- **Event Time (`timestamp`):** The point in time when the log event occurred on the monitored host. This timestamp drives windowing, anomaly detection, timeline alignment, and Git commit correlation.
- **Ingestion Time (`ingested_at`):** The point in time when LogPilot's ingestion API received and recorded the batch. Used for system auditing, latency tracking, and deduplication ordering.
- *Rule:* Ingestion time is never used as event time unless the event timestamp is completely missing and unrecoverable.

#### 2. Timezone Normalization
- All timestamps are converted to UTC and stored in PostgreSQL as `TIMESTAMPTZ`.
- Explicit timezone offsets (e.g., `2026-10-25T18:04:12+02:00`, `2026-10-25T11:04:12-05:00`) are normalized to UTC `2026-10-25T16:04:12Z`.
- If an offset is missing, the normalizer defaults to UTC, flags `attributes._tz_assumed: true`, and retains the original raw string in `attributes._raw_timestamp`.

#### 3. Out-of-Order Ingestion & Clock Skew
- Distributed systems frequently emit logs out of order due to network buffering, container teardowns, and async retries.
- The canonical schema supports out-of-order ingestion. The PostgreSQL partition and indexing scheme (`(project_id, timestamp)`) accommodates historical inserts.
- **Clock Skew Thresholds (TBD):** Future heuristic rules may flag events whose event timestamp lies substantially in the future (e.g., $> +10$ minutes from server UTC) as `CLOCK_SKEW_ANOMALY`. In V1, future-dated events beyond $+24$ hours are rejected as invalid timestamps.

---

## 6. Structured Attributes and Correlation Identifiers

### 6.1. Structured Attribute Envelope (`attributes`)
Arbitrary contextual key-value metadata is captured within the `attributes` JSONB dictionary.

#### Guardrails and Constraints:
- **Maximum Serialized Size:** 32 KB per event. Payloads exceeding this limit have leaf values truncated.
- **Maximum Nesting Depth:** 3 levels (e.g., `attributes.network.client.ip`). Deeper nesting is serialized as stringified JSON or flattened.
- **Key Naming Convention:** Snake_case ASCII strings matching regex `^[a-z0-9_.-]{1,64}$`.
- **Reserved Key Collisions:** Top-level canonical field names (`id`, `project_id`, `timestamp`, `level`, `message_raw`) must not appear inside `attributes`. Ingestion normalizers automatically prepend `src_` to colliding user keys (e.g., `attributes.level` becomes `attributes.src_level`).

### 6.2. Standardized Context & Correlation Namespaces
To maximize correlation efficacy across modules, adapters populate standardized attribute keys when available:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       STANDARDIZED ATTRIBUTE TAXONOMY                       │
├─────────────────────┬──────────────────────┬────────────────────────────────┤
│ Namespace           │ Field Name           │ Example Value                  │
├─────────────────────┼──────────────────────┼────────────────────────────────┤
│ **Correlation**     │ `trace_id`           │ "4bf92f3577b34da6a3ce929d0e0e" │
│                     │ `span_id`            │ "00f067aa0ba902b7"             │
│                     │ `request_id`         │ "req_01HPX8K7B9A23"            │
│                     │ `session_id`         │ "sess_99a8b7c6"                │
├─────────────────────┼──────────────────────┼────────────────────────────────┤
│ **Service Context** │ `service.name`       │ "payment-gateway"              │
│                     │ `service.version`    │ "v2.4.1"                       │
│                     │ `service.environment`│ "production"                   │
├─────────────────────┼──────────────────────┼────────────────────────────────┤
│ **Host & Runtime**  │ `host.hostname`      │ "worker-k8s-node-04"           │
│                     │ `host.ip`            │ "10.244.3.18"                  │
│                     │ `container.id`       │ "e2b3c4d5f6a7"                 │
│                     │ `process.pid`        │ 4182                           │
├─────────────────────┼──────────────────────┼────────────────────────────────┤
│ **Code Origin**     │ `code.filepath`      │ "services/billing/charge.py"   │
│                     │ `code.lineno`        │ 184                            │
│                     │ `code.function`      │ "execute_charge"               │
│                     │ `code.namespace`     │ "billing.charge"               │
└─────────────────────┴──────────────────────┴────────────────────────────────┘
```

*Tracing Dependency Note:* Providing `trace_id` or `span_id` is **strictly optional**. LogPilot does not require an active distributed tracing system (OpenTelemetry/Jaeger). When present, correlation IDs accelerate incident correlation; when absent, LogPilot relies on temporal, statistical, and template clustering.

### 6.3. Safe Indexing & Vectorization Strategy
- **Provisional Database Indexing:** Structured attributes in PostgreSQL are proposed for GIN indexing (e.g., `USING gin (attributes jsonb_path_ops)`) to allow low-latency querying on high-cardinality keys like `trace_id` and `service.name`. Specific indexing strategies, path operators, and partial index definitions remain provisional and subject to physical database tuning.
- **Strict Separation of Storage Authority:** PostgreSQL is the **sole authoritative system of record** for all telemetry events. Qdrant serves strictly as a **derived vector retrieval index**. If Qdrant is cleared or degraded, authoritative state in PostgreSQL remains 100% intact, and vector indices can be regenerated by re-embedding stored `log_events`.
- **Vector Embedding Projection:** Vector index embeddings generated for RAG retrieval do not embed the entire raw `attributes` JSON blob. Embeddings are generated exclusively from sanitized `message_raw` and primary contextual anchors (`service.name`, `code.filepath`) to minimize context window bloat and eliminate vector noise.

---

## 7. Schema Versioning and Compatibility

### 7.1. Schema Version vs. Application Version
The Canonical Event Schema maintains an independent versioning lifecycle from the application API:
- **Schema Version (`schema_version`):** Identifies the structural format of the serialized telemetry event record (e.g., `"1.0"`).
- **Application API Version:** The HTTP communication contract published under `/api/v1` in [D06](file:///docs/api/API_CONTRACTS.md).
- Decoupling these versions ensures that backend analytical pipelines can consume historical records or process data across rolling worker updates without requiring API version bumps.

### 7.2. Evolution and Compatibility Invariants

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SCHEMA COMPATIBILITY INVARIANTS                      │
├────────────────────────────┬────────────────────────────────────────────────┤
│ Operation Type             │ Schema Compatibility Guarantee                 │
├────────────────────────────┼────────────────────────────────────────────────┤
│ **Additive Optional Fields**│ Fully Supported. New optional fields in JSONB   │
│                            │ or top-level schemas must have default values. │
├────────────────────────────┼────────────────────────────────────────────────┤
│ **Field Removal / Renaming**│ Prohibited in Minor Versions. Must undergo a   │
│                            │ deprecation cycle spanning at least one major  │
│                            │ release before removal.                        │
├────────────────────────────┼────────────────────────────────────────────────┤
│ **Type Mutation**          │ Strictly Prohibited. A field type change       │
│                            │ constitutes a breaking major schema bump.      │
├────────────────────────────┼────────────────────────────────────────────────┤
│ **Unknown Upstream Keys**  │ Tolerant Reader. Unrecognized keys in incoming │
│                            │ JSON payloads are preserved under `attributes` │
│                            │ rather than failing validation.                │
└────────────────────────────┴────────────────────────────────────────────────┘
```

### 7.3. Worker Behavior on Version Discrepancies
- **Minor Version Discrepancies (`1.0` vs. `1.1`):** Downstream workers (anomaly detectors, embedding indexers) continue processing seamlessly, parsing known fields and ignoring unknown additive properties.
- **Unsupported Major Versions (`2.0` received by `1.x` worker):** The worker halts processing on that batch, logs a fatal contract incompatibility alert, and marks the ingestion run as `FAILED` with error code `UNSUPPORTED_SCHEMA_VERSION`.

---

## 8. Validation, Malformed Records, and Ingestion Outcomes

### 8.1. Validation Matrix and Ingestion Outcomes

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                            VALIDATION MATRIX & INGESTION OUTCOMES                           │
├──────────────────────────┬────────────────────────┬─────────────────────────────────────────┤
│ Ingestion Scenario       │ Record-Level Outcome   │ Ingestion Run Accounting                │
├──────────────────────────┼────────────────────────┼─────────────────────────────────────────┤
│ **Valid Canonical Record**│ Accepted & Persisted   │ `events_processed` incremented (+1).    │
├──────────────────────────┼────────────────────────┼─────────────────────────────────────────┤
│ **Missing Optional Fields** Accepted & Persisted   │ `events_processed` incremented (+1).    │
│                          │ Defaults assigned      │ Optional fields set to null/empty map.  │
├──────────────────────────┼────────────────────────┼─────────────────────────────────────────┤
│ **Partially Parseable**  │ Accepted with Fallbacks│ `events_processed` incremented (+1).    │
│ (e.g., text w/o timestamp│ Server time applied;   │ `attributes._normalization_notes`       │
│ or non-standard level)   │ Level mapped to `INFO` │ records applied fallback rules.         │
├──────────────────────────┼────────────────────────┼─────────────────────────────────────────┤
│ **Oversized Record**     │ Truncated & Accepted   │ `events_processed` incremented (+1).    │
│ (message > 64 KB or      │ Excess truncated;      │ Warning logged in `_normalization_notes`│
│ attributes > 32 KB)      │ Redaction reapplied    │ payload capped at safe boundaries.      │
├──────────────────────────┼────────────────────────┼─────────────────────────────────────────┤
│ **Malformed Input Line** │ Rejected (Single Line) │ `errors_count` incremented (+1).        │
│ (corrupted bytes/syntax) │ Discarded from insert  │ Ingestion run marked `PARTIAL` if other │
│                          │ batch                  │ records in batch succeed.               │
├──────────────────────────┼────────────────────────┼─────────────────────────────────────────┤
│ **Security Violation**   │ Sanitized or Rejected  │ `events_processed` incremented (+1) if  │
│ (unmaskable credential)  │ (Redacted to marker)   │ sanitized; `errors_count` (+1) if drop. │
├──────────────────────────┼────────────────────────┼─────────────────────────────────────────┤
│ **Batch Envelope Crash** │ Batch Rejected (400)   │ Run fails immediately (`FAILED`).       │
│ (unparseable HTTP JSON)  │ Zero records written   │ No records inserted into database.      │
└──────────────────────────┴────────────────────────┴─────────────────────────────────────────┘
```

### 8.2. Ingestion Run Status Semantics
In strict compliance with [D05](file:///docs/architecture/DATABASE_DOMAIN_MODEL.md):
- `COMPLETED`: All records in the batch were valid or safely normalized and successfully committed to `log_events`.
- `PARTIAL`: One or more individual records failed parsing or validation and were skipped, but remaining valid records were successfully committed. `errors_count > 0` and `events_processed > 0`.
- `FAILED`: Fatal batch-level error (database timeout, schema corruption, authentication failure) preventing any records from being committed.

---

## 9. Idempotency and Deduplication

### 9.1. Identity Vectors in Telemetry Ingestion
Reliable log shippers, container agents, and network retry loops inevitably submit duplicate records. To manage idempotency safely without conflating distinct operational occurrences, LogPilot differentiates three distinct layers of identity:

1. **Source-Provided Event Identity (`source_event_id`):** An optional, stable identifier assigned by the upstream producer or collector (e.g., AWS CloudWatch event ID, OTel log record ID, syslog sequential sequence number). When provided, it is preserved under `attributes.source_event_id`.
2. **Ingestion Request / Batch Identity (`ingestion_run_id`):** A server-assigned UUID identifying a specific batch submission. When an HTTP client retries an unacknowledged transmission or recovers from a network timeout, re-submitting with the same batch context allows correlation of retry attempts.
3. **Content-Derived Fingerprint (`event_hash`):** A cryptographic digest computed over normalized event fields to assist in identifying re-transmitted duplicates.

### 9.2. Disambiguating Concurrency from Duplication
A fundamental challenge in distributed telemetry is that **identical message text and identical timestamps do not necessarily mean two events are duplicates**:
- **High-Concurrency Scale:** In distributed systems, multiple worker threads, coroutines, or autoscaled container instances frequently emit identical log lines (e.g., `"Heartbeat OK"`, `"Worker acquired lock"`, or `"Health check succeeded"`) at the exact same second or millisecond.
- **Timestamp Coarseness:** Many upstream logging facilities emit timestamps with low resolution (e.g., whole-second syslog resolution or millisecond truncation). Multiple distinct occurrences within that time slice would collide if timestamps and message bodies alone were treated as a unique identity.
- **Normalization Sensitivity:** Subtle differences in whitespace trimming, attribute key ordering, or Unicode normalization can alter naive hash calculations, causing false negatives in duplicate detection. Conversely, over-aggressive normalization could cause distinct events to falsely match.
- **Partial Ingestion Failures:** In batches where only a subset of events was successfully persisted before a crash, retrying the batch introduces an overlap where already-committed events must be safely recognized without rejecting the remainder of the batch.

### 9.3. Safe Retry Requirements & Provisional Strategy
To ensure safe retries without corrupting downstream analytics, the ingestion pipeline must guarantee:
1. **Idempotent Ingestion Retries:** Re-submitting an identical batch after a network interruption must not result in duplicate `LogEvent` records or inflated event counts.
2. **Deterministic Fingerprint (Candidate Formulation):** As a candidate default, LogPilot computes `event_hash` as:
   $$\text{event\_hash} = \text{SHA256}(\text{project\_id} \parallel \text{log\_source\_id} \parallel \text{timestamp} \parallel \text{message\_raw})$$
   Where `timestamp` uses standardized ISO 8601 UTC microsecond representation and `message_raw` is the sanitized, trimmed body.
3. **Provisional Conflict-Handling Strategy:** One candidate approach is database-level deduplication via upsert:
   ```sql
   -- Candidate evaluation pattern (provisional; not a mandated universal behavior)
   INSERT INTO log_events (id, project_id, log_source_id, timestamp, level, message_raw, attributes, event_hash, ingested_at)
   VALUES (...)
   ON CONFLICT (project_id, log_source_id, event_hash, timestamp) 
   DO NOTHING;
   ```
4. **Unresolved Implementation Decisions (TBD):**
   - The exact `event_hash` formula, including whether `attributes` or collector sequence IDs should be hashed into the digest.
   - The conflict-handling strategy: evaluating database-level `ON CONFLICT DO NOTHING` versus application-layer Redis deduplication caches or Bloom filters during ingestion staging.
   - The deduplication window and uniqueness scope: whether uniqueness constraints should be strictly scoped to a rolling temporal window (e.g., 1 hour, 24 hours, or 30 days) to prevent massive B-tree index degradation over long-term historical tables.
   - Physical table partitioning strategy (e.g., monthly range partitioning on `timestamp`).
   These details remain explicitly designated as **TBD** for physical database design and benchmark evaluation.

---

## 10. Security, Redaction, and Data Minimization

### 10.1. Defense-in-Depth Redaction Model
Telemetry often inadvertently captures high-risk secrets: database passwords, OAuth access tokens, AWS secret keys, private SSH keys, and unencrypted session cookies. LogPilot enforces an uncompromising defense-in-depth sanitization protocol:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DEFENSE-IN-DEPTH REDACTION                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  [ Layer 1: Client-Side Local Agent Pre-Filtering ]                        │
│  - Respects `.logpilotignore` patterns (e.g., excluding `credentials.json`) │
│  - Executes pre-flight regex redaction before transmitting over network     │
│                                │                                            │
│                                ▼                                            │
│  [ Layer 2: Ingestion Gateway Active Detection ]                            │
│  - Server-side regex and high-entropy scanner runs on all incoming batches  │
│  - Masks recognized secret patterns in both `message` and `attributes`      │
│                                │                                            │
│                                ▼                                            │
│  [ Layer 3: Context Minimization for Downstream AI ]                       │
│  - RAG vector indexing embeds only sanitized snippets                       │
│  - Prompts to LLMs exclude uninspected codebase files and raw secret buffers │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.2. Proposed Built-In Redaction Targets & Candidate Rules
In accordance with [ADR-006](file:///docs/adr/adr-006-repository-intelligence-and-secret-redaction.md), the system enforces active secret detection to prevent credentials from entering persistent storage, vector indices, or LLM prompts. The specific detection patterns, entropy thresholds, and replacement tokens in the table below represent candidate defaults; the formal algorithms, exact regular expressions, and configurable rule syntax remain designated as **TBD** and are deferred to [D11 — Security Model](file:///docs/architecture/SECURITY_MODEL.md):

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PROPOSED CANDIDATE SECRET REDACTION RULES                │
├──────────────────────┬─────────────────────────────┬────────────────────────┤
│ Secret Classification│ Proposed Pattern Scope      │ Proposed Mask Token    │
├──────────────────────┼─────────────────────────────┼────────────────────────┤
│ **API & Cloud Keys** │ `AKIA[0-9A-Z]{16}`,         │ `[REDACTED_API_KEY]`   │
│                      │ `ghp_[A-Za-z0-9_]{36}`,     │                        │
│                      │ `sk-[A-Za-z0-9]{48}`        │                        │
├──────────────────────┼─────────────────────────────┼────────────────────────┤
│ **Private Keys**     │ `-----BEGIN PRIVATE KEY---` │ `[REDACTED_PRIV_KEY]`  │
│                      │ `-----BEGIN RSA PRIVATE---` │                        │
├──────────────────────┼─────────────────────────────┼────────────────────────┤
│ **Connection URIs**  │ `postgres://user:pass@host` │ `postgres://[REDACTED] │
│                      │ `mongodb://user:pass@host`  │  @host`                │
├──────────────────────┼─────────────────────────────┼────────────────────────┤
│ **Auth Headers/Tokens│ `Bearer eyJ...`,            │ `Bearer [REDACTED_JWT]`│
│                      │ `Basic [A-Za-z0-9+/=]{16,}` │                        │
├──────────────────────┼─────────────────────────────┼────────────────────────┤
│ **Key-Value Secrets**│ `(?i)(password|secret|token │ `password="[REDACTED]"`│
│                      │ |api_key)\s*[:=]\s*["'][^"']│                        │
└──────────────────────┴─────────────────────────────┴────────────────────────┘
```

### 10.3. Low-Confidence Redaction & Retention Implications
- **Low-Confidence or Ambiguous Sensitive Content:** When the redaction scanner encounters ambiguous strings with low detection confidence, or when an input record appears to contain unstructured sensitive material that cannot be safely normalized, the system must prevent uninspected exposure. Evaluated candidate strategies include:
  1. *Conservative Redaction (Proposed Default):* Masking the suspicious span with generic `[REDACTED]` markers to prioritize data safety over diagnostic verbosity.
  2. *Quarantine & Flagging:* Routing the record into a quarantined state marked for administrative review without publishing it to downstream RAG/LLM workers.
  3. *Record-Level Rejection:* Skipping the ambiguous record and incrementing `ingestion_runs.errors_count` without persisting unverified content.
  The definitive operational policy for low-confidence handling and developer override syntax is formally governed by [D11 — Security Model](file:///docs/architecture/SECURITY_MODEL.md).
- **Raw Payload Retention Invariant:** LogPilot does **not require** permanent retention of unredacted raw source payloads. In V1, PostgreSQL persists only the sanitized `message_raw` and sanitized `attributes`. This zero-unredacted-retention baseline minimizes data liability. Whether raw source payloads may optionally be archived in external cold storage (e.g., S3/MinIO) for audit compliance remains an open policy decision deferred to D11.
- **AI Context Invariant:** Local LLM execution (e.g., local Ollama instance) **does not waive** security controls. Secrets must be masked before prompt assembly regardless of whether inference executes locally or in the cloud. Re-indexing, embedding, or replaying telemetry operates strictly on sanitized records.

---

## 11. Relationship to the Domain Model

The canonical event schema directly corresponds to the PostgreSQL entity model ratified in [D05 — Database & Domain Model](file:///docs/architecture/DATABASE_DOMAIN_MODEL.md):

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     RELATIONAL DOMAIN MAPPING (D05 / D07)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────────┐         ┌────────────────┐         ┌────────────────┐    │
│   │   Project    │◄────────┤   LogSource    │◄────────┤  IngestionRun  │    │
│   └──────┬───────┘         └───────┬────────┘         └────────────────┘    │
│          │                         │                                        │
│          │         ┌───────────────┘                                        │
│          │         ▼                                                        │
│          │  ┌──────────────┐         ┌────────────────┐                     │
│          ├──┤   LogEvent   ├────────►│  LogTemplate   │                     │
│          │  └──────┬───────┘         └────────────────┘                     │
│          │         │                                                        │
│          │         ├────────────────────────┐                               │
│          │         ▼                        ▼                               │
│          │  ┌──────────────┐         ┌────────────────┐                     │
│          │  │IncidentEvent │         │IncidentEvidence│                     │
│          │  └──────┬───────┘         └────────┬───────┘                     │
│          │         │                          │                             │
│          ▼         ▼                          ▼                             │
│   ┌───────────────────────────────────────────────────┐                     │
│   │                     Incident                      │                     │
│   └───────────────────────────────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 11.1. Authoritative vs. Derived State Mapping

| D05 Domain Entity | D07 Event Schema Alignment | Relational Storage & Authority |
|---|---|---|
| `log_sources` | Defines originating telemetry producer (`source_type`, `environment`). | **Authoritative in PostgreSQL.** Immutable parent link for `log_events`. |
| `ingestion_runs` | Tracks batch sync progress (`events_processed`, `errors_count`). | **Authoritative in PostgreSQL.** Transitory operational tracking. |
| `log_events` | Stores normalized canonical event record (`timestamp`, `level`, `message_raw`, `attributes`). | **Authoritative in PostgreSQL.** System of record for all log analytics. |
| `log_templates` | Mined structural patterns (`pattern_raw`, `template_hash`). | **Derived & Aggregated in PostgreSQL.** Cached in Redis (`cache:template:{hash}`). |
| `anomaly_signals`| Statistical deviations over event windows (`window_start`, `window_end`). | **Derived Analytical State in PostgreSQL.** Generated by ML worker. |
| `incident_events`| Associative join table linking `log_events.id` to `incidents.id`. | **Authoritative Relational Join in PostgreSQL.** |
| `incident_evidence`| Captured diagnostic evidence snapshot (`evidence_payload`) and source record pointer (`source_ref` $\rightarrow$ `LogEvent.id`, `commit_sha`, etc.) supporting an RCA hypothesis. | **Authoritative Evidence Record in PostgreSQL.** Provenance is preserved by linking `source_ref` to source entities. Retention and deletion follow incident lifecycle policies. |

### 11.2. Cross-Project Relational Integrity
In strict compliance with D05:
- Adding `project_id` to `log_events` is insufficient on its own to guarantee cross-project isolation.
- The schema requires compound foreign keys and transactional service checks guaranteeing that:
  - `log_events.log_source_id` belongs to the exact same `project_id`.
  - An `IncidentEvent` or `IncidentEvidence` record in Project A cannot link to a `LogEvent` in Project B.
  - Query filters on `log_events` unconditionally bind the verified session `project_id`.

---

## 12. Relationship to APIs and Workers

### 12.1. Ingestion Endpoint Alignment (D06)
In accordance with [D06 — API Contracts](file:///docs/api/API_CONTRACTS.md):
- Ingestion occurs via `POST /api/v1/projects/{project_id}/log-sources/{log_source_id}/ingest`.
- The API accepts a batch payload containing an array of events:
  ```json
  {
    "events": [
      {
        "timestamp": "2026-10-25T16:04:12.102Z",
        "message": "PaymentGatewayTimeout: Connection dropped after 3000ms",
        "level": "ERROR",
        "attributes": {
          "service": "payment-gateway",
          "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736"
        }
      }
    ]
  }
  ```
- **Public API vs. Internal Persisted Representation:**
  - *Public API Ingestion Schema:* Accepts client-supplied fields (`timestamp`, `message`, `level`, `attributes`). Does not accept internal fields (`id`, `project_id`, `event_hash`, `template_id`).
  - *Internal Canonical Record:* Ingestion workers normalize the API payload, attach authoritative identifiers (`id`, `project_id`, `log_source_id`, `ingested_at`, `event_hash`), and persist the expanded representation into PostgreSQL `log_events`.

### 12.2. Downstream Worker Consumption Contracts
1. **Template Miner Worker:** Consumes freshly inserted `log_events` in micro-batches; matches patterns against `log_templates`; updates `log_events.template_id`.
2. **Anomaly Detection Worker:** Reads windowed aggregates from Redis feature buffers; detects rate spikes or novel template deviations; writes `anomaly_signals`.
3. **Incident Correlator Worker:** Evaluates `anomaly_signals` against open incidents; groups correlated `log_events` into `incident_events`.
4. **RCA Context Worker:** Extracts critical `log_events` and attached stack traces; compiles forensic snippets into `incident_evidence`.

---

## 13. Canonical Examples

### Example 1: Structured JSON Application Log

#### Raw Input (Collector Inbound):
```json
{
  "time": "2026-10-25T16:04:12.102Z",
  "lvl": "error",
  "msg": "Database connection pool exhausted",
  "app": "checkout-service",
  "env": "production",
  "pool": {
    "active": 50,
    "max": 50,
    "waiting": 14
  },
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "db_url": "postgres://pgadmin:SuperSecretPass123@postgres.internal:5432/orders"
}
```

#### Normalized Canonical LogEvent (Persisted Representation):
```json
{
  "id": "e4a1b2c3-d4e5-4f6a-8b9c-0d1e2f3a4b5c",
  "project_id": "e4b9b9c0-9f5a-4b71-923c-1b772c68a4e1",
  "log_source_id": "7b54359d-648b-4a57-b087-76b325298a01",
  "timestamp": "2026-10-25T16:04:12.102000Z",
  "ingested_at": "2026-10-25T16:04:12.305112Z",
  "level": "ERROR",
  "message_raw": "Database connection pool exhausted",
  "attributes": {
    "service.name": "checkout-service",
    "service.environment": "production",
    "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
    "pool": {
      "active": 50,
      "max": 50,
      "waiting": 14
    },
    "db_url": "postgres://pgadmin:[REDACTED_PASSWORD]@postgres.internal:5432/orders"
  },
  "template_id": "9f12a3b4-c5d6-4e7f-8a9b-0c1d2e3f4a5b",
  "event_hash": "a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0",
  "schema_version": "1.0"
}
```

---

### Example 2: Plain-Text Log Normalized into Canonical Event

#### Raw Input (Collector Inbound):
```text
2026-10-25 18:04:12.450+02:00 [WARN] billing.processor: Failed to connect to payment gateway retry=3/5 delay=500ms
```

#### Normalized Canonical LogEvent (Persisted Representation):
```json
{
  "id": "b1c2d3e4-f5a6-4b7c-8d9e-0f1a2b3c4d5e",
  "project_id": "e4b9b9c0-9f5a-4b71-923c-1b772c68a4e1",
  "log_source_id": "7b54359d-648b-4a57-b087-76b325298a01",
  "timestamp": "2026-10-25T16:04:12.450000Z",
  "ingested_at": "2026-10-25T16:04:13.010203Z",
  "level": "WARNING",
  "message_raw": "Failed to connect to payment gateway retry=3/5 delay=500ms",
  "attributes": {
    "code.namespace": "billing.processor",
    "retry.count": 3,
    "retry.max": 5,
    "retry.delay_ms": 500,
    "_raw_timestamp": "2026-10-25 18:04:12.450+02:00"
  },
  "template_id": "8e9f0a1b-2c3d-4e5f-6a7b-8c9d0e1f2a3b",
  "event_hash": "f6e5d4c3b2a109876543210fedcba9876543210fedcba9876543210fedcba987",
  "schema_version": "1.0"
}
```

---

### Example 3: Event with Trace and Correlation Identifiers

#### Raw Input (Collector Inbound):
```json
{
  "timestamp": "2026-10-25T16:05:00.000Z",
  "message": "HTTP 504 Gateway Timeout on POST /api/v1/charge",
  "level": "ERROR",
  "attributes": {
    "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
    "span_id": "00f067aa0ba902b7",
    "request_id": "req_01HPX8K7B9A23",
    "http.method": "POST",
    "http.target": "/api/v1/charge",
    "http.status_code": 504
  }
}
```

#### Normalized Canonical LogEvent (Persisted Representation):
```json
{
  "id": "c2d3e4f5-a6b7-4c8d-9e0f-1a2b3c4d5e6f",
  "project_id": "e4b9b9c0-9f5a-4b71-923c-1b772c68a4e1",
  "log_source_id": "7b54359d-648b-4a57-b087-76b325298a01",
  "timestamp": "2026-10-25T16:05:00.000000Z",
  "ingested_at": "2026-10-25T16:05:00.124500Z",
  "level": "ERROR",
  "message_raw": "HTTP 504 Gateway Timeout on POST /api/v1/charge",
  "attributes": {
    "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
    "span_id": "00f067aa0ba902b7",
    "request_id": "req_01HPX8K7B9A23",
    "http.method": "POST",
    "http.target": "/api/v1/charge",
    "http.status_code": 504
  },
  "template_id": "7d8e9f0a-1b2c-3d4e-5f6a-7b8c9d0e1f2a",
  "event_hash": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3",
  "schema_version": "1.0"
}
```

---

### Example 4: Malformed or Partially Parseable Input

#### Raw Input (Collector Inbound):
```text
System panic at unknown thread! Memory allocation failed (no timestamp, no brackets)
```

#### Normalized Canonical LogEvent (Persisted Representation with Fallbacks):
```json
{
  "id": "d3e4f5a6-b7c8-4d9e-0f1a-2b3c4d5e6f7a",
  "project_id": "e4b9b9c0-9f5a-4b71-923c-1b772c68a4e1",
  "log_source_id": "7b54359d-648b-4a57-b087-76b325298a01",
  "timestamp": "2026-10-25T16:06:12.890123Z",
  "ingested_at": "2026-10-25T16:06:12.890123Z",
  "level": "INFO",
  "message_raw": "System panic at unknown thread! Memory allocation failed (no timestamp, no brackets)",
  "attributes": {
    "_normalization_notes": [
      "Missing timestamp in raw input: defaulted to ingestion receipt time.",
      "Missing severity token in raw input: defaulted to INFO."
    ],
    "_tz_assumed": true
  },
  "template_id": null,
  "event_hash": "c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4",
  "schema_version": "1.0"
}
```

---

### Example 5: Redacted Event Demonstrating Secret Masking

#### Raw Input (Collector Inbound):
```text
2026-10-25 16:07:00 [ERROR] AuthenticationFailed: Failed AWS STS AssumeRole using secret_key="sk-ant-api03-abcdef1234567890abcdef1234567890" for user token Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.doNotLeakThisSignature
```

#### Normalized Canonical LogEvent (Persisted Representation):
```json
{
  "id": "e4f5a6b7-c8d9-4e0f-1a2b-3c4d5e6f7a8b",
  "project_id": "e4b9b9c0-9f5a-4b71-923c-1b772c68a4e1",
  "log_source_id": "7b54359d-648b-4a57-b087-76b325298a01",
  "timestamp": "2026-10-25T16:07:00.000000Z",
  "ingested_at": "2026-10-25T16:07:00.450123Z",
  "level": "ERROR",
  "message_raw": "AuthenticationFailed: Failed AWS STS AssumeRole using secret_key=\"[REDACTED_API_KEY]\" for user token Bearer [REDACTED_JWT]",
  "attributes": {
    "auth.mechanism": "AWS_STS_AssumeRole",
    "_redacted_items_count": 2
  },
  "template_id": "5f6a7b8c-9d0e-1f2a-3b4c-5d6e7f8a9b0c",
  "event_hash": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5",
  "schema_version": "1.0"
}
```

---

### Example 6: Versioned Normalized Event

#### Serialized Canonical LogEvent (`schema_version: "1.0"`):
```json
{
  "id": "f5a6b7c8-d9e0-4f1a-2b3c-4d5e6f7a8b9c",
  "project_id": "e4b9b9c0-9f5a-4b71-923c-1b772c68a4e1",
  "log_source_id": "7b54359d-648b-4a57-b087-76b325298a01",
  "timestamp": "2026-10-25T16:08:30.500000Z",
  "ingested_at": "2026-10-25T16:08:30.820100Z",
  "level": "CRITICAL",
  "message_raw": "Fatal worker crash: OutOfMemoryError in container worker-04",
  "attributes": {
    "host.hostname": "k8s-node-02",
    "container.id": "worker-04",
    "process.exit_code": 137,
    "memory.limit_bytes": 1073741824,
    "memory.usage_bytes": 1073741824
  },
  "template_id": "4a5b6c7d-8e9f-0a1b-2c3d-4e5f6a7b8c9d",
  "event_hash": "e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6",
  "schema_version": "1.0"
}
```

---

## 14. Test and Acceptance Checklist

The canonical schema must be validated through automated test suites prior to deployment:

- [ ] **Field Type & Constraint Enforcement:** Validates that Pydantic models reject records missing required logical fields (`id`, `project_id`, `log_source_id`, `timestamp`, `level`, `message_raw`, `schema_version`).
- [ ] **Severity Normalization:** Tests that lowercase, capitalized, and RFC 5424 syslog numeric levels map deterministically to `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`.
- [ ] **Unknown Severity Preservation:** Tests that unrecognized levels (e.g., `"EMERG"`, `"CUSTOM"`) map to `INFO` with the original token recorded in `attributes.original_level`.
- [ ] **Timestamp Parsing & Timezone Conversion:** Verifies that offsets (`+02:00`, `-05:00`, `Z`) convert accurately to UTC without loss of precision.
- [ ] **Missing Timestamp Fallback:** Confirms that records without timestamps default safely to server `ingested_at` time and set `_tz_assumed: true`.
- [ ] **Attribute Size & Depth Bounds:** Verifies that attributes exceeding proposed default limits (e.g., 32 KB or 3 nesting levels) are bounded/truncated without unhandled crashes.
- [ ] **Reserved Field Collision Handling:** Ensures that user keys matching top-level field names (e.g., `attributes.level`) are safely prefixed as `attributes.src_level`.
- [ ] **Candidate Secret Masking:** Proves that credentials matching active detection rules in both `message_raw` and `attributes` are masked before persistence.
- [ ] **Idempotent Retry Handling:** Proves that re-ingesting an identical batch after a network interruption does not create duplicate `LogEvent` records or skew anomaly counts.
- [ ] **Multi-Tenant Isolation:** Asserts that queries filtering by Project A never return `log_events` belonging to Project B under any circumstances.
- [ ] **Entity Separation & Evidence Provenance:** Verifies that `log_events` does not contain inline anomaly detection state or direct incident domain attributes, and that `IncidentEvidence` maintains valid `source_ref` references.

---

## 15. Open Decisions and Traceability (TBD Register)

In accordance with LogPilot architectural governance, open technical decisions and implementation details are registered below without premature resolution:

| Decision ID | Open Architectural Decision | Architectural Significance & Context | Target Phase / Document |
|---|---|---|---|
| **TBD-D07-01** | **Raw Payload Cold Storage Retention** | Evaluates whether complete, unredacted incoming raw payloads should be archived in cold S3/MinIO buckets for audit replay vs. discarded after normalization to minimize data liability. | [D11 — Security Model](file:///docs/architecture/SECURITY_MODEL.md) / Implementation |
| **TBD-D07-02** | **Clock-Skew Thresholds & Correction** | Establishes acceptable time drift thresholds between distributed client clocks and server UTC, and defines when an event is rejected vs. flagged with `CLOCK_SKEW_ANOMALY`. | [D08 — ML & RCA Architecture](file:///docs/architecture/ML_RCA_ARCHITECTURE.md) |
| **TBD-D07-03** | **Log Template Mining Algorithm Selection** | Selects the formal parameter extraction algorithm (e.g., Drain3, Spell, LenMa, or AEL) and determines whether parameter tokens use `<*>` or typed placeholders (`<IP>`, `<NUM>`). | [D08 — ML & RCA Architecture](file:///docs/architecture/ML_RCA_ARCHITECTURE.md) |
| **TBD-D07-04** | **Multi-Line Stack Trace Buffer Window** | Configures ingestion buffer timeout windows (e.g., 250ms vs. 500ms) for assembling multi-line stack traces emitted over asynchronous container log streams. | Local Agent / Collector Implementation |
| **TBD-D07-05** | **Indexable Attribute Allowlist Policy** | Defines whether GIN JSONB index path indexing applies globally or is restricted to a curated allowlist (`trace_id`, `service.name`, `http.status_code`) to conserve storage. | Database Tuning / Performance Phase |
| **TBD-D07-06** | **Deduplication Strategy & Partitioning Window** | Evaluates database-level `ON CONFLICT` constraints vs. application/cache deduplication, and determines whether deduplication uniqueness is bounded to rolling partition windows. | Database Migrations / Phase 2 |
| **TBD-D07-07** | **Configurable User Redaction Syntax & Exact Masking Rules** | Selects the configuration schema (YAML regex lists vs. UI rules), exact entropy thresholds, and definitive low-confidence handling policies. | [D11 — Security Model](file:///docs/architecture/SECURITY_MODEL.md) |
| **TBD-D07-08** | **Pydantic Serialization Library Tooling** | Evaluates high-performance serialization libraries (`pydantic-core` / `orjson`) for micro-batch transformation inside high-throughput ingestion workers. | Backend Implementation Phase |
| **TBD-D07-09** | **Maximum Record & Attribute Size Tuning** | Benchmarks proposed default size ceilings (64 KB message, 32 KB attributes, 3-level depth) under real-world microservice workloads. | Performance & Ingestion Benchmarking |
| **TBD-D07-10** | **Schema Migration & Backward Compatibility Tooling** | Defines automated contract drift detection tooling and background backfill runners for historical schema migrations. | CI/CD & Pipeline Tooling Phase |

---

## 16. Relationship to Downstream Specifications

This document (**D07**) standardizes the canonical event contract. Downstream system components consume and build upon this specification:

- **[D05 — Database & Domain Model](file:///docs/architecture/DATABASE_DOMAIN_MODEL.md):** Defines table schemas, foreign key cascade behaviors, and indexes for `log_events`.
- **[D06 — API Contracts](file:///docs/api/API_CONTRACTS.md):** Defines the external transport contract for log ingestion endpoints.
- **[D08 — ML & RCA Architecture](file:///docs/architecture/ML_RCA_ARCHITECTURE.md):** Defines feature vector extraction from `log_events` and template frequency anomaly scoring.
- **[D09 — RAG Architecture](file:///docs/architecture/RAG_ARCHITECTURE.md):** Defines vector chunking, token bounding, and similarity search over sanitized log events.
- **[D10 — LLM Architecture](file:///docs/architecture/LLM_ARCHITECTURE.md):** Defines prompt assembly of forensic log snippets into LLM context windows.
- **[D11 — Security Model](file:///docs/architecture/SECURITY_MODEL.md):** Defines enterprise RBAC, secret detection regular expressions, and tenant isolation audit controls.
- **[D12 — Evaluation & Research Framework](file:///docs/architecture/EVALUATION_FRAMEWORK.md):** Defines benchmark datasets, log replay harnesses, and RCA precision/recall scoring.
