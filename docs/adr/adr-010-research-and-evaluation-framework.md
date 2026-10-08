# ADR-010: Research and Evaluation Framework

**Status:** Accepted
**Date:** 2026-10-08

## Context

LogPilot is intended to support future conference-quality research. The research direction explores whether combining runtime anomaly signals, repository context, and historical incident retrieval can improve automated root-cause identification compared with log-only approaches.

Evaluation and experimentation must be designed into the architecture from the beginning, not bolted on later.

## Decision

### Research Question Direction

> "Can combining runtime anomaly signals, repository context, and historical incident retrieval improve automated root-cause identification compared with log-only approaches?"

### Experiment Design

The system must support controlled experiments comparing different pipeline configurations:

| Experiment | Comparison |
|---|---|
| Detection | Statistical baseline vs. Isolation Forest |
| Retrieval | Dense vs. sparse vs. hybrid retrieval |
| Retrieval | Hybrid retrieval vs. reranked retrieval |
| RCA signals | Log-only RCA vs. log + repository |
| RCA signals | Log + repository vs. log + repository + historical incidents |
| LLM grounding | LLM without evidence vs. evidence-grounded LLM |

### Evaluation Metrics

| Category | Metrics |
|---|---|
| Detection | Precision, Recall, F1, False-positive rate, Detection latency |
| RCA | Top-1 RCA accuracy, Top-3 RCA recall |
| Retrieval | Recall@K, MRR, nDCG |
| LLM quality | Groundedness, Evidence attribution |

### Infrastructure

- **MLflow** for experiment tracking, metric logging, and model versioning
- **Custom evaluation harness** for end-to-end pipeline evaluation
- **Datasets directory** (`datasets/`) for curated and synthetic evaluation datasets
- **Experiments directory** (`experiments/`) for experiment configurations, notebooks, and results

### Directory Structure

```
ml/
└── evaluation/          # Evaluation harness code

datasets/                # Evaluation datasets
├── raw/                 # Raw collected data (gitignored)
└── processed/           # Processed evaluation sets (gitignored)

experiments/             # Experiment tracking
├── README.md            # Experiment workflow documentation
└── (experiment configs, notebooks, results)
```

### Design Principles

- Every ML component must expose interfaces that allow swapping implementations for A/B comparison
- Metrics collection must be standardized across experiments
- Evaluation datasets must be versioned and reproducible
- Results must be reproducible given the same data and configuration

## Consequences

### Positive

- Research is a first-class concern, not an afterthought
- Standardized metrics enable rigorous comparison
- MLflow provides industry-standard experiment tracking
- Modular ML components enable clean experiment design

### Negative

- Designing for experimentation adds some architectural overhead
- Creating quality evaluation datasets requires significant effort

### Neutral

- Specific evaluation datasets do not exist yet — creation is a future task
- MLflow configuration and deployment are **TBD**
- The evaluation harness API is **TBD**
- Whether to use synthetic, semi-synthetic, or real-world evaluation data (or a combination) is **TBD**

## Alternatives Considered

1. **No evaluation framework**: Rejected. Without evaluation, there is no way to measure whether the system works or to support research claims.

2. **Custom experiment tracking only**: Rejected. MLflow provides standardized tracking, visualization, and model registry that would be expensive to rebuild.

3. **MLflow + custom evaluation harness**: Selected. MLflow handles experiment tracking; the custom harness handles LogPilot-specific evaluation logic.
