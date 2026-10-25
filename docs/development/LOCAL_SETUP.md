# LogPilot Local Development Setup Guide

This guide describes how to start the minimum local development environment for the LogPilot backend modular monolith, backing storage services, migrations, and automated tests.

---

## 1. Prerequisites

- **Python:** 3.11+ (Python 3.11, 3.12, 3.13, or 3.14)
- **Docker & Docker Compose:** Docker Desktop or Docker Engine with Docker Compose v2.x+
- **Git:** Version control on branch `develop`

---

## 2. Environment Configuration

1. Copy the safe template file to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Review the default connection settings in `.env`. The defaults are pre-configured for local developer container ports:
   - PostgreSQL: `127.0.0.1:5432` (`logpilot` / `logpilot_dev_password`)
   - Redis: `127.0.0.1:6379`
   - Qdrant: `127.0.0.1:6333` (REST) / `127.0.0.1:6334` (gRPC)

*Security Note:* Never commit `.env` or real cryptographic credentials to source control. `.env` is gitignored by default.

---

## 3. Infrastructure Management (Docker Compose)

The local backing services (PostgreSQL 16, Redis 7, Qdrant 1.11) are orchestrated via `infrastructure/compose/docker-compose.yml`.

### Start Backing Services
```bash
docker compose -f infrastructure/compose/docker-compose.yml up -d
```

### Check Service Health
```bash
docker compose -f infrastructure/compose/docker-compose.yml ps
```
All services are configured with automated health checks (`pg_isready`, `redis-cli ping`, and Qdrant `/readyz`).

### Stop Backing Services
```bash
docker compose -f infrastructure/compose/docker-compose.yml down
```

### Stop and Wipe Local Volumes (Reset Environment)
```bash
docker compose -f infrastructure/compose/docker-compose.yml down -v
```

---

## 4. Python Environment & Dependencies

1. Create and activate a Python virtual environment:
   ```bash
   # Windows PowerShell:
   python -m venv .venv
   .venv\Scripts\Activate.ps1

   # Linux / macOS:
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install backend dependencies and developer tools:
   ```bash
   pip install -e .[dev]
   ```

---

## 5. Database Migrations (Alembic)

Alembic manages schema evolution for PostgreSQL (ADR-005):

- **Apply pending migrations:**
  ```bash
  alembic upgrade head
  ```
- **Generate a new migration:**
  ```bash
  alembic revision --autogenerate -m "describe_schema_change"
  ```
- **Roll back last migration:**
  ```bash
  alembic downgrade -1
  ```

---

## 6. Running the Backend API

Start the FastAPI development server with hot-reload:
```bash
uvicorn logpilot_api.main:app --reload --host 127.0.0.1 --port 8000
```

Verify endpoints:
- **Contract Health & Liveness (D06 § 7.1):**
  ```bash
  curl http://127.0.0.1:8000/api/v1/health
  # Response: {"status":"HEALTHY","version":"0.1.0","timestamp":"..."}
  ```
- **Liveness Probe:**
  ```bash
  curl http://127.0.0.1:8000/health
  # Response: {"status":"UP","timestamp":"..."}
  ```
- **Dependency Readiness Probe:**
  ```bash
  curl http://127.0.0.1:8000/ready
  ```
- **Interactive OpenAPI Documentation:**
  Open `http://127.0.0.1:8000/docs` in your browser (available in development mode only).

---

## 7. Testing & Quality Checks

- **Run unit and integration test suite:**
  ```bash
  pytest
  ```
- **Run Ruff linter:**
  ```bash
  ruff check .
  ```
- **Run Ruff formatter check:**
  ```bash
  ruff format --check .
  ```
- **Auto-format code:**
  ```bash
  ruff format .
  ```
