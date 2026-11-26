# Stage 3: Generator v2

**Date:** 2026-11-26 · **Status:** Done (waiting for review)

## What we did

We taught the fake-data generator to make the **insurance company's answer** to every claim: a remit, like an 835 file. A remit says paid, denied or partly denied, how much was paid, and **why**, using standard CARC and RARC reason codes. We planted clear reasons for denials in the data, added random "noise" denials, and added a command-line tool that saves everything as Parquet files.

## What we built

| File | What it does |
|---|---|
| `src/rcm/generator/remits.py` | Makes one remit per claim plus its adjustment lines (CARC/RARC codes and dollar amounts) |
| `src/rcm/generator/reference.py` | New lookups: 11 CARC codes with their RARC partner, denial-driver strengths, and payer terms (noise rate, allowed %, patient share) |
| `src/rcm/generator/schema.py` | Two new tables (`remits`, `remit_adjustments`). `rarc_code` is the only column allowed to be empty. |
| `src/rcm/generator/io.py` | Writes and reads one Parquet file per table |
| `src/rcm/generator/__main__.py` | The command-line tool |
| `.env.example` | Placeholder for `RCM_RAW_DIR`, the output folder |
| `pyproject.toml` | Adds `pyarrow`, which pandas needs to write Parquet |

### The two new tables

| Table | One row is | Key columns |
|---|---|---|
| `remits` | the payer's first answer to a claim | `claim_status` (paid, partially_denied, denied), `adjudication_date` (7 to 45 days after submission), `allowed_amount`, `paid_amount`, `patient_responsibility` |
| `remit_adjustments` | one reason money was not paid on a line | `group_code` (CO = provider absorbs it, PR = patient owes it), `carc_code`, `rarc_code`, `adjustment_amount` |

The money always balances: **billed charge = paid + all adjustments**. A tested rule enforces it.

### Why claims get denied (the planted drivers)

Each driver uses only facts known **when the claim is sent**, so the model can learn them in later steps.

| Driver | Rule | Denial code | Chance of denial when present |
|---|---|---|---|
| Late submission | Sent after the payer's timely-filing limit (90, 180 or 365 days) | CARC 29 | 95% |
| Missing prior auth | MRI, stress test, colonoscopy or cataract surgery without auth | CARC 197 + RARC M62 | 80% |
| Diagnosis/procedure mismatch | Wellness diagnosis (Z00.00) on a sick visit, or screening diagnosis (Z12.11) on a diagnostic colonoscopy | CARC 11 + RARC M76 | 50% |
| Strict payer | Medicaid and Medicare Advantage | (raises the noise rate) | about 2× the others |
| **Noise** | Random, with no reason the data can show | CARC 16, 27, 50, 18 or 96 | 2% to 13%, depending on payer type |

If more than one driver applies, only one reason is used, in this order: late, then auth, then mismatch, then noise. Noise denials hit the whole claim 60% of the time and one random line otherwise.

### Safety rule: no leaks

Remit fields (CARC, paid amount, status and so on) live **only** in the remit tables. The claim tables are unchanged from Step 2, and a test checks that no remit column appears on them. This is what stops the model from "cheating" later.

## Tests (written first)

We wrote the tests first and ran them. They failed (missing `NULLABLE_COLUMNS`, `io` and CLI). Then we wrote the code until they passed.

| Test file | What it checks |
|---|---|
| `tests/unit/test_generator_remits.py` | One remit per claim. Dates in order. Money balances. Status matches the CARC codes. Fully denied claims pay $0. Partial denials exist. RARC matches its CARC. CO/PR groups are right. No remit fields on claim tables. |
| `tests/unit/test_generator_denial_drivers.py` | 40,000 claims: denial rate between 8% and 15%. **Every driver has lift above 1.5.** Each driver shows up as its own CARC. Driver CARCs never appear without the driver. Noise exists on "clean" claims. No driver is 100% certain. |
| `tests/unit/test_generator_io.py` | Parquet write and read give back the same data. The output folder comes from the flag, then the env var, then `data/raw`. The CLI matches the library for the same seed. Bad arguments are rejected. |
| `tests/unit/test_generator_schema.py`, `test_generator_synthetic.py` | Extended to cover the two new tables and their `SYN-RMT-` and `SYN-ADJ-` IDs |
| `tests/integration/test_generator_cli.py` | Runs the real CLI at **full size** (100,000 claims, 18 months), checks all 7 files, the denial rate, and that every remit links back to a claim |

The driver tests rebuild each driver flag **directly from the claim data**, not from the generator's code. So they check the data itself, not just our code.

"Lift" means how much more often claims **with** a driver are denied than claims **without** it. A lift of 2 means twice as often.

## How to run it

```bash
source .venv/bin/activate
pip install -e ".[dev]"
python -m rcm.generator --seed 42 --claims 100000 --months 18
```

Options: `--start-date 2025-01-01`, `--providers 200`, `--out <folder>`. Without `--out`, it uses `$RCM_RAW_DIR`, then `data/raw/`. The files are git-ignored and never committed.

## Results (seed 42, 100,000 claims, 18 months)

Run time: about 2.5 seconds.

| Table | Rows |
|---|---|
| claims | 100,000 |
| claim_lines | 187,995 |
| remits | 100,000 |
| remit_adjustments | 362,074 |

**Denial rate: 9.7%** (6,415 fully denied and 3,277 partly denied)

| Driver | Claims with it | Denied with it | Denied without it | Lift |
|---|---|---|---|---|
| Missing prior auth | 831 | 82.2% | 9.1% | 9.05 |
| Late submission | 670 | 95.1% | 9.1% | 10.43 |
| Dx/procedure mismatch | 4,595 | 52.9% | 7.6% | 6.95 |
| Strict payer | 24,300 | 15.4% | 7.9% | 1.96 |

About 64% of denials are noise. That is on purpose: the model must not find this too easy.

Test suite: **98 passed** (90 unit, 8 integration), with **99% coverage** on `src/`.

## What is next

**Step 4: dbt init + staging.** Set up a dbt project on DuckDB, read these Parquet files into staging models, and add `unique`, `not_null` and `accepted_values` tests.
