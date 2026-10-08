# LogPilot — Datasets

This directory contains curated and synthetic datasets for evaluating LogPilot's ML pipeline, anomaly detection, retrieval, and root cause analysis.

## Directory Structure

```
datasets/
├── README.md          # This file
├── raw/               # Raw collected data (gitignored)
└── processed/         # Processed evaluation sets (gitignored)
```

## Data Policy

- `raw/` and `processed/` subdirectories are **gitignored** — large data files must not be committed to the repository
- Dataset metadata, schemas, and generation scripts should be committed
- Datasets must not contain real production secrets or personally identifiable information
- Dataset versioning strategy is **TBD**

## Status

No datasets have been created yet. Dataset creation will begin when the ML pipeline and evaluation harness are implemented.
