# ADR-009: RAG Pipeline Architecture

**Status:** Accepted
**Date:** 2026-10-08

## Context

LogPilot's root cause analysis and investigation guidance require retrieving relevant context from multiple sources: historical incidents, repository content, log patterns, runbooks, and documentation. The retrieval-augmented generation (RAG) pipeline is the mechanism that finds and provides this context to the LLM for evidence-grounded explanations.

A well-designed RAG pipeline is critical to the quality of RCA outputs and is also a key variable in the project's research experiments.

## Decision

Build a **custom retrieval pipeline** with a phased approach:

### V1: Dense Retrieval

- Use dense vector embeddings (Sentence Transformers) for semantic similarity search
- Store embeddings in Qdrant with metadata payloads
- Support metadata filtering (by project, service, time range, log level, etc.)
- Retrieve from multiple collections: logs, incidents, repository context

### Future Phases

| Phase | Capability |
|---|---|
| V2 | Sparse retrieval (BM25 or equivalent) |
| V2 | Hybrid retrieval (dense + sparse fusion) |
| V3 | Reranking (cross-encoder or similar) |

### Retrieval Sources

The RAG pipeline retrieves from:

1. **Historical incidents**: Past incidents with similar patterns, symptoms, or affected services
2. **Repository context**: Relevant code, configuration, and documentation
3. **Log patterns**: Similar log sequences or templates from past events
4. **Runbooks / documentation**: Operational guides relevant to the affected service

### Design Principles

- The retrieval pipeline is a **component** of the RCA engine, not a standalone system
- Retrieved context is used as **evidence** for the RCA pipeline (see ADR-003), not passed directly to an LLM without processing
- Retrieval quality is measurable via standard IR metrics (Recall@K, MRR, nDCG)
- The pipeline must be modular enough to swap retrieval strategies for research experiments

### Schema and Embedding

- Embedding model selection is **TBD** (initial candidate: Sentence Transformers all-MiniLM or similar)
- Chunking strategy for different content types is **TBD**
- Qdrant collection design is **TBD**

## Consequences

### Positive

- Custom pipeline allows full control over retrieval quality and experimentation
- Phased approach avoids premature complexity
- Metadata filtering enables precise scoping (project, service, time)
- Modular design supports A/B experimentation (dense vs. hybrid vs. reranked)

### Negative

- Building a custom pipeline requires more effort than using an off-the-shelf RAG framework
- Retrieval quality depends heavily on embedding model choice and chunking strategy

### Neutral

- Whether to use a RAG framework (LangChain, LlamaIndex, etc.) or build from scratch is **TBD** — the architecture supports either approach as long as the modular requirements are met
- The specific embedding model, chunk sizes, and overlap strategy are implementation decisions

## Alternatives Considered

1. **Off-the-shelf RAG framework (LangChain/LlamaIndex)**: Not rejected, but not mandated. The architecture must support research experimentation, which may require more control than a framework provides. This decision will be made during implementation.

2. **No RAG (LLM with full context)**: Rejected. Sending all context to the LLM is expensive, slow, and hits token limits. Retrieval is necessary.

3. **Keyword search only**: Rejected. Semantic similarity is essential for finding conceptually related incidents and context.
