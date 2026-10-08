# ADR-003: Evidence-Based Root Cause Analysis

**Status:** Accepted
**Date:** 2026-10-08

## Context

Root cause analysis (RCA) is a core capability of LogPilot. A naive approach would simply pass log data to an LLM and ask "What caused this?" — but this produces unreliable, unverifiable, and often hallucinated explanations.

Production-quality RCA requires a systematic, evidence-based methodology where the LLM enhances human-readable explanation of already-identified candidate causes rather than serving as the sole source of analysis.

## Decision

RCA must be **evidence-based** rather than LLM-only.

The RCA pipeline follows this structure:

```
Incident
    → Candidate evidence collection
        → Candidate cause identification
            → Evidence scoring
                → Ranked probable causes
                    → Retrieval (RAG)
                        → LLM explanation (grounded in evidence)
```

The system must use terminology such as **"probable root cause"** rather than claiming certainty.

### Evidence Signals

The RCA engine considers multiple evidence signals for scoring and ranking:

| Signal | Description |
|---|---|
| Temporal precedence | Events that preceded the incident |
| Anomaly strength | Statistical confidence of detected anomalies |
| Dependency impact | Effects propagated through service dependencies |
| Error correlation | Co-occurring errors across services/components |
| Service relationships | Known service dependency graph |
| Repository evidence | Recent code/config changes relevant to affected components |
| Git correlation | Commits/deploys temporally correlated with incident onset |
| Historical incident similarity | Similar past incidents and their resolved causes |

### Structured Output

RCA results are structured, not free-form prose:

```json
{
  "summary": "...",
  "probable_root_causes": [
    {
      "cause": "...",
      "confidence": 0.91,
      "evidence": [
        { "type": "temporal_precedence", "description": "...", "weight": 0.8 },
        { "type": "git_correlation", "description": "...", "weight": 0.7 }
      ]
    }
  ],
  "affected_services": [],
  "recommended_actions": [],
  "uncertainty": "medium"
}
```

## Consequences

### Positive

- RCA results are verifiable and traceable — each cause is backed by specific evidence
- Reduces LLM hallucination risk by grounding explanations in concrete signals
- Supports research evaluation (precision, recall, attribution metrics)
- Builds developer trust through transparency

### Negative

- More complex to implement than a simple LLM prompt
- Requires building and maintaining evidence collection and scoring infrastructure
- Evidence signal coverage depends on available data sources

### Neutral

- The specific scoring/ranking algorithm is an implementation detail to be decided during development
- The relative weights of evidence signals may need tuning and are candidates for research experimentation

## Alternatives Considered

1. **LLM-only RCA** ("What caused this?"): Rejected. Unreliable, unverifiable, prone to hallucination, and not suitable for production incident investigation.

2. **Statistical-only RCA** (no LLM): Rejected. Statistical methods alone cannot produce human-readable explanations or leverage repository context effectively.

3. **Evidence-based pipeline with LLM explanation**: Selected. Combines the rigor of evidence-based analysis with the communication ability of LLMs.
