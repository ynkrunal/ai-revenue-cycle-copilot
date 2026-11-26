# Stage 4: dbt Init and Staging

**Date:** 2026-11-26 · **Status:** Done (waiting for review)

## What we did

We set up **dbt**, a tool that turns raw files into clean, tested database tables using SQL. It runs on **DuckDB**, a small database that lives in a single file on your laptop, so nothing needs a server. dbt reads the 7 Parquet files from Step 3 and makes one **staging model** for each. A staging model is a clean copy of a raw table with the right column types. We also added **schema tests**: automatic checks that run every time dbt builds.

## What we built

| File | What it does |
|---|---|
| `dbt/dbt_project.yml` | The dbt project. Staging models are built as views in the `main_staging` schema. |
| `dbt/profiles.yml` | How dbt connects to DuckDB. The database file path comes from `RCM_DUCKDB_PATH` (default `data/rcm.duckdb`). |
| `dbt/models/staging/_sources.yml` | Points dbt at the Parquet files. The folder comes from `RCM_RAW_DIR` (default `data/raw`). |
| `dbt/models/staging/stg_*.sql` | 7 staging models, one per raw table. They keep the same column names and cast each column to a clean SQL type. |
| `dbt/models/staging/_stg_models.yml` | A description of every model and its column tests |
| `dbt/tests/` | An empty folder for custom tests (Step 5) |
| `pyproject.toml` | Adds `dbt-core`, `dbt-duckdb` and `pyyaml` to the `[dev]` extras |

### Clean types

| Generator type | SQL type in staging |
|---|---|
| text | `VARCHAR` |
| whole number | `INTEGER` |
| money | `DECIMAL(12,2)`, exact cents with no rounding drift |
| yes/no | `BOOLEAN` |
| date | `DATE` |

### The 73 schema tests

| Test | What it catches | Where |
|---|---|---|
| `not_null` | Empty values | Every column except `rarc_code`, which is allowed to be empty |
| `unique` | Duplicate IDs | Every primary key (7) |
| `accepted_values` | Unknown codes | 13 columns: payer type, specialty, state, sex, place of service, CPT, ICD-10, claim status, group code, CARC and RARC |
| `relationships` | Broken links, such as a remit pointing at a claim that does not exist | All 8 foreign keys |

## Tests (written first)

We wrote the tests first and ran them. They failed (6 failed, 53 errors) because the `dbt/` folder did not exist yet. Then we built the dbt project until they passed.

| Test file | What it checks |
|---|---|
| `tests/unit/test_dbt_project.py` | Every raw table has a source and a staging model. Column names match the generator schema exactly. Every primary key has `unique` and `not_null`. Every required column has `not_null`. The `accepted_values` lists match the Python reference codes **exactly**, so adding a new CARC in Python without updating dbt fails a test. Every foreign key has a `relationships` test. Paths come from env vars. |
| `tests/integration/test_dbt_build.py` | Generates a small sample, runs a **real `dbt build`**, then opens the DuckDB file. Row counts match the Parquet files. Columns stay in order with the right SQL types. Money adds up to the cent. |
| (same file) | **Proves the tests work:** it plants bad data and checks that `dbt build` fails with the right test name. The bad data is an unknown payer type, a remit for a claim that does not exist, and a duplicate claim ID. |

## How to run it

Run these from the repo root:

```bash
source .venv/bin/activate
pip install -e ".[dev]"
python -m rcm.generator --seed 42 --claims 100000 --months 18   # writes data/raw/
dbt build --project-dir dbt --profiles-dir dbt                  # builds + tests
```

To use other folders, set the env vars first:

```bash
export RCM_RAW_DIR=/path/to/raw
export RCM_DUCKDB_PATH=/path/to/rcm.duckdb
```

To look at the data:

```bash
python -c "import duckdb; print(duckdb.connect('data/rcm.duckdb').sql('select * from main_staging.stg_claims limit 5'))"
```

The `data/rcm.duckdb`, `dbt/target/`, `dbt/logs/` and `dbt/.user.yml` files are git-ignored. dbt's anonymous usage stats are turned off in `dbt_project.yml`, so dbt sends nothing home.

## Results

On the full 100,000-claim data (seed 42), `dbt build` gave:

```
Finished running 73 data tests, 7 view models in 1.96 seconds
Completed successfully
Done. PASS=80 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=80
```

- `ruff check .` and `ruff format --check .`: passed
- `pytest -q`: **157 passed** (142 unit, 15 integration)
- Coverage on `src/`: 99%. dbt code is SQL and YAML, so the dbt tests cover it instead.
- dbt printed no deprecation warnings. Tests use the `data_tests:` and `arguments:` style that dbt 1.10 and later expect.

## A note on CI

dbt is now in the `[dev]` extras, so GitHub Actions installs it and runs the dbt integration tests as part of `pytest`. The separate `dbt build` step in CI is planned for Step 14.

## What is next

**Step 5: dbt marts.** Build `fct_claims`, `dim_payer`, `dim_provider`, `feat_claims_at_submission` (features known at submission only) and `mart_denial_kpis`. Add a custom test that no remit column leaks into the features.
