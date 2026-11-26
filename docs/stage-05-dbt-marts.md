# Stage 5: dbt Marts

**Date:** 2026-11-26 · **Status:** Done (waiting for review)

## What we did

We built the **marts**: the finished tables that the model, the API and the dashboard will read. There are five:

| Mart | One row is | Used for |
|---|---|---|
| `fct_claims` | a claim and what the payer decided | the **label** (`is_denied`), the worklist dollars, KPIs |
| `dim_payer` | a payer | names, payer type, timely-filing limit |
| `dim_provider` | a provider | names, specialty, state |
| `feat_claims_at_submission` | a claim, as it looked **on the day it was sent** | **model features** (Step 6 onward) |
| `mart_denial_kpis` | a submission month and payer | denial rate, dollars denied, top denial reason, trends |

We also added two **intermediate** models (helper views) and one **seed** (a small lookup CSV).

## How the data flows

```
raw Parquet → staging (Step 4)
                ├── int_claim_line_summary ─┐
                │   (line facts per claim)  ├─→ feat_claims_at_submission   ← features
                ├── claims, payers, ... ────┘
                │
                ├── remits + adjustments → int_claim_outcomes ─→ fct_claims ─→ mart_denial_kpis
                │                          (labels only)         ↑ dim_payer, dim_provider
                └── carc_reference (seed) ─┘
```

The feature table and the remit data sit on **separate branches**. They meet only later, in Python, when we join features to the label by `claim_id`.

## The leakage guard (the key acceptance test)

"Leakage" means the model can see the answer while training. For example, it could see the paid amount, which is only known **after** the payer decides. A leaky model looks great in testing and fails in real life. We check for leakage in four ways:

| Check | Where | How it works |
|---|---|---|
| **dbt test** `assert_no_remit_columns_in_features` | `dbt/tests/` | Fails if any feature column also exists in a remit table, or has a name like `paid`, `allowed`, `carc`, `denied`, `adjudicat`, `status`... It also fails if the feature table is missing. |
| **Lineage check** (pytest) | `tests/integration/test_dbt_marts.py` | Reads dbt's own dependency graph (`manifest.json`) and follows the feature model all the way back to the raw files. It must never reach `remits`, `remit_adjustments`, `int_claim_outcomes` or `fct_claims`. |
| **Proof the dbt test works** (pytest) | same file | Copies the dbt project, sneaks `paid_amount` into the feature SQL, runs `dbt build`, and checks that it **fails** on the leakage test |
| **Static SQL check** (pytest) | `tests/unit/test_dbt_marts_project.py` | Follows every `ref()` in the SQL files, with no build needed |

## The features (27 columns)

All are knowable on the day the claim is sent:

- **Who:** `payer_id`, `payer_type`, `timely_filing_days`, `provider_id`, `provider_specialty`, `provider_state`, `patient_age_at_service`, `patient_sex`
- **What:** `place_of_service`, `primary_icd10`, `primary_cpt_code`, `line_count`, `distinct_cpt_count`, `total_units`, `total_charge`, `max_line_charge`, `has_z_code_dx`
- **Auth:** `requires_prior_auth`, `prior_auth_obtained`, `missing_prior_auth`
- **Timing:** `service_date`, `submission_date`, `submission_month` (for the time split), `days_to_submit`, `past_timely_filing_limit`, `share_of_timely_limit_used`

We did **not** add a hand-made "dx/procedure mismatch" flag that copies the generator's rule. The model should find that pattern itself, from `primary_icd10`, `primary_cpt_code` and `has_z_code_dx`.

## The CARC seed

`dbt/seeds/carc_reference.csv` lists all 11 CARC codes with their description, whether each is a denial, and a **reason group**: authorization, timely_filing, coding, billing_error, eligibility, medical_necessity, duplicate, non_covered, contractual or patient_responsibility. KPIs use the groups now. Step 11 will use them for "recoverability". A pytest check keeps the seed in sync with the generator's `reference.py`.

## Other custom dbt tests

| Test | What it checks |
|---|---|
| `assert_one_row_per_claim_in_marts` | `fct_claims` and the feature table each have exactly one row per claim |
| `assert_label_matches_status` | `is_denied`, `claim_status`, the denial CARC and the denied dollars all agree |
| `assert_kpis_reconcile_to_fct_claims` | The KPI totals (claims, denials, dollars) add back up to `fct_claims` exactly, with one row per month and payer |
| `assert_kpi_denial_rate_in_range` | The denial rate is between 0 and 1 |

## Tests (written first)

We wrote the tests first and ran them: 20 failed, because no marts existed yet. Then we built the models until they passed. The integration tests also check the marts against the raw Parquet data, computed separately in pandas. They check the label, the denial reason and dollars, `days_to_submit`, `missing_prior_auth`, `past_timely_filing_limit`, patient age, primary CPT, submission month and the KPI totals by month.

We also moved the `dbt build` runner into `tests/integration/dbt_helpers.py`, so the staging and marts tests share it.

## How to run it

```bash
source .venv/bin/activate
python -m rcm.generator --seed 42 --claims 100000 --months 18
dbt build --project-dir dbt --profiles-dir dbt
```

To look at the KPIs:

```bash
python -c "import duckdb; print(duckdb.connect('data/rcm.duckdb').sql('select * from main_marts.mart_denial_kpis limit 10'))"
```

## Results (seed 42, 100,000 claims)

```
Finished running 1 seed, 5 table models, 161 data tests, 9 view models in 5.54 seconds
Completed successfully
Done. PASS=176 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=176
```

- Denial rate in `fct_claims`: **9.69%**, the same as Step 3
- Medicaid and Medicare Advantage are denied about **2×** as often as Medicare (15.6% and 15.1% vs 6.0%)
- **Authorization** denials are few (662 claims) but carry the most dollars (**$1.43M** of $4.36M denied), because they hit expensive services
- Test suite: **177 passed** (153 unit, 24 integration), coverage 99% on `src/`

## A heads-up for Step 6

Service dates run January 2025 to June 2026, but late claims are **sent** up to 120 days later. So submission months July to October 2026 have only a few claims each (1,097, 242, 130 and 36), and those are mostly late filers. If Step 6 used the "last 3 submission months" as the holdout, it would test on only 408 claims that are nearly all late. Step 6 should define the holdout as the last 3 months **of the 18-month window** (April to June 2026). It should then drop the thin tail or put it in the holdout, and the stage doc should say which.

## What is next

**Step 6: Baseline + priority.** Train a logistic regression on `feat_claims_at_submission` joined to the `fct_claims` label, using a time-based split. Log PR-AUC and ROC-AUC, compute the priority score, and write a worklist CSV sorted by priority.
