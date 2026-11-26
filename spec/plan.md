# Technical Plan: AI Revenue Cycle Copilot

Companion to [`PRD.md`](../PRD.md). Step status is tracked in [`TASK.md`](../TASK.md).

## 1. Stack

Python 3.12 · SQL · dbt (DuckDB locally, BigQuery optional) · XGBoost · SHAP · FastAPI · Streamlit · Power BI (optional) · Docker · GitHub Actions

## 2. Architecture

```
 ┌──────────────────────┐
 │ Synthetic generator  │  src/rcm/generator  (seeded, ~100k claims, 18 months)
 └─────────┬────────────┘
           ▼
   data/raw/*.parquet   (git-ignored)
           ▼
 ┌──────────────────────┐   target: duckdb (default) | bigquery (optional)
 │ dbt                  │   staging → intermediate → marts
 └─────────┬────────────┘
           ├──────────────► marts → CSV export → Power BI (optional, Windows)
           ▼
   feat_claims_at_submission
           ▼
 ┌──────────────────────┐
 │ Train                │  baseline (logistic) + XGBoost, SHAP reasons
 └─────────┬────────────┘
           ▼
   models/artifacts/    (git-ignored)
           ▼
 ┌──────────────────────┐        ┌──────────────────────┐
 │ FastAPI              │ ◄────► │ Streamlit UI         │
 │ /health /score       │  HTTP  │ worklist · drill-down│
 │ /worklist /claims/id │        │ · KPIs               │
 └──────────────────────┘        └──────────────────────┘
        (docker-compose: api + ui)
```

## 3. Key design decisions

- **Leakage guard.** Features are built only from claim fields known at submission (payer, CPT/ICD, place of service, prior-auth flag, provider, charge, days from service to submit, etc.). Remit/835 fields (CARC, paid amount, adjudication date) are used **only** to build the label. A dbt test and a pytest check enforce this.
- **Label.** `is_denied = 1` if the first remit has a denial CARC (full or line-level denial, as defined in the generator).
- **Split.** By submission month. The last 3 of 18 months are the holdout. No random split.
- **Priority.** `P(deny) × open_balance × recoverability(CARC group)`. Recoverability starts as a fixed lookup per CARC group (e.g., CO-197 missing auth = high, CO-29 timely filing = low).
- **Metrics.** PR-AUC (primary, because classes are imbalanced), ROC-AUC, Brier score / calibration curve, and precision@top-k for the worklist.
- **Config.** All environment-specific settings (DuckDB path, BigQuery project, API URL) come from environment variables. Example values go in `.env.example`; `.env` is never committed.
- **Synthetic data.** Fake names and IDs carry obvious synthetic prefixes (e.g., `SYN-MRN-000123`). No real NPIs or SSN-shaped values.

## 4. File structure (target)

```
ai-revenue-cycle-copilot/
├── PRD.md  TASK.md  CLAUDE.md  README.md
├── pyproject.toml  .env.example  docker-compose.yml
├── spec/plan.md
├── docs/                      stage-NN-*.md, model-card.md, screenshots
├── src/rcm/
│   ├── generator/             reference data, claims, remits, CLI
│   ├── features/              load features from DuckDB/BigQuery
│   ├── models/                baseline, xgboost, shap, priority
│   ├── api/                   FastAPI app
│   └── ui/                    Streamlit app
├── dbt/
│   ├── dbt_project.yml  profiles.yml (env-based)
│   ├── models/{staging,intermediate,marts}/
│   └── tests/
├── tests/{unit,integration}/
├── docker/{api.Dockerfile,ui.Dockerfile}
├── powerbi/                   README + exports (optional)
└── .github/workflows/ci.yml
```

Note: `.gitignore` ignores **any** directory named `data/`, so source code must never live in a folder called `data`.

## 5. Ordered steps (each ≤ 1 day)

| # | Step | Phase |
|---|---|---|
| 0 | Planning docs (PRD, plan, tasks, CLAUDE.md, .gitignore) | Plan |
| 1 | Scaffold: pyproject, ruff, pytest, CI (lint + tests) | Thin slice |
| 2 | Generator v1: reference data, claim headers and lines, seeded | Thin slice |
| 3 | Generator v2: remits + CARC/RARC, denial drivers + noise, 100k claims to parquet | Thin slice |
| 4 | dbt init (DuckDB) + staging models + schema tests | Thin slice |
| 5 | dbt marts: fct_claims, dims, feat_claims_at_submission, mart_denial_kpis | Thin slice |
| 6 | Baseline model + priority score → CSV worklist | Thin slice |
| 7 | FastAPI v1: /health, /score, /worklist | Thin slice |
| 8 | Streamlit v1 worklist + docker-compose (**thin slice done**) | Thin slice |
| 9 | XGBoost, time split, metrics vs baseline | Deepen |
| 10 | SHAP top-3 reasons in /score and /claims/{id} | Deepen |
| 11 | Recoverability by CARC group → refined priority | Deepen |
| 12 | Streamlit v2: drill-down + KPI page | Deepen |
| 13 | Docker hardening + CI image build | Harden |
| 14 | Full CI: sample data → dbt build → pytest + coverage ≥ 80% | Harden |
| 15 | Optional: BigQuery dbt target | Optional |
| 16 | Optional: Power BI exports + .pbix | Optional |
| 17 | Model card, README, final docs | Finish |

Schedule: steps 1–8 in week 1 (plus buffer), 9–14 in week 2, 15–17 in week 3. If time runs short, drop 15 and 16 first.

## 6. Per-step workflow

1. Write failing tests (red) → implement (green) → refactor.
2. Run the full suite and show the output.
3. Write `docs/stage-NN-<slug>.md` in plain English.
4. Update the status in `TASK.md`.
5. Show the diff → wait for user approval → commit → push.
