# Model Card: Claim Denial Risk

**Status:** Baseline only (Step 6). XGBoost (Step 9), SHAP reasons (Step 10) and recoverability (Step 11) come later, and Step 17 completes this card.
**Date:** 2026-11-26

## What it does

It predicts the chance that a claim's **first remit denies at least one line** (`is_denied`), using only facts known **when the claim is submitted**. The score feeds a worklist ranked by `P(deny) × billed charge × recoverability`. Recoverability is 1.0 for now.

## Intended use

- **Users:** denials and AR analysts deciding which claims to review first.
- **Not for:** paying or denying claims automatically, judging patients or providers, or any use with real patient data.

## Data

- **100% synthetic:** a seeded generator (seed 42) made 100,000 claims over 18 months of service dates (January 2025 to June 2026). There is no real PHI or PII.
- **Denials come from planted drivers plus noise:**
  - late filing (CARC 29)
  - missing prior auth (CARC 197)
  - diagnosis/procedure mismatch (CARC 11)
  - stricter payer types
  - random background denials, about 64% of all denials
- **Label:** `fct_claims.is_denied`. Features come from `feat_claims_at_submission`, and the two are joined by `claim_id` in Python.

## Leakage controls

- The feature table is built on a dbt branch that never reads remit data. Three checks enforce this:
  - a dbt test fails on any remit or outcome-like column
  - a pytest check follows dbt's lineage graph
  - a pytest check proves the dbt test catches an injected `paid_amount`
- The Python join rejects any outcome column on the feature side.
- IDs and raw dates are not features.
- There is **no** hand-made dx/procedure mismatch feature. The model must learn that pattern from the codes.

## Evaluation design

| Part | Submission months | Claims |
|---|---|---|
| Train | Jan 2025 to Mar 2026 | 81,881 |
| **Holdout** | **Apr to Jun 2026** | **16,614** |
| Tail, **excluded** | Jul to Oct 2026 | 1,505 |

**Why the tail is excluded:** visits end on June 30, 2026, so claims submitted after that are **only** for earlier visits. July is mostly end-of-June visits, and August to October are entirely claims sent 30+ days late. Overall, about 45% of the tail was sent 30+ days late, compared with about 5% in a normal month, and its denial rate is 18.3% compared with about 10%. It is incomplete and skewed toward slow filers, which are easy to flag, so it would inflate the metrics. It is left out of training and out of **every** metric. `metrics.json` reports only its size, months and actual denial rate, in a separate `excluded_tail` section.

## Results: baseline logistic regression (holdout, Apr to Jun 2026)

| Metric | Value |
|---|---|
| PR-AUC (primary) | **0.418** (base rate 0.098, about 4.3×) |
| ROC-AUC | 0.745 |
| Brier score | 0.0718 |
| Precision in the top 500 | 66.2% |
| Mean predicted vs actual denial rate | 9.7% vs 9.8% |
| Denied dollars caught in the top 500 by priority | 53.1% (charge-only sort: 34.0%, random: 3.0%) |

Train PR-AUC is 0.381 and ROC-AUC is 0.742, close to the holdout, so there is no sign of overfitting.

Calibration on the holdout, by predicted-risk band:

| Predicted band | Claims | Mean predicted | Actual |
|---|---|---|---|
| 0 to 5% | 6,276 | 4.0% | 4.5% |
| 5 to 10% | 6,155 | 6.5% | 6.0% |
| 10 to 20% | 2,766 | 12.7% | 12.9% |
| 20 to 40% | 913 | 28.1% | 31.8% |
| 40 to 100% | 504 | 68.7% | 65.9% |

The largest weights are past the timely-filing limit (+5.06), missing prior auth (+2.67), Z-code diagnosis (+1.40), prior auth obtained (−1.34) and requires prior auth (+1.33).

## Limits

- **Synthetic data:** the drivers were planted, so finding them shows the pipeline works, not that it would work on real claims.
- **About 64% of denials are random noise** that no submission-time field can explain. That caps how well any model can do here.
- **A linear model** cannot fully learn feature combinations, such as the Z-code diagnosis plus sick-visit CPT pattern. XGBoost in Step 9 should do better.
- **Recoverability is 1.0 for everyone** until Step 11, so the worklist does not yet favor claims that are easier to win on appeal.
- **The holdout is one 3-month period from one seed.** No confidence intervals yet.
