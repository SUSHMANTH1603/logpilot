# ADR-005: Storage Architecture — PostgreSQL, Redis and Qdrant

**Status:** Accepted
**Date:** 2026-10-08

## Context

LogPilot requires persistent storage for incidents, logs, configuration, and user data; a vector store for semantic retrieval; and infrastructure for caching, queuing, and ephemeral state. The choice of storage systems and their roles must be clearly defined to avoid architectural confusion.

## Decision

Use three storage systems with clearly separated roles:

| Store | Role | Principle |
|---|---|---|
| **PostgreSQL** | System of record | The authoritative source of truth for all persistent application data |
| **Redis** | Cache, message queues, ephemeral state | Infrastructure — never a source of truth; data is lossy/rebuildable |
| **Qdrant** | Vector retrieval and semantic indexing | A retrieval/indexing system — not a source of truth; entirely rebuildable from PostgreSQL |

### PostgreSQL — System of Record

- All persistent data (incidents, logs, users, projects, configurations, audit logs) is stored in PostgreSQL
- If PostgreSQL data and Qdrant/Redis data disagree, PostgreSQL is authoritative
- Schema managed via Alembic migrations
- ORM: SQLAlchemy 2.x

### Redis — Infrastructure Layer

- Async task queues (for worker job dispatch)
- Caching (query results, computed values, rate limiting)
- Ephemeral session/state data
- Pub/sub for real-time notifications (**TBD** whether this is needed in V1)
- **Must not** store data that cannot be rebuilt from PostgreSQL

### Qdrant — Vector Retrieval

- Stores vector embeddings for semantic search (log embeddings, incident embeddings, repository context embeddings)
- Used by the RAG pipeline for dense retrieval
- The entire Qdrant index is rebuildable from source data in PostgreSQL
- Not queried as a source of truth for business logic

## Consequences

### Positive

- Clear ownership of data eliminates ambiguity about which store is authoritative
- Qdrant being rebuildable means vector index corruption or migration issues are recoverable
- Redis being ephemeral simplifies its operational requirements
- Each store is used for its strengths

### Negative

- Three separate data stores to operate and monitor
- Consistency between PostgreSQL and Qdrant must be managed (eventual consistency is acceptable for retrieval)

### Neutral

- The specific Redis queue library/pattern (Celery, arq, custom, etc.) is **TBD**
- Qdrant collection design and embedding dimensionality are implementation decisions
- PostgreSQL schema design will evolve through Alembic migrations

## Alternatives Considered

1. **PostgreSQL with pgvector instead of Qdrant**: Considered. pgvector is simpler operationally but Qdrant provides more advanced vector search features (filtering, payload indexing, HNSW tuning). This decision may be revisited if operational complexity becomes a concern.

2. **Redis as a data store**: Rejected. Using Redis for persistent data creates durability risks and architectural confusion about the source of truth.

3. **Single database for everything**: Rejected. PostgreSQL is not optimized for high-performance vector similarity search at scale.
