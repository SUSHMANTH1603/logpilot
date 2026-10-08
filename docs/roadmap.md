# LogPilot — Development Roadmap

## Overview

This roadmap outlines the planned development phases for LogPilot. Phases are sequential but may overlap. Specific timelines are **TBD**.

## Phase 0: Repository and Architecture Foundation ← **Current**

- [x] Repository structure
- [x] Architecture documentation
- [x] Architectural Decision Records (ADRs)
- [x] Development standards
- [x] AI-assisted development workflow
- [x] Definition of Done
- [x] Research direction documentation
- [x] `.gitignore` and `.logpilotignore`
- [ ] CI pipeline setup
- [ ] Development environment setup (Docker Compose for dependencies)
- [ ] Python project configuration (pyproject.toml for each component)
- [ ] TypeScript project configuration (package.json for web/extension)

## Phase 1: Core Backend Infrastructure

- [ ] FastAPI application scaffold (`apps/api/`)
- [ ] Database schema design and initial Alembic migrations
- [ ] PostgreSQL connection and session management
- [ ] Redis connection and queue infrastructure
- [ ] Qdrant connection and collection setup
- [ ] Authentication and authorization foundation
- [ ] Project-level data isolation
- [ ] Health check and status endpoints
- [ ] Pydantic schema package (`packages/schemas/`)
- [ ] Configuration management (Pydantic Settings)
- [ ] Logging and error handling standards
- [ ] OpenTelemetry instrumentation foundation

## Phase 2: Log Ingestion Pipeline

- [ ] Log ingestion adapter interface
- [ ] Manual log input adapter
- [ ] Local file log adapter
- [ ] Docker log adapter
- [ ] OpenTelemetry log adapter
- [ ] Log parser and normalizer
- [ ] Template extraction
- [ ] Ingestion worker (`workers/ingestion/`)
- [ ] Ingestion API endpoints

## Phase 3: Anomaly Detection

- [ ] Feature extraction pipeline
- [ ] Statistical baseline detector
- [ ] Isolation Forest detector
- [ ] Anomaly detection evaluation harness
- [ ] Analysis worker (`workers/analysis/`)
- [ ] Detection API endpoints

## Phase 4: Repository Intelligence

- [ ] Repository scanner
- [ ] `.logpilotignore` enforcement
- [ ] Secret detection and redaction
- [ ] Git history analysis
- [ ] Dependency analysis
- [ ] Service relationship inference
- [ ] Repository context embedding and indexing
- [ ] Local agent foundation (`agent/logpilot-agent/`)

## Phase 5: RAG and Retrieval

- [ ] Embedding pipeline (Sentence Transformers)
- [ ] Qdrant collection management
- [ ] Dense retrieval implementation
- [ ] Metadata filtering
- [ ] Indexing worker (`workers/indexing/`)
- [ ] Retrieval evaluation harness

## Phase 6: LLM Integration

- [ ] LLM provider abstraction (`LLMProvider` interface)
- [ ] Ollama provider implementation
- [ ] Cloud LLM provider implementation
- [ ] Structured output enforcement
- [ ] Safe context construction (redaction, scoping)
- [ ] LLM configuration UI (web dashboard settings)

## Phase 7: Root Cause Analysis

- [ ] Incident correlation engine
- [ ] Evidence collection pipeline
- [ ] Evidence scoring and ranking
- [ ] RCA candidate ranking
- [ ] RAG-enhanced LLM explanation
- [ ] Structured RCA output
- [ ] RCA evaluation harness

## Phase 8: VS Code Extension

- [ ] Extension scaffold
- [ ] Agent communication protocol
- [ ] Monitoring controls
- [ ] Incident notification
- [ ] Investigation UI
- [ ] Evidence display
- [ ] Probable root cause presentation
- [ ] Recommended investigation steps

## Phase 9: Web Dashboard

- [ ] React application scaffold (`apps/web/`)
- [ ] OpenAPI TypeScript client generation
- [ ] Incident management views
- [ ] Live log viewer
- [ ] Service views
- [ ] Repository information views
- [ ] Historical incidents and search
- [ ] Analytics dashboards
- [ ] Settings and configuration
- [ ] AI provider configuration

## Phase 10: Research and Evaluation

- [ ] Evaluation dataset creation
- [ ] MLflow configuration
- [ ] End-to-end evaluation harness
- [ ] Baseline experiments (see [Research](research/))
- [ ] Ablation studies
- [ ] Results analysis and documentation

## Phase 11: Production Readiness

- [ ] Security audit
- [ ] Performance testing and optimization
- [ ] Production Docker configuration
- [ ] Deployment documentation
- [ ] Monitoring and alerting for LogPilot itself
- [ ] User documentation

## Notes

- This roadmap captures intended development order, not commitments
- Phases may be reordered based on learnings and priorities
- Each phase will be broken into specific tasks/issues when it begins
- New phases or items should not be added without discussion
