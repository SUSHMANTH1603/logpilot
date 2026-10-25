# LogPilot — API Contracts & Interface Definitions

**Document ID:** D06  
**Status:** Draft for Architecture Review  
**Parent Documents:** [D01 — Product Requirements Document](file:///docs/requirements/PRD.md), [D02 — V1 Scope & Acceptance Criteria](file:///docs/requirements/V1_SCOPE.md), [D03 — System Architecture Document](file:///docs/architecture/SYSTEM_ARCHITECTURE.md), [D04 — Repository Architecture Document](file:///docs/architecture/REPOSITORY_ARCHITECTURE.md), [D05 — Database & Domain Model Document](file:///docs/architecture/DATABASE_DOMAIN_MODEL.md)  
**Project:** LogPilot: An Intelligent Observability and Root Cause Analysis Platform  

---

## 1. Objective & Scope

The purpose of this document is to establish the authoritative **V1 HTTP REST API Contract** for LogPilot. 

This contract serves as the interoperability specification binding all system clients and workers:
- **Local LogPilot Agent:** Streaming pre-filtered log batches, Git metadata, and local repository topology.
- **Web Dashboard:** Incident exploration, log tailing, timeline inspection, RCA reviews, and system settings.
- **VS Code Extension:** Developer-centric incident triage, inline code diagnostics, and jump-to-source navigation.
- **Async Workers & Micro-Tasks:** Operation coordination, batch status inspection, and background job polling.

The API contract strictly operationalizes the product requirements and domain models approved in [D01](file:///docs/requirements/PRD.md), [D02](file:///docs/requirements/V1_SCOPE.md), [D03](file:///docs/architecture/SYSTEM_ARCHITECTURE.md), [D04](file:///docs/architecture/REPOSITORY_ARCHITECTURE.md), and [D05](file:///docs/architecture/DATABASE_DOMAIN_MODEL.md). It is a contract specification only; no application implementation code, client SDK generation, or migrations are created in this task.

---

## 2. API Design Principles

The LogPilot HTTP API adheres to twelve fundamental design principles:

1. **RESTful Resource Orientation:** Endpoints represent nouns (`projects`, `log-sources`, `incidents`, `evidence`) manipulated via standard HTTP methods (`GET`, `POST`, `PATCH`, `DELETE`).
2. **Strict Versioned Namespace:** All V1 API endpoints are published exclusively under the `/api/v1` prefix.
3. **Pydantic as Canonical Schema Authority:** Backend Python Pydantic models define all request validation and response serialization schemas.
4. **OpenAPI as the Machine-Readable Contract:** FastAPI automatically compiles the OpenAPI 3.1 specification, serving as the single source of truth for downstream toolchains.
5. **Generated Client Bindings:** TypeScript types and API client classes are strictly generated from OpenAPI into `packages/client/`. No manual duplicate TypeScript interfaces are permitted.
6. **Decoupled Architecture:** Route handlers act strictly as transport adapters. Complex domain rules and persistence transactions reside entirely in domain services (`apps/api/src/logpilot_api/modules/*`).
7. **Server-Side Authorization Enforcement:** Access control and multi-tenant project isolation are enforced strictly on the server; client-provided metadata is never trusted as proof of authorization.
8. **Principal-Scoped Access:** Every project-scoped request is validated against the authenticated principal's project membership and role permissions.
9. **Zero Secret Exposure:** API request/response envelopes never accept, log, or return plaintext API keys, database credentials, JWT secrets, or unredacted passwords.
10. **Non-Blocking Asynchronous Ingestion:** Long-running operations (log parsing, anomaly detection, vector indexing, LLM synthesis) return `202 Accepted` with a job tracking handle; HTTP handlers never block indefinitely.
11. **Contract Stability & Versioning:** Existing endpoints must preserve backward compatibility. Breaking schema mutations require an explicit minor/major version increment.
12. **Safe, Predictable Error Envelopes:** All error responses adhere to a uniform, machine-readable envelope with zero stack trace or internal database leakages.

---

## 3. Authentication & Authorization Model

LogPilot distinguishes sharply between **Authentication Identity** (who the caller is) and **Project Authorization** (what project resources the caller can access).

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       AUTHENTICATION & AUTHORIZATION FLOW                   │
│                                                                             │
│  Inbound Request ──► Bearer Token (JWT) or Ingestion Token (API Key)       │
│                               │                                             │
│                               ▼                                             │
│  [ Authentication Layer ] ──► Validates cryptographic signature             │
│                               Resolves authenticated `User` or `LogSource`  │
│                               │                                             │
│                               ▼                                             │
│  [ Authorization Layer ]  ──► Resolves `ProjectMembership` for User         │
│                               Validates URL path `:project_id`              │
│                               Enforces Role: OWNER / ENGINEER / VIEWER      │
│                               │                                             │
│                               ▼                                             │
│  [ Execution Context ]    ──► Passes verified `(user_id, project_id, role)` │
│                               to Application Domain Service                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.1. Authentication Context
- **User Authentication:** Developers and operators authenticate using Bearer tokens (JSON Web Tokens) supplied via the `Authorization: Bearer <token>` HTTP header.
- **Agent / Log Source Ingestion:** Automated agents and telemetry shippers authenticate using source-scoped API keys supplied via the `X-LogPilot-Source-Key: <key>` header.
- **Unauthenticated Handling (`401 Unauthorized`):** Returned when credentials are missing, malformed, expired, or cryptographically invalid.

### 3.2. Project Membership & Roles
In accordance with [D05](file:///docs/architecture/DATABASE_DOMAIN_MODEL.md), authorization is scoped to project memberships across three baseline roles:
1. **`OWNER`:** Full administration rights over the project (manage memberships, update project settings, register repositories, delete sources).
2. **`ENGINEER`:** Active diagnostic and operational access (submit logs, triage incidents, transition lifecycle states, trigger RCA explanations, add investigation notes).
3. **`VIEWER`:** Read-only access (view dashboards, inspect incidents, read explanations and audit logs).

### 3.3. Authorization Enforcement Invariants
- **No Client Trust:** Never trust a client-supplied `project_id` in request payloads as proof of access. The URL path parameter `:project_id` is validated against the authenticated user's `project_memberships` in PostgreSQL.
- **Access Violation Handling (`403 Forbidden` vs. `404 Not Found`):** If an authenticated user attempts to access a project for which they hold no membership, the API returns `404 Not Found` to prevent project enumeration; if they hold membership but insufficient role permissions (e.g., `VIEWER` attempting to update incident state), the API returns `403 Forbidden`.

*Implementation Status Note:* Specific JWT claims, token refresh lifecycles, and cryptographic algorithms remain explicitly **TBD** and are deferred to [D11 — Security Model](file:///docs/architecture/SECURITY_MODEL.md).

---

## 4. Canonical Response Conventions & Status Codes

All API endpoints adhere to standardized HTTP status codes and consistent response payloads.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          HTTP STATUS CODE TAXONOMY                          │
├──────────────┬────────────────────────┬─────────────────────────────────────┤
│ Status Code  │ Standard Meaning       │ LogPilot Application Context        │
├──────────────┼────────────────────────┼─────────────────────────────────────┤
│ `200 OK`     │ Successful Operation   │ Synchronous reads, updates, and RCA │
│ `201 Created`│ Resource Created       │ Synchronous resource creation       │
│ `202 Accepted` Background Work Enqueued│ Async log ingestion, RCA synthesis │
│ `204 No Content` Empty Success         │ Resource deletion                   │
│ `400 Bad Request` Client Syntax Error │ Malformed JSON or semantic payload  │
│ `401 Unauthorized` Auth Missing/Invalid│ Missing or expired bearer token     │
│ `403 Forbidden` Insufficient Perms     │ User lacks project role privileges  │
│ `404 Not Found` Missing Entity / Hide  │ Resource does not exist or hidden   │
│ `409 Conflict` Invalid State Transition│ Lifecycle state machine collision   │
│ `422 Unprocessable` Validation Failure│ Pydantic schema validation error    │
│ `429 Too Many` Rate Limit Exceeded     │ Ingestion rate limit throttled      │
│ `500 Internal Error` Unexpected Crash │ Unhandled server-side exception     │
└──────────────┴────────────────────────┴─────────────────────────────────────┘
```

### 4.1. Standardized Error Response Envelope
Every error condition ($4xx$ and $5xx$) returns a deterministic JSON schema:
```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "The requested incident does not exist in this project.",
    "request_id": "req_01HPX7K9V4N38M2ZB71Q",
    "details": []
  }
}
```
- `code` (string): Stable machine-readable enum (e.g., `UNAUTHORIZED`, `INVALID_STATE_TRANSITION`, `VALIDATION_ERROR`, `RATE_LIMITED`).
- `message` (string): Safe, user-friendly descriptive string with zero internal system details.
- `request_id` (string): Traceability identifier correlating client requests with backend application logs.
- `details` (array): Optional list of field-specific validation errors (e.g., `[{"field": "level", "issue": "Invalid log level"}]`).

---

## 5. Pagination, Filtering & Time Range Standards

To protect against memory exhaustion and latency degradation, collection endpoints enforce uniform pagination and time filtering.

### 5.1. Pagination Parameters
- `page` (integer, query, default: `1`): 1-indexed page number.
- `limit` (integer, query, default: `20`, maximum: `100`): Maximum items per page.

### 5.2. Standard Paginated Response Envelope
```json
{
  "items": [],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total_items": 142,
    "total_pages": 8,
    "has_next": true,
    "has_prev": false
  }
}
```

### 5.3. Time Filtering Conventions
- All time-based query parameters accept ISO 8601 UTC strings:
  - `start_time` (string, query): Inclusive lower bound (e.g., `2026-10-25T12:00:00Z`).
  - `end_time` (string, query): Inclusive upper bound (e.g., `2026-10-25T14:30:00Z`).
- If omitted, default query windows are bounded according to project configuration (e.g., past 24 hours for incidents).

---

## 6. Asynchronous Processing & Ingestion Contract

Because LogPilot must process high-volume telemetry without blocking client HTTP threads, telemetry ingestion follows an **asynchronous job model**:

```
Client (Local Agent / App)                   FastAPI Backend                 Redis / Worker
        │                                           │                               │
        │─── POST /log-sources/{id}/ingest ────────►│                               │
        │    (Batch of 500 log events)              │                               │
        │                                           │─── Enqueue Ingestion Run ────►│
        │◄── HTTP 202 Accepted ─────────────────────│    (Task ID in Redis)         │
        │    (ingestion_run_id, status: "QUEUED")   │                               │
        │                                           │                               │
        │                                           │                               ▼
        │                                           │                    Parse & Normalization
        │                                           │                    Template Extraction
        │                                           │                    Write to PostgreSQL
        │                                           │                               │
        │─── GET /ingestion-runs/{id} ─────────────►│                               │
        │                                           │◄── Query IngestionRun Status ─│
        │◄── HTTP 200 OK ───────────────────────────│                               │
        │    (status: "COMPLETED", processed: 500)  │                               │
```

### Asynchronous Status Enum (`JobStatus`):
- `QUEUED`: Batch registered and buffered in Redis queue.
- `RUNNING`: Worker actively parsing, normalizing, and template mining.
- `COMPLETED`: Ingestion finished; events written to PostgreSQL.
- `FAILED`: Fatal processing error; unparseable items isolated to fallback.
- `PARTIAL`: Batch completed with non-fatal errors recorded.

---

## 7. Endpoint Catalog (V1)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          V1 ENDPOINT ROUTING CATALOG                        │
├───────────────────┬─────────────────────────────────────────────────────────┤
│ Group             │ Endpoints                                               │
├───────────────────┼─────────────────────────────────────────────────────────┤
│ Health & Meta     │ `GET /api/v1/health`                                    │
├───────────────────┼─────────────────────────────────────────────────────────┤
│ Projects & Teams  │ `POST /api/v1/projects`                                 │
│                   │ `GET /api/v1/projects`                                  │
│                   │ `GET /api/v1/projects/{project_id}`                     │
│                   │ `GET /api/v1/projects/{project_id}/members`             │
│                   │ `POST /api/v1/projects/{project_id}/members`            │
├───────────────────┼─────────────────────────────────────────────────────────┤
│ Repositories & Git│ `POST /api/v1/projects/{project_id}/repositories`       │
│                   │ `GET /api/v1/projects/{project_id}/repositories`        │
│                   │ `GET /api/v1/projects/{project_id}/repositories/{repo_id}`
│                   │ `GET /api/v1/projects/{project_id}/repositories/{repo_id}/revisions`
├───────────────────┼─────────────────────────────────────────────────────────┤
│ Log Ingestion     │ `POST /api/v1/projects/{project_id}/log-sources`        │
│                   │ `GET /api/v1/projects/{project_id}/log-sources`         │
│                   │ `GET /api/v1/projects/{project_id}/log-sources/{src_id}`│
│                   │ `POST /api/v1/projects/{project_id}/log-sources/{src_id}/ingest`
│                   │ `GET /api/v1/projects/{project_id}/ingestion-runs/{run_id}`
├───────────────────┼─────────────────────────────────────────────────────────┤
│ Incidents & Events│ `GET /api/v1/projects/{project_id}/incidents`           │
│                   │ `GET /api/v1/projects/{project_id}/incidents/{inc_id}`  │
│                   │ `GET /api/v1/projects/{project_id}/incidents/{inc_id}/events`
│                   │ `GET /api/v1/projects/{project_id}/incidents/{inc_id}/evidence`
│                   │ `PATCH /api/v1/projects/{project_id}/incidents/{inc_id}/state`
├───────────────────┼─────────────────────────────────────────────────────────┤
│ RCA & Synthesis   │ `GET /api/v1/projects/{project_id}/incidents/{inc_id}/rca`
│                   │ `POST /api/v1/projects/{project_id}/incidents/{inc_id}/rca/explain`
├───────────────────┼─────────────────────────────────────────────────────────┤
│ Investigations    │ `GET /api/v1/projects/{project_id}/incidents/{inc_id}/investigation`
│                   │ `PATCH /api/v1/projects/{project_id}/incidents/{inc_id}/investigation`
├───────────────────┼─────────────────────────────────────────────────────────┤
│ Configuration     │ `GET /api/v1/projects/{project_id}/configuration`       │
│                   │ `PUT /api/v1/projects/{project_id}/configuration`       │
├───────────────────┼─────────────────────────────────────────────────────────┤
│ Audit             │ `GET /api/v1/projects/{project_id}/audit-records`       │
└───────────────────┴─────────────────────────────────────────────────────────┘
```

---

### 7.1. Health & Service Metadata

#### `GET /api/v1/health`
- **Purpose:** Public readiness and liveness check for Docker Compose health probes and monitoring agents.
- **Authentication:** None (Public).
- **Execution:** Synchronous.
- **Responses:**
  - `200 OK`: `{"status": "HEALTHY", "version": "1.0.0", "timestamp": "2026-10-25T16:00:00Z"}`
  - `503 Service Unavailable`: Database or critical storage connectivity lost.
- **Security Constraint:** Never returns connection strings, internal IP addresses, database versions, or memory statistics.

---

### 7.2. Projects & Membership

#### `POST /api/v1/projects`
- **Purpose:** Create a new isolated workspace project.
- **Authentication:** Bearer token required.
- **Request Body:**
  ```json
  {
    "name": "Checkout Service",
    "slug": "checkout-service",
    "description": "Production payment and checkout pipeline"
  }
  ```
- **Responses:**
  - `201 Created`: Project details object. Creator automatically assigned `OWNER` role.
  - `400 Bad Request`: Malformed payload.
  - `409 Conflict`: `slug` already exists.
  - `422 Unprocessable Entity`: Validation failure.

#### `GET /api/v1/projects`
- **Purpose:** List all projects where the authenticated user holds membership.
- **Authentication:** Bearer token required.
- **Query Parameters:** `page`, `limit`.
- **Responses:**
  - `200 OK`: Paginated list of projects with user's assigned role in each.

#### `GET /api/v1/projects/{project_id}`
- **Purpose:** Retrieve project details and telemetry summary.
- **Authentication:** Bearer token required.
- **Project Authorization:** Requires `VIEWER`, `ENGINEER`, or `OWNER` role.
- **Responses:**
  - `200 OK`: Project entity details.
  - `404 Not Found`: Project does not exist or user lacks membership.

#### `GET /api/v1/projects/{project_id}/members`
- **Purpose:** List project members and their assigned roles.
- **Authentication:** Bearer token required.
- **Project Authorization:** Requires `VIEWER`, `ENGINEER`, or `OWNER`.
- **Responses:**
  - `200 OK`: List of member records (`user_id`, `email`, `role`, `joined_at`).

#### `POST /api/v1/projects/{project_id}/members`
- **Purpose:** Add a user to the project or update an existing member's role.
- **Authentication:** Bearer token required.
- **Project Authorization:** Requires explicit project-management permission (held by the `OWNER` role in the baseline authorization model). An `ENGINEER` or `VIEWER` is strictly forbidden from adding members, assigning roles, escalating another user's privileges, or granting themselves `OWNER` status. Any unauthorized attempt returns `403 Forbidden`.
- **Request Body:**
  ```json
  {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "role": "ENGINEER"
  }
  ```
- **Responses:**
  - `200 OK`: Updated membership record (`user_id`, `project_id`, `role`, `joined_at`).
  - `400 Bad Request`: Malformed payload or invalid role value.
  - `403 Forbidden`: Authenticated user lacks project-management permission or attempted unauthorized privilege escalation.
  - `404 Not Found`: User or Project not found.
- **Specification Boundary:** Detailed role-permission mappings and fine-grained administrative access controls are deferred to [D11 — Security Model](file:///docs/architecture/SECURITY_MODEL.md).

---

### 7.3. Repositories & Git Context

#### `POST /api/v1/projects/{project_id}/repositories`
- **Purpose:** Register a source repository with a project for context intelligence and RCA indexing.
- **Authentication:** Bearer token required.
- **Project Authorization:** Requires `ENGINEER` or `OWNER`.
- **Request Body:**
  ```json
  {
    "name": "checkout-backend",
    "vcs_url": "https://github.com/org/checkout-backend.git",
    "default_branch": "main"
  }
  ```
- **Responses:**
  - `201 Created`: Registered repository details with `indexing_status: "PENDING"`.
  - `409 Conflict`: Repository with same name already registered in project.

#### `GET /api/v1/projects/{project_id}/repositories`
- **Purpose:** List registered code repositories for a project.
- **Authentication:** Bearer token required.
- **Project Authorization:** Requires `VIEWER`, `ENGINEER`, or `OWNER`.
- **Responses:**
  - `200 OK`: List of repository objects.

#### `GET /api/v1/projects/{project_id}/repositories/{repository_id}`
- **Purpose:** Retrieve repository status and indexing health.
- **Authentication:** Bearer token required.
- **Project Authorization:** Requires `VIEWER`, `ENGINEER`, or `OWNER`.
- **Responses:**
  - `200 OK`: Repository object including `indexing_status`, `indexed_at`, and default branch.
  - `404 Not Found`: Repository not found or belongs to another project.

#### `GET /api/v1/projects/{project_id}/repositories/{repository_id}/revisions`
- **Purpose:** Retrieve recent Git revisions harvested by the Local Agent or Git scanner.
- **Authentication:** Bearer token required.
- **Project Authorization:** Requires `VIEWER`, `ENGINEER`, or `OWNER`.
- **Query Parameters:** `limit` (default: 20).
- **Responses:**
  - `200 OK`: List of `RepositoryRevision` items (`commit_sha`, `author_name`, `message`, `committed_at`).

---

### 7.4. Log Sources & Ingestion

#### `POST /api/v1/projects/{project_id}/log-sources`
- **Purpose:** Register a telemetry emitter under a project.
- **Authentication:** Bearer token required.
- **Project Authorization:** Requires `ENGINEER` or `OWNER`.
- **Request Body:**
  ```json
  {
    "name": "payment-api-stdout",
    "source_type": "FILE",
    "environment": "production"
  }
  ```
- **Responses:**
  - `201 Created`: Log source details including an internal `ingestion_key` for shippers.
  - `409 Conflict`: Name already in use for specified environment.

#### `GET /api/v1/projects/{project_id}/log-sources`
- **Purpose:** List all configured log sources for a project.
- **Authentication:** Bearer token required.
- **Project Authorization:** Requires `VIEWER`, `ENGINEER`, or `OWNER`.
- **Responses:**
  - `200 OK`: List of log source records.

#### `GET /api/v1/projects/{project_id}/log-sources/{log_source_id}`
- **Purpose:** Get specific log source details and health statistics.
- **Authentication:** Bearer token required.
- **Project Authorization:** Requires `VIEWER`, `ENGINEER`, or `OWNER`.
- **Responses:**
  - `200 OK`: Log source record.
  - `404 Not Found`: Source does not exist.

#### `POST /api/v1/projects/{project_id}/log-sources/{log_source_id}/ingest`
- **Purpose:** Submit a batch of sanitized log lines for asynchronous parsing, normalization, and anomaly detection.
- **Authentication:** Bearer token or `X-LogPilot-Source-Key` required.
- **Project Authorization:** Validated against owning project and active source status.
- **Execution:** **Asynchronous** (Enqueues task in Redis, immediately returns).
- **Request Body:**
  ```json
  {
    "events": [
      {
        "timestamp": "2026-10-25T16:04:12.102Z",
        "message": "2026-10-25 16:04:12 [ERROR] PaymentGatewayTimeout: Connection dropped after 3000ms",
        "level": "ERROR",
        "attributes": {
          "service": "payment-gateway",
          "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736"
        }
      }
    ]
  }
  ```
- **Responses:**
  - `202 Accepted`:
    ```json
    {
      "ingestion_run_id": "7b54359d-648b-4a57-b087-76b325298a01",
      "status": "QUEUED",
      "received_count": 1,
      "enqueued_at": "2026-10-25T16:04:12.305Z"
    }
    ```
  - `400 Bad Request`: Empty event batch or unparseable JSON payload.
  - `401 Unauthorized`: Invalid source key or missing auth.
  - `429 Too Many Requests`: Ingestion rate limit exceeded.

#### `GET /api/v1/projects/{project_id}/ingestion-runs/{ingestion_run_id}`
- **Purpose:** Inspect status and metrics of a submitted ingestion job.
- **Authentication:** Bearer token required.
- **Project Authorization:** Requires `VIEWER`, `ENGINEER`, or `OWNER`.
- **Responses:**
  - `200 OK`:
    ```json
    {
      "id": "7b54359d-648b-4a57-b087-76b325298a01",
      "log_source_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "status": "COMPLETED",
      "events_processed": 1,
      "errors_count": 0,
      "started_at": "2026-10-25T16:04:12.310Z",
      "completed_at": "2026-10-25T16:04:12.450Z"
    }
    ```

---

### 7.5. Incidents & Events

#### `GET /api/v1/projects/{project_id}/incidents`
- **Purpose:** List operational incidents with filtering and pagination.
- **Authentication:** Bearer token required.
- **Project Authorization:** Requires `VIEWER`, `ENGINEER`, or `OWNER`.
- **Query Parameters:**
  - `state` (string, optional): Filter by lifecycle state (`DETECTED`, `INVESTIGATING`, `RESOLVED`, `IGNORED`).
  - `severity` (string, optional): Filter by severity (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
  - `start_time` / `end_time` (string, optional): ISO UTC time bounds.
  - `page` / `limit` (integers, optional): Pagination controls.
- **Responses:**
  - `200 OK`: Paginated list of incident summary cards.

#### `GET /api/v1/projects/{project_id}/incidents/{incident_id}`
- **Purpose:** Retrieve comprehensive incident detail and status.
- **Authentication:** Bearer token required.
- **Project Authorization:** Requires `VIEWER`, `ENGINEER`, or `OWNER`.
- **Responses:**
  - `200 OK`: Incident entity object including timestamps, severity, and triage metadata.
  - `404 Not Found`: Incident not found or belongs to another project.

#### `GET /api/v1/projects/{project_id}/incidents/{incident_id}/events`
- **Purpose:** Retrieve chronological log events associated with an incident.
- **Authentication:** Bearer token required.
- **Project Authorization:** Requires `VIEWER`, `ENGINEER`, or `OWNER`.
- **Query Parameters:** `page`, `limit`.
- **Responses:**
  - `200 OK`: Paginated list of linked `LogEvent` records with their assigned role (`TRIGGER`, `EVIDENCE`, `CORRELATED_CONTEXT`).

#### `GET /api/v1/projects/{project_id}/incidents/{incident_id}/evidence`
- **Purpose:** Retrieve all structured evidence items assembled for an incident.
- **Authentication:** Bearer token required.
- **Project Authorization:** Requires `VIEWER`, `ENGINEER`, or `OWNER`.
- **Responses:**
  - `200 OK`: List of `IncidentEvidence` items (source type, deterministic pointer reference, summary, extracted snapshot payload).

#### `PATCH /api/v1/projects/{project_id}/incidents/{incident_id}/state`
- **Purpose:** Transition the operational lifecycle state of an incident.
- **Authentication:** Bearer token required.
- **Project Authorization:** Requires `ENGINEER` or `OWNER` role.
- **Request Body:**
  ```json
  {
    "state": "INVESTIGATING",
    "reason": "Engineer assigned and verifying logs"
  }
  ```
- **Responses:**
  - `200 OK`: Updated incident entity with new state and updated timestamp.
  - `400 Bad Request`: Unrecognized state parameter.
  - `403 Forbidden`: `VIEWER` attempted state modification.
  - `409 Conflict`: Invalid state transition (e.g., attempting `RESOLVED` $\rightarrow$ `DETECTED`).

---

### 7.6. Root Cause Analysis (RCA) & Explanation

#### `GET /api/v1/projects/{project_id}/incidents/{incident_id}/rca`
- **Purpose:** Retrieve ranked probable root cause candidates and supporting evidence references.
- **Authentication:** Bearer token required.
- **Project Authorization:** Requires `VIEWER`, `ENGINEER`, or `OWNER`.
- **Responses:**
  - `200 OK`: List of ranked `RCACandidate` objects, score confidence breakdowns, supporting evidence IDs, and explanation generation status (`PENDING`, `GENERATING`, `COMPLETED`, `FAILED`).
  - `404 Not Found`: Incident not found.

#### `POST /api/v1/projects/{project_id}/incidents/{incident_id}/rca/explain`
- **Purpose:** Request or trigger evidence-grounded LLM explanation synthesis for the incident's RCA candidates.
- **Authentication:** Bearer token required.
- **Project Authorization:** Requires `ENGINEER` or `OWNER` role.
- **Execution & Response Contract:**
  - **Asynchronous Execution (Default):** Because LLM inference involves variable latency and potential queuing, the endpoint must not imply synchronous completion. When executed asynchronously, the API returns **`202 Accepted`** containing an explanation tracking status object (`status: "PENDING"` or `status: "GENERATING"`), an operation identifier (`operation_id`), and a polling pointer. Clients inspect the resulting explanation status via `GET /api/v1/projects/{project_id}/incidents/{incident_id}/rca`.
  - **Synchronous Completion (Supported Option):** If the implementation supports immediate synchronous completion (e.g., returning an existing valid cached explanation or executing against an ultra-low-latency provider within request bounds), the API may return **`200 OK`** with the completed `RCAExplanation` payload.
- **Failure Resilience Invariant:** An LLM timeout, provider downtime, or generation failure updates the explanation status to `FAILED` or `TIMEOUT`; it **MUST NEVER** invalidate, overwrite, or corrupt the underlying `Incident`, its assembled `IncidentEvidence`, or the calculated `RCACandidate` rankings.
- **Framework Agnosticism:** The underlying execution strategy (in-process background task vs. asynchronous worker queue) remains open and implementation-dependent.
- **Responses:**
  - `202 Accepted`:
    ```json
    {
      "operation_id": "op_01HPX8Y7B2M41",
      "incident_id": "8f12a95c-3721-4d1e-8e4a-9b1c7a82e110",
      "status": "PENDING",
      "message": "RCA explanation generation has been enqueued.",
      "poll_url": "/api/v1/projects/e4b9b9c0-9f5a-4b71-923c-1b772c68a4e1/incidents/8f12a95c-3721-4d1e-8e4a-9b1c7a82e110/rca"
    }
    ```
  - `200 OK`: Completed `RCAExplanation` record (if returned synchronously or serving cached synthesis).
  - `404 Not Found`: Incident not found or belongs to another project.
  - `504 Gateway Timeout`: If synchronous generation was attempted and exceeded the client/gateway timeout threshold, returning a safe failure notice without affecting underlying incident data.

---

### 7.7. Investigations & Collaboration

#### `GET /api/v1/projects/{project_id}/incidents/{incident_id}/investigation`
- **Purpose:** Retrieve active investigation notes, assignee, and scratchpad.
- **Authentication:** Bearer token required.
- **Project Authorization:** Requires `VIEWER`, `ENGINEER`, or `OWNER`.
- **Responses:**
  - `200 OK`: Investigation entity details.

#### `PATCH /api/v1/projects/{project_id}/incidents/{incident_id}/investigation`
- **Purpose:** Update developer triage notes, assignees, or post-mortem resolution text.
- **Authentication:** Bearer token required.
- **Project Authorization:** Requires `ENGINEER` or `OWNER`.
- **Request Body:**
  ```json
  {
    "assigned_user_id": "550e8400-e29b-41d4-a716-446655440000",
    "notes_markdown": "Identified connection pool exhaustion under load."
  }
  ```
- **Responses:**
  - `200 OK`: Updated investigation entity.

---

### 7.8. Configuration & Governance

#### `GET /api/v1/projects/{project_id}/configuration`
- **Purpose:** Read non-sensitive project operational settings.
- **Authentication:** Bearer token required.
- **Project Authorization:** Requires `VIEWER`, `ENGINEER`, or `OWNER`.
- **Responses:**
  - `200 OK`: Key-value map of configuration settings.

#### `PUT /api/v1/projects/{project_id}/configuration`
- **Purpose:** Update project operational settings (retention windows, anomaly thresholds).
- **Authentication:** Bearer token required.
- **Project Authorization:** Requires `OWNER` role.
- **Request Body:** `{"retention.log_days": 14, "anomaly.sensitivity": 0.85}`.
- **Responses:**
  - `200 OK`: Updated configuration map.
  - `403 Forbidden`: Non-owner attempted configuration mutation.

---

### 7.9. Audit Trail

#### `GET /api/v1/projects/{project_id}/audit-records`
- **Purpose:** Retrieve immutable operational audit logs for compliance inspection.
- **Authentication:** Bearer token required.
- **Project Authorization:** Requires `ENGINEER` or `OWNER`.
- **Query Parameters:** `page`, `limit`, `start_time`, `end_time`.
- **Responses:**
  - `200 OK`: Paginated list of `AuditRecord` objects (`action`, `user_id`, `target_entity`, `change_diff`, `timestamp`).

---

## 8. Incident Lifecycle Contract & State Machine Rules

The API strictly implements the state transition machine ratified in [D01](file:///docs/requirements/PRD.md), [D02](file:///docs/requirements/V1_SCOPE.md), and [D05](file:///docs/architecture/DATABASE_DOMAIN_MODEL.md):

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       VALID API LIFECYCLE TRANSITIONS                       │
├─────────────────────┬─────────────────────┬──────────────────┬──────────────┤
│ Current State       │ Requested State     │ Result           │ HTTP Status  │
├─────────────────────┼─────────────────────┼──────────────────┼──────────────┤
│ `DETECTED`          │ `INVESTIGATING`     │ Allowed          │ `200 OK`     │
│ `DETECTED`          │ `IGNORED`           │ Allowed          │ `200 OK`     │
│ `INVESTIGATING`     │ `RESOLVED`          │ Allowed          │ `200 OK`     │
│ `INVESTIGATING`     │ `IGNORED`           │ Allowed          │ `200 OK`     │
│ `RESOLVED`          │ `INVESTIGATING`     │ Allowed (Reopen) │ `200 OK`     │
│ `RESOLVED`          │ `DETECTED`          │ Prohibited       │ `409 Conflict│
│ `IGNORED`           │ `DETECTED`          │ Prohibited       │ `409 Conflict│
│ `IGNORED`           │ `INVESTIGATING`     │ Allowed (Reopen) │ `200 OK`     │
└─────────────────────┴─────────────────────┴──────────────────┴──────────────┘
```

### Lifecycle Transition Invariants:
1. **Server Ownership:** Only explicit server-side state transitions succeed. Client UI state never overrides database state.
2. **Deterministic Conflict Error:** Any attempt to trigger an unlisted or backwards state transition returns `409 Conflict` with error code `INVALID_STATE_TRANSITION`.
3. **Audit Trail Recording:** Every state transition automatically writes an immutable record to the `audit_records` table with the user ID, previous state, and new state.

---

## 9. Contract Examples (Canonical Payloads)

### Example 1: Project Creation Response (`201 Created`)
```json
{
  "id": "e4b9b9c0-9f5a-4b71-923c-1b772c68a4e1",
  "name": "Payment Gateway Service",
  "slug": "payment-gateway",
  "description": "Core payment integration and ledger pipeline",
  "created_at": "2026-10-25T16:00:00.000Z",
  "updated_at": "2026-10-25T16:00:00.000Z"
}
```

### Example 2: Accepted Log Ingestion Response (`202 Accepted`)
```json
{
  "ingestion_run_id": "7b54359d-648b-4a57-b087-76b325298a01",
  "status": "QUEUED",
  "received_count": 250,
  "enqueued_at": "2026-10-25T16:04:12.305Z"
}
```

### Example 3: Paginated Incident List Response (`200 OK`)
```json
{
  "items": [
    {
      "id": "8f12a95c-3721-4d1e-8e4a-9b1c7a82e110",
      "incident_number": "INC-2026-0042",
      "title": "Payment Gateway connection timeouts exceeding 15% error rate",
      "state": "INVESTIGATING",
      "severity": "CRITICAL",
      "detected_at": "2026-10-25T15:58:30.000Z",
      "resolved_at": null,
      "linked_events_count": 184,
      "top_probable_cause": "Database connection pool exhaustion after commit a1b2c3d"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total_items": 1,
    "total_pages": 1,
    "has_next": false,
    "has_prev": false
  }
}
```

### Example 4: Incident Detail with Evidence References (`200 OK`)
```json
{
  "id": "8f12a95c-3721-4d1e-8e4a-9b1c7a82e110",
  "project_id": "e4b9b9c0-9f5a-4b71-923c-1b772c68a4e1",
  "incident_number": "INC-2026-0042",
  "title": "Payment Gateway connection timeouts exceeding 15% error rate",
  "state": "INVESTIGATING",
  "severity": "CRITICAL",
  "window_start": "2026-10-25T15:50:00.000Z",
  "window_end": "2026-10-25T16:05:00.000Z",
  "detected_at": "2026-10-25T15:58:30.000Z",
  "resolved_at": null,
  "evidence": [
    {
      "id": "ev_01HPX80Z9A4V1",
      "source_type": "LOG_EVENT",
      "source_ref": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "summary": "Timeout exception while acquiring connection pool socket",
      "evidence_payload": {
        "level": "ERROR",
        "stack_trace": "TimeoutError: connection timeout after 3000ms\n at pg.Pool.connect()"
      }
    },
    {
      "id": "ev_01HPX81G5B7W2",
      "source_type": "GIT_COMMIT",
      "source_ref": "a1b2c3d4e5f67890123456789abcdef012345678",
      "summary": "Commit a1b2c3d modified pool configuration max_connections from 50 to 10",
      "evidence_payload": {
        "changed_file": "config/database.py",
        "diff_snippet": "- pool_size = 50\n+ pool_size = 10"
      }
    }
  ]
}
```

### Example 5: Ranked RCA Candidate with Supporting Evidence (`200 OK`)
```json
{
  "incident_id": "8f12a95c-3721-4d1e-8e4a-9b1c7a82e110",
  "candidates": [
    {
      "id": "rca_01HPX89M2N5P1",
      "rank_order": 1,
      "confidence_score": 0.88,
      "probable_cause": "Database connection pool exhaustion caused by pool size reduction in commit a1b2c3d",
      "algorithm_version": "rca-heuristic-v1",
      "supporting_evidence_ids": [
        "ev_01HPX80Z9A4V1",
        "ev_01HPX81G5B7W2"
      ],
      "explanation": {
        "operation_id": "op_01HPX8Y7B2M41",
        "provider_model": "ollama/llama3:8b",
        "status": "COMPLETED",
        "narrative_markdown": "The payment gateway service experienced connection timeouts because the maximum connection pool capacity was reduced from 50 to 10 in commit `a1b2c3d`. Under the prevailing traffic of 45 concurrent requests, threads queued indefinitely, causing HTTP 504 gateway timeouts.",
        "recommended_steps": [
          "Revert commit `a1b2c3d` or restore `pool_size = 50` in `config/database.py`.",
          "Inspect active database connection usage metrics in PostgreSQL.",
          "Verify connection timeout thresholds in client configurations."
        ]
      }
    }
  ]
}
```

### Example 6: Standardized Error Envelope (`409 Conflict`)
```json
{
  "error": {
    "code": "INVALID_STATE_TRANSITION",
    "message": "Cannot transition incident from RESOLVED directly back to DETECTED.",
    "request_id": "req_01HPX8K7B9A23",
    "details": [
      {
        "field": "state",
        "current_state": "RESOLVED",
        "requested_state": "DETECTED",
        "allowed_transitions": [
          "INVESTIGATING"
        ]
      }
    ]
  }
}
```

---

## 10. OpenAPI & TypeScript Client Generation Pipeline

To eliminate manual schema drift between the Python backend and TypeScript clients, LogPilot establishes an automated contract generation flow:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CONTRACT GENERATION & CLIENT PIPELINE                  │
│                                                                             │
│                        Pydantic Models (apps/api)                           │
│                        (Canonical Schema Authority)                         │
│                                     │                                       │
│                                     ▼                                       │
│                           FastAPI Route Handlers                            │
│                                     │                                       │
│                                     ▼                                       │
│                         OpenAPI 3.1 JSON Export                             │
│                      (Extracted via build command)                          │
│                                     │                                       │
│                                     ▼                                       │
│                       TypeScript Generator Tooling                          │
│                                     │                                       │
│                  ┌──────────────────┴──────────────────┐                    │
│                  ▼                                     ▼                    │
│       Typed API Client Class                 TypeScript Domain Types        │
│      (`packages/client/src/index.ts`)     (`packages/client/src/types.ts`)  │
│                  │                                     │                    │
│         ┌────────┴────────┐                   ┌────────┴────────┐           │
│         ▼                 ▼                   ▼                 ▼           │
│   Web Dashboard   VS Code Extension     Web Dashboard   VS Code Extension   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Pipeline Rules:
1. **Pydantic Authority:** All API data types originate as Pydantic models in `apps/api/src/logpilot_api/`.
2. **Reserved Client Package:** Generated client bindings reside in `packages/client/`. They are never hand-edited.
3. **CI Drift Detection:** Continuous integration runs an automated check verifying that the generated client in `packages/client/` matches the latest OpenAPI specification export.

---

## 11. Security, Data Minimization & Privacy

1. **Authorization Verification:** Every route taking a `:project_id` parameter verifies membership in PostgreSQL prior to executing business logic.
2. **Payload Size Guardrails:** Request bodies are bounded by maximum payload settings (e.g., maximum 5MB for log ingestion batches) to prevent memory exhaustion attacks.
3. **Redaction Prior to Persistence:** Client agents perform pre-flight secret masking; server-side ingestion normalizers run regex and entropy filters on `message_raw`.
4. **Context Minimization:** RCA and Explanation endpoints return extracted evidence snippets and diff segments, avoiding bulk dump of uninspected repository code.
5. **Safe Provider Gateways:** Upstream LLM timeouts, network exceptions, or malformed provider JSON streams are caught at the gateway and mapped to safe error messages without leaking internal API keys or endpoints.

---

## 12. Contract Testing Strategy

The HTTP API contract will be validated through automated test suites:
- **Contract Schema Tests:** Validates that live FastAPI responses match generated OpenAPI schemas exactly.
- **Authorization Boundary Tests:** Verifies that tokens from Project A receive `404 Not Found` when requesting resources from Project B.
- **Lifecycle Transition Tests:** Tests all valid and invalid state transitions against the incident state machine.
- **Idempotent Ingestion Tests:** Verifies that resubmitting identical log batches produces matching hash deduplication and zero duplicate database entries.
- **Error Envelope Verification:** Confirms that all $4xx$ and $5xx$ responses strictly adhere to the uniform error schema.

---

## 13. Open Decisions & Implementation TBDs

The following technical implementation details are explicitly recorded as **TBD** and deferred to downstream specifications:

1. **Exact Authentication Token Mechanism:** Selection between symmetric HMAC JWT vs. asymmetric RSA/EdDSA token signing (*Deferred to D11*).
2. **Token Expiration & Refresh Lifecycles:** Access token and refresh token durations and revocation lists (*Deferred to D11*).
3. **Exact TypeScript Client Generator:** Tooling selection between `openapi-typescript-codegen`, `hey-api`, or `orval` (*Deferred to Implementation*).
4. **Default Pagination Limits:** Formal environment configuration for default and max pagination bounds (*Deferred to Implementation*).
5. **Exact Rate Limiting Algorithm:** Redis-backed token bucket vs. fixed-window counter thresholds (*Deferred to Implementation*).
6. **Granular Role Permission Matrix:** Advanced feature flags beyond basic OWNER/ENGINEER/VIEWER roles (*Deferred to Post-V1*).
7. **Detailed Audit Log API Exposure:** Long-term audit filtering and streaming export protocols (*Deferred to D11*).

---

## 14. Relationship to Downstream Design Documents

This document (**D06**) defines the external API surface. Detailed technical designs are formally delegated to:

- **D05 — Database & Domain Model:** Authoritative relational schemas, foreign keys, and tables.
- **D07 — Event & Telemetry Schemas:** Canonical log event payload dictionaries and template miner outputs.
- **D08 — ML & RCA Architecture:** Feature vector formulas, anomaly scoring parameters, and heuristic ranking weights.
- **D09 — RAG Architecture:** Vector retrieval query formats and context window assembly tokens.
- **D10 — LLM Architecture:** Model-specific system prompts, JSON mode definitions, and Gateway timeout policies.
- **D11 — Security Model:** Cryptographic authentication, secret entropy scanning algorithms, and RBAC policies.
- **D12 — Evaluation & Research Framework:** Benchmark datasets and experimental reproducibility protocols.
