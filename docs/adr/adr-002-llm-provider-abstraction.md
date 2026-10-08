# ADR-002: LLM Provider Abstraction

**Status:** Accepted
**Date:** 2026-10-08

## Context

LogPilot uses LLMs for evidence-grounded explanations, incident summarization, and investigation guidance. The system must support both local inference (Ollama) and cloud LLM providers.

Hard-coding the application to a single LLM provider would create vendor lock-in and limit deployment flexibility. Different environments (development, air-gapped, cloud) may require different providers.

## Decision

Create an **LLM provider abstraction** that decouples the rest of the application from any specific LLM implementation.

Conceptual structure:

```
LLMProvider (abstract interface)
    ├── OllamaProvider
    └── CloudLLMProvider
```

Key design constraints:

1. The application code interacts only with the abstract `LLMProvider` interface
2. Provider selection is configuration-driven
3. LLM responses must be **structured** (not uncontrolled prose) — the provider abstraction enforces structured output schemas
4. The system must support both local Ollama inference and cloud inference
5. Entire repositories must never be sent to an LLM by default
6. Secrets must be filtered/redacted before any LLM processing

Example conceptual structured output:

```json
{
  "summary": "...",
  "probable_root_causes": [
    {
      "cause": "...",
      "confidence": 0.91,
      "evidence": []
    }
  ],
  "affected_services": [],
  "recommended_actions": [],
  "uncertainty": "medium"
}
```

## Consequences

### Positive

- No vendor lock-in to any specific LLM provider
- Supports air-gapped / local-only deployments via Ollama
- Structured outputs enable programmatic processing of LLM results
- Secret redaction is enforced at the abstraction layer

### Negative

- Abstraction adds a layer of indirection
- Different providers may have different capabilities; the abstraction must handle capability differences gracefully (approach **TBD**)

### Neutral

- The specific cloud LLM provider(s) to support are **TBD**
- The structured output enforcement mechanism (e.g., function calling, JSON mode, output parsing) is an implementation detail to be decided during implementation

## Alternatives Considered

1. **Direct Ollama integration only**: Rejected. Limits deployment options and prevents using more capable cloud models when available.

2. **Direct integration with a specific cloud provider**: Rejected. Creates vendor lock-in.

3. **Abstract provider interface**: Selected. Provides flexibility while keeping the application code clean.
