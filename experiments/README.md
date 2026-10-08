# LogPilot — Experiments

This directory contains experiment configurations, notebooks, and results for LogPilot's ML and research evaluation work.

## Intended Workflow

1. **Design**: Define the experiment hypothesis, independent/dependent variables, and evaluation metrics
2. **Configure**: Create experiment configuration (dataset, model parameters, pipeline settings)
3. **Run**: Execute the experiment using the evaluation harness
4. **Track**: Log metrics and artifacts to MLflow
5. **Analyze**: Review results, compare with baselines
6. **Document**: Record findings and conclusions

## Directory Structure

```
experiments/
├── README.md              # This file
└── (future experiment configs, notebooks, and results)
```

As experiments are conducted, they will be organized by experiment ID or name.

## Tools

- **MLflow** for experiment tracking (not yet configured)
- **Custom evaluation harness** in `ml/evaluation/` (not yet implemented)
- **Datasets** in `datasets/` (not yet created)

## Status

No experiments have been conducted yet. This directory will be populated as the ML pipeline and evaluation harness are implemented.
