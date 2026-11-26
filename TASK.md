# TASK.md

Work **one step at a time**, in order. Status values: `Todo` · `Doing` · `Done`.
Every step: tests first → full suite run with output shown → `docs/stage-NN-*.md` → user reviews the diff → commit + push.

| # | Step | Acceptance criteria | Status |
|---|---|---|---|
| 0 | Planning docs | `PRD.md`, `spec/plan.md`, `TASK.md`, `CLAUDE.md`, `.gitignore`, `docs/stage-00-planning.md` committed and pushed after review; `CLAUDE.md` < 100 lines | Done |
| 1 | Scaffold | `pyproject.toml` (Python 3.12, `[dev]` extras); ruff configured; `pytest -q` runs one smoke test; `.github/workflows/ci.yml` runs ruff + pytest and is green on GitHub | Done |
| 2 | Generator v1 | Seeded generator creates payers, providers, synthetic patients, claim headers and lines; same seed → identical output (tested); schema tests pass; IDs use synthetic prefixes and no SSN-shaped values (tested) | Todo |
| 3 | Generator v2 | Adds remits with CARC/RARC codes; injected denial drivers + noise; CLI writes ~100k claims over 18 months to `data/raw/*.parquet`; denial rate between 8% and 15% (tested); each driver shows lift > 1 (tested) | Todo |
| 4 | dbt init + staging | dbt project with DuckDB profile (env-based); staging models for every raw table; `unique`/`not_null`/`accepted_values` tests; `dbt build --project-dir dbt --profiles-dir dbt` passes | Todo |
| 5 | dbt marts | `fct_claims`, `dim_payer`, `dim_provider`, `feat_claims_at_submission`, `mart_denial_kpis` built; a custom dbt test confirms no remit columns in the features; `dbt build` passes | Todo |
| 6 | Baseline + priority | Logistic regression trained on a time split (last 3 months = holdout); PR-AUC / ROC-AUC logged; priority score computed; worklist CSV sorted by priority descending (tested) | Todo |
| 7 | FastAPI v1 | `/health`, `/score` (claim features → probability), `/worklist?limit=` work; pydantic schemas; integration tests with TestClient pass | Todo |
| 8 | Streamlit v1 + compose | Streamlit worklist table calls the API; `docker compose up` serves both; manual check documented with a screenshot. **Thin slice done.** | Todo |
| 9 | XGBoost | XGBoost trained on the same split; beats baseline on PR-AUC; calibration checked; artifact saved to `models/artifacts/`; comparison table in the stage doc | Todo |
| 10 | SHAP reasons | Top-3 reasons per claim, readable labels; returned by `/score` and `/claims/{id}`; tests check 3 reasons present and sorted by impact | Todo |
| 11 | Recoverability | CARC-group recoverability lookup; priority uses it; hand-built ranking cases pass (e.g., high-$ missing-auth outranks low-$ timely-filing) | Todo |
| 12 | Streamlit v2 | Claim drill-down page (features, score, reasons) and KPI page (denial rate, top CARC, $ at risk, trend); Streamlit AppTest smoke tests pass | Todo |
| 13 | Docker hardening | Slim images, non-root user, healthchecks; CI builds both images; CI green | Todo |
| 14 | Full CI | CI generates a small sample, runs `dbt build`, runs pytest with coverage ≥ 80% on `src/`; CI green | Todo |
| 15 | BigQuery target (optional) | `bigquery` target in `profiles.yml` read from env vars; documented setup; not run in CI; no credentials committed | Todo |
| 16 | Power BI (optional) | Marts exported to CSV; `.pbix` built on Windows; screenshots in `docs/` | Todo |
| 17 | Final docs | `README.md` (quickstart, architecture, screenshots), `docs/model-card.md`; every PRD definition-of-done item checked | Todo |
