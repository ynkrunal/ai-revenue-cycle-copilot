# PRD: AI Revenue Cycle Copilot for Healthcare

**Status:** Draft v1 (Stage 0) · **Date:** 2026-11-25 · **Owner:** Krunal Vaghasiya

## 1. Problem

Denied claims cost healthcare providers cash and analyst time. Denials/AR analysts usually work their queues first-in-first-out or by dollar amount. Neither method accounts for **how likely a claim is to be denied** or **how likely the money is to be recovered**. As a result, analysts spend hours on claims that won't pay, and recoverable dollars age past timely-filing limits.

## 2. Users

| User | Role | What they need |
|---|---|---|
| **Primary: Denials/AR analyst** | Works claim queues daily | A ranked worklist: which claims to touch first, and why |
| Secondary: RCM manager | Monitors team and KPIs | Denial rate, top denial reasons, cash at risk, trends |

## 3. What the product does

1. **Predict.** Scores each claim's **probability of denial** using only facts known *at submission*, and shows the **top 3 reasons** for each score (SHAP).
2. **Prioritize.** Ranks open and denied claims by expected dollars at stake:
   `priority = P(deny) × balance × recoverability(CARC group)`
3. **Show.** A Streamlit app with a worklist, a claim drill-down and a KPI page. A FastAPI service exposes the same data. Power BI is optional.

All data is **synthetic**: a seeded Python generator produces about 100k 837/835-like claims and remits over 18 months, with realistic payers, CPT/ICD-10 codes and CARC/RARC codes.

## 4. In scope

- Synthetic data generator (claims, claim lines, remits, payers, providers, fake patients)
- dbt models on **DuckDB** (staging → intermediate → marts), with an optional **BigQuery** target
- Baseline model (logistic regression) and an **XGBoost** denial model, using a time-based split
- SHAP reason codes per claim
- Priority score and worklist
- **FastAPI**: `/health`, `/score`, `/worklist`, `/claims/{id}`
- **Streamlit** UI: worklist, drill-down, KPIs
- **Docker** / docker-compose, **GitHub Actions** CI (lint, tests, dbt build, image build)
- Optional: **Power BI** report built from exported marts (on Windows)
- Plain-English stage docs and a model card

## 5. Out of scope

- Any real PHI or PII, or any real patient, provider or payer records
- Real X12 EDI parsing, clearinghouse or payer API integration
- Automated appeal letters or LLM/chat features
- Authentication, multi-tenant hosting, production deployment
- HIPAA certification or compliance claims

## 6. Definition of done

- [ ] `docker compose up` starts the API and UI, and the worklist loads in the browser.
- [ ] CI is green on `main`: ruff, pytest (coverage ≥ 80% on `src/`), `dbt build` on a small generated sample, Docker image build.
- [ ] XGBoost **beats the baseline on PR-AUC** on the time-based holdout (last 3 months), with results in `docs/model-card.md`.
- [ ] Features contain no post-submission (remit) fields, and a test enforces this.
- [ ] The worklist orders claims by expected $ at risk, and a test asserts the ordering.
- [ ] Every step in `TASK.md` is marked **Done** and has a `docs/stage-NN-*.md` document.

## 7. Risks

| Risk | Mitigation |
|---|---|
| **Scope too big for ~3 weeks** (top risk) | Thin end-to-end slice first (generator → dbt → baseline → API → UI by step 8), then go deeper. BigQuery and Power BI are optional and come last. |
| Synthetic data too "easy" | Overlapping drivers plus noise; report results against a baseline; honest model card |
| Target leakage | Features use as-of-submission fields only; split by submission month |
| Power BI is Windows-only | Export marts to CSV; build the `.pbix` on Windows; optional |
