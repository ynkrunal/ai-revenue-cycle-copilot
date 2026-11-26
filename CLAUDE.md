# CLAUDE.md

AI Revenue Cycle Copilot: predicts claim denial risk and ranks a worklist for denials/AR analysts.
Read `PRD.md` (what and why), `spec/plan.md` (how), and `TASK.md` (current step) before starting work.

## Hard rules

1. **Synthetic data only.** Never use, request, or generate real PHI or PII. All patients, providers, payers and IDs come from the generator and use synthetic prefixes (e.g., `SYN-MRN-000123`).
2. **Never read or commit `.env` or secrets.** This includes `service-account*.json`, API keys and tokens. Use `.env.example` for placeholder names only.
3. **One `TASK.md` step at a time.** Do not start the next step until the current one is approved, committed and pushed.
4. **Never claim tests pass without running them** and showing the actual command output.
5. **Test-first (TDD):** write the failing test, make it pass, then refactor. Unit and integration tests.
6. **No commit or push until the user has reviewed the diff** and approved it.

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Test commands (run all before saying a step is done)

```bash
ruff check . && ruff format --check .            # lint + format
pytest -q                                        # full test suite
pytest -q tests/unit                             # unit tests only
pytest -q tests/integration                      # integration tests only
pytest -q --cov=src --cov-report=term-missing    # coverage (target >= 80%)
dbt build --project-dir dbt --profiles-dir dbt   # dbt models + tests (DuckDB)
docker compose build                             # images build
```

Commands become available as their `TASK.md` step lands (pytest from step 1, dbt from step 4, Docker from step 8).

## Common commands

```bash
python -m rcm.generator --seed 42 --claims 100000 --months 18   # synthetic data -> data/raw/
uvicorn rcm.api.main:app --reload                               # API on :8000
streamlit run src/rcm/ui/app.py                                 # UI on :8501
docker compose up                                               # API + UI
```

## Per-step workflow

1. Set the step to `Doing` in `TASK.md`.
2. Write tests first, then implement.
3. Run the full test commands above and paste the output.
4. Write `docs/stage-NN-<slug>.md` in simple English: what was built, why, how to run it, what is next.
5. Set the step to `Done` in `TASK.md`.
6. Show `git status` and `git diff`, then **wait for approval**.
7. After approval: commit with a clear "why" message, then `git push`.

## Conventions

- Python 3.12, src layout (`src/rcm/`), type hints, ruff for lint and format.
- Config comes from environment variables; nothing environment-specific is hard-coded.
- Model features use **as-of-submission fields only**. Remit fields are labels only (leakage guard).
- Time-based train/test split (last 3 months = holdout). Never a random split.
- Never name a source folder `data/`, because `.gitignore` ignores every `data/` directory.
- Generated data (`data/`, `*.parquet`, `*.duckdb`) and model artifacts are never committed.
