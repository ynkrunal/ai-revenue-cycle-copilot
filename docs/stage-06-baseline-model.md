# Stage 6: Baseline Model and Priority Score

**Date:** 2026-11-26 · **Status:** Done (waiting for review)

## What we did

We trained the first denial model, a **logistic regression**. It gives every claim a **chance of denial** (`p_deny`). Then we turned that chance into a **priority score** and wrote a ranked **worklist CSV**, so an analyst knows which claims to look at first.

```
priority = P(deny) × balance × recoverability
```

- **Balance** is the billed charge, the dollars at stake on that claim.
- **Recoverability** is set to **1.0 for every claim** for now. Step 11 replaces it with a lookup by denial-reason group.

## How the data is joined

Features come from `feat_claims_at_submission`, which only has facts known on the day the claim is sent. The label (`is_denied`) comes from `fct_claims`. Python reads the two tables **separately** and joins them by `claim_id` (`rcm/models/features.py`). The join refuses to run in three cases:

- a claim appears twice
- a claim has no label
- any outcome column (`paid_amount`, `carc_code`, `is_denied` and so on) is on the feature side

## The time split (decided before this step)

| Part | Submission months | Claims | Used for |
|---|---|---|---|
| Train | Jan 2025 to Mar 2026 | 81,881 | fitting the model |
| **Holdout** | **Apr to Jun 2026** (last 3 months of the 18-month window) | 16,614 | **all reported metrics** and the worklist |
| Tail, **dropped** | Jul to Oct 2026 | 1,505 | nothing. It is reported separately and never scored. |

### Why the tail is dropped

Visits stop on June 30, 2026, but claims can be sent up to 120 days later. So July to October 2026 only contain claims for **earlier** visits:

| Month | Claims | Sent 30+ days late | Denial rate |
|---|---|---|---|
| Normal month (Apr to Jun 2026) | about 5,500 | about 5% | about 10% |
| Jul 2026 | 1,097 | 24.6% | 12.2% |
| Aug 2026 | 242 | 100% | 29.8% |
| Sep 2026 | 130 | 100% | 40.0% |
| Oct 2026 | 36 | 100% | 50.0% |

July is mostly end-of-June visits. August to October are **only** late claims. These months are **incomplete and skewed toward slow filers**, so they do not look like a normal month of work. Testing on them would make the model look better than it is, because late claims are easy to spot. Training on them would teach the model a mix it will never see in real life.

> **Correction:** the Step 5 doc first said the whole tail was "mostly late filers". That is only true for August to October. We fixed that line in the Step 5 doc.

## The features (22)

The model uses 22 of the 27 feature-table columns. It leaves out IDs that invite memorizing (`claim_id`, `provider_id`) and raw dates, which do not carry over to future months. `submission_month` is used only to split.

- **Categories (one-hot):** payer, payer type, provider specialty and state, place of service, primary ICD-10, primary CPT, patient sex
- **Numbers (log, then scaled):** timely-filing days, line count, distinct CPT count, total units, total charge, largest line charge, days to submit, share of the timely-filing limit used, patient age
- **Flags:** requires prior auth, prior auth obtained, missing prior auth, past the timely-filing limit, has a Z-code diagnosis

As agreed, there is **no** hand-made "dx/procedure mismatch" feature.

## Results (seed 42, 100,000 claims)

| Set | PR-AUC | ROC-AUC | Brier | Denial rate | Precision in top 500 |
|---|---|---|---|---|---|
| Train | 0.381 | 0.742 | 0.0720 | 9.5% | 91.0% |
| **Holdout** | **0.418** | **0.745** | **0.0718** | **9.8%** | **66.2%** |

How to read this:

- **PR-AUC 0.418 vs a 9.8% base rate:** about **4.3×** better than guessing. This is the main metric, because denials are rare.
- **Train and holdout are close.** There is no sign of overfitting. Precision in the top 500 is higher on train only because 500 is a much smaller slice of 82k claims than of 17k.
- **Well calibrated:** the average predicted chance is 9.7% and the actual rate is 9.8%. Each risk band is close too. For example, claims scored 40% to 100% averaged 68.7% predicted and 65.9% actual.
- **The model found the planted drivers.** The biggest weights are past the timely-filing limit (+5.06), missing prior auth (+2.67) and has a Z-code diagnosis (+1.40).

