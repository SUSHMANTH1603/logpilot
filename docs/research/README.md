# LogPilot — Research Direction

## Research Question

> Can combining runtime anomaly signals, repository context, and historical incident retrieval improve automated root-cause identification compared with log-only approaches?

## Background

Traditional observability tools detect anomalies from runtime signals (logs, metrics, traces) but lack awareness of repository context — code changes, configuration, dependencies, service relationships, and historical incidents. LogPilot hypothesizes that incorporating these additional signals into the RCA pipeline improves root cause identification accuracy.

## Planned Experiments

| # | Experiment | Independent Variable | Dependent Variables |
|---|---|---|---|
| 1 | Detection method | Statistical baseline vs. Isolation Forest | Precision, Recall, F1, FPR, Detection latency |
| 2 | Retrieval strategy (dense vs. sparse) | Dense vs. sparse vs. hybrid retrieval | Recall@K, MRR, nDCG |
| 3 | Retrieval strategy (reranking) | Hybrid retrieval vs. reranked retrieval | Recall@K, MRR, nDCG |
| 4 | RCA signal scope (repo) | Log-only RCA vs. log + repository | Top-1 accuracy, Top-3 recall |
| 5 | RCA signal scope (history) | Log + repository vs. log + repo + historical incidents | Top-1 accuracy, Top-3 recall |
| 6 | LLM grounding | LLM without evidence vs. evidence-grounded LLM | Groundedness, Evidence attribution |

## Evaluation Metrics

### Detection Metrics
- Precision
- Recall
- F1 score
- False-positive rate (FPR)
- Detection latency

### RCA Metrics
- Top-1 RCA accuracy
- Top-3 RCA recall

### Retrieval Metrics
- Recall@K
- Mean Reciprocal Rank (MRR)
- Normalized Discounted Cumulative Gain (nDCG)

### LLM Quality Metrics
- Groundedness (proportion of claims backed by provided evidence)
- Evidence attribution (correct citation of evidence sources)

## Evaluation Datasets

Evaluation datasets are **TBD**. Options under consideration:

- Synthetic incident datasets with known root causes
- Semi-synthetic datasets (real logs with injected faults)
- Real-world incident datasets (if available and anonymizable)
- Open-source benchmark datasets (if applicable ones exist)

Dataset creation and curation is a future task.

## Tools

- **MLflow**: Experiment tracking, metric logging, model versioning
- **Custom evaluation harness**: End-to-end pipeline evaluation specific to LogPilot

## Directory Structure

```
ml/evaluation/           # Evaluation harness code
datasets/                # Evaluation datasets
experiments/             # Experiment configs, notebooks, results
docs/research/           # This directory — research documentation
```

## Status

Research infrastructure is in the planning phase. No experiments have been conducted yet.
