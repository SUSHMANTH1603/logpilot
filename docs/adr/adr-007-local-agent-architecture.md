# ADR-007: Local Agent Architecture

**Status:** Accepted
**Date:** 2026-10-08

## Context

LogPilot's VS Code extension needs access to the developer's local environment: repository files, Git history, local log files, Docker containers, and potentially a local Ollama instance. The VS Code extension itself must remain lightweight and should not contain heavy ML or business logic.

A local agent process bridges the gap between the VS Code extension and the LogPilot backend, handling tasks that require local filesystem and runtime access.

## Decision

Deploy a **local Python agent** (`agent/logpilot-agent/`) that runs alongside the developer's environment.

### Responsibilities

| Responsibility | Description |
|---|---|
| Repository access | Read source files, configuration, dependencies, project structure |
| Git information | Retrieve history, recent commits, diffs, branch information |
| Log collection | Read local log files, collect Docker container logs |
| Local filtering | Apply `.logpilotignore` rules, filter irrelevant data before sending to backend |
| Local inference | Interface with local Ollama instance for inference |
| Extension communication | Serve as the backend for the VS Code extension |
| Backend communication | Forward relevant data to the FastAPI backend |

### Architecture Position

```
VS Code Extension  ←→  Local Agent  ←→  FastAPI Backend
   (TypeScript)          (Python)         (Python)
   Lightweight           Bridge           Full Platform
   UI only               Local access     Business logic
                         Preprocessing    ML / RCA / RAG
                         Ollama access    Storage
```

### Design Constraints

- The agent runs on the developer's machine — it must be lightweight and not consume excessive resources
- The agent must not duplicate business logic that belongs in the backend
- Communication protocol between the extension and agent is **TBD** (likely HTTP/REST or WebSocket)
- Communication protocol between the agent and backend is **TBD** (likely HTTP/REST)
- The agent must respect `.logpilotignore` when scanning the repository

## Consequences

### Positive

- Keeps the VS Code extension thin and focused on UI
- Provides secure local access to repository and runtime data without exposing it directly to the network
- Enables local Ollama inference without routing through the backend
- Python agent can share schema definitions with the backend

### Negative

- Users must install and run a separate agent process (installation/lifecycle UX is important)
- Agent must be kept in sync with backend API changes

### Neutral

- Agent installation and lifecycle management approach is **TBD**
- Whether the agent runs as a background daemon or is launched by the extension is **TBD**
- Agent update/versioning strategy is **TBD**

## Alternatives Considered

1. **VS Code extension communicates directly with backend**: Rejected. Would not have access to local repository files or local Ollama without exposing them over the network.

2. **Node.js agent** (same language as extension): Rejected. Python agent can share schemas and domain code with the Python backend, reducing duplication.

3. **Agent built into the extension as a bundled binary**: Considered. May be explored for improved UX, but adds packaging complexity. Decision deferred.