### Does the worklist help?

These are the shares of all denied dollars in the holdout that sit in the **top 500 claims** (3% of the list):

| Sort the list by | Denied dollars caught |
|---|---|
| **Priority (P(deny) × charge)** | **53.1%** |
| P(deny) only | 40.8% |
| Charge only (biggest bills first) | 34.0% |
| Random | 3.0% |

Working the top 3% by priority catches **over half** of the denied dollars. That is about 1.6× better than "biggest bill first".

## What we built

| File | What it does |
|---|---|
| `src/rcm/models/features.py` | Feature lists, the leakage-safe join and the DuckDB loader |
| `src/rcm/models/split.py` | The time split (train, holdout, tail) |
| `src/rcm/models/baseline.py` | The scikit-learn pipeline: one-hot, log and scale, logistic regression. It turns any number type into float first, because raw DuckDB rows carry money as `Decimal`. |
| `src/rcm/models/metrics.py` | PR-AUC, ROC-AUC, Brier, precision@k and denied-dollars-captured@k |
| `src/rcm/models/priority.py` | Priority score and the ranked worklist. Ties break by `claim_id`, so the order is stable. |
| `src/rcm/models/train.py` | The command-line tool. It writes `baseline_logreg.joblib`, `metrics.json` and `worklist.csv`. |
| `docs/model-card.md` | A first model card (Step 17 completes it) |
| `pyproject.toml` | Adds `scikit-learn` and `duckdb` to the runtime dependencies |
| `.env.example` | Adds `RCM_DUCKDB_PATH` and `RCM_ARTIFACTS_DIR` |

## Tests (written first)

We wrote the tests first and ran them. They all failed at import, because `rcm.models` did not exist yet. Then we wrote the code until they passed. One bug was caught **by the integration test**: the saved model crashed on raw DuckDB rows because of `Decimal` money values. We fixed the pipeline and added a unit test so it stays fixed.

| Test file | What it checks |
|---|---|
| `test_model_split.py` | The default split gives exactly Jan 2025 to Mar 2026, Apr to Jun 2026 and Jul 2026 onward. No overlap, nothing lost, every train month is before every holdout month. Other windows work. An empty holdout is an error. |
| `test_model_features.py` | No feature is a remit, outcome, ID or raw-date column. There is no mismatch feature. The join matches by `claim_id` and rejects duplicates, missing labels and leaked outcome columns. |
| `test_model_priority.py` | Priority = p × balance × recoverability. Bad inputs are rejected. A big low-risk bill can outrank a small high-risk one. The list is sorted with ranks 1 to n. Ties are stable. The input is not changed. |
| `test_model_metrics.py` | Precision@k and dollars-captured@k on hand-worked examples. `evaluate` reports every metric and needs both classes. |
| `test_model_baseline.py` | It learns a planted signal, handles unseen categories, gives the same result every run, ignores undeclared columns (such as `paid_amount`) and accepts `Decimal` money. |
| `tests/integration/test_train_baseline.py` | Generate, dbt build, train. Metrics are logged and beat chance. The months are exactly as agreed. The tail is reported apart and **not scored**. The worklist is the holdout sorted by priority, with no outcome columns. Priority beats sorting by charge. The saved model reloads and scores. Paths come from env vars. |

## How to run it

```bash
source .venv/bin/activate
python -m rcm.generator --seed 42 --claims 100000 --months 18
dbt build --project-dir dbt --profiles-dir dbt
python -m rcm.models.train                 # reads data/rcm.duckdb, writes models/artifacts/
```

The output in `models/artifacts/` is git-ignored:

- `baseline_logreg.joblib`: the trained model
- `metrics.json`: every metric, the split months and the separate tail summary
- `worklist.csv`: holdout claims ranked by priority (rank, claim, payer, provider, CPT, charge, p_deny, recoverability, priority_score)

Test suite: **226 passed** (193 unit, 33 integration), with 98% coverage on `src/`.

## What is next

**Step 7: FastAPI v1.** Serve `/health`, `/score` (claim features in, denial probability out) and `/worklist?limit=` from this model and worklist.
