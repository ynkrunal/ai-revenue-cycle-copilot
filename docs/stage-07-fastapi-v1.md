# Stage 7: FastAPI v1

**Date:** 2026-11-26 · **Status:** Done (waiting for review)

## What we did

We put the Step 6 model and worklist behind a small **web API** built with **FastAPI**. Other programs, like the Streamlit app in Step 8, can now ask it questions over HTTP:

| Endpoint | Question it answers | Example |
|---|---|---|
| `GET /health` | "Is the API ready?" | `{"status": "ok", "model_loaded": true, "model": "baseline_logreg", "worklist_rows": 16614}` |
| `POST /score` | "What is the chance this claim gets denied?" | Send one claim's 22 features and get back `p_deny`, `recoverability` and `priority_score` |
| `GET /worklist?limit=50&offset=0` | "Which claims should I work first?" | One page of the ranked worklist, plus the `total` row count |

FastAPI also gives free, interactive docs at `/docs`.

## How it works

1. At startup, the API loads `baseline_logreg.joblib` and `worklist.csv` **once** from `$RCM_ARTIFACTS_DIR` (default `models/artifacts`).
2. `/score` checks the request, runs the model, and computes `priority = p_deny × total_charge × recoverability`. Recoverability is still 1.0 until Step 11.
3. `/worklist` returns rows from the Step 6 worklist in rank order. It does not re-score anything.
4. If the files are missing, the API still starts. `/health` answers **503** (`"status": "unavailable"`), and `/score` and `/worklist` answer **503** too, instead of crashing.

## Input checks (pydantic schemas)

`POST /score` only accepts a claim that looks right:

- **All 22 model features are required.** A missing one gives a `422` error that names the field.
- **Coded fields must use known values:** payer type, specialty, place of service, sex and state. These lists are tested against the generator's `reference.py`, so they cannot drift apart.
- **Numbers must make sense:** charges ≥ 0, at least 1 line, age 0 to 120, days to submit ≥ 0, timely-filing days > 0.
- **Unknown fields are rejected.** This is a leakage guard at the API's front door. Sending `paid_amount`, `is_denied`, `carc_code` or any other outcome gives a `422` error. Only submission-time facts get in.
- **New CPT or ICD-10 codes are allowed** (any text). The model ignores categories it has never seen, instead of failing.

The worklist keeps codes as **text**, so CPT `66984` stays `"66984"` and is never turned into a number.

## What we built

| File | What it does |
|---|---|
| `src/rcm/api/schemas.py` | Request and response shapes (`ClaimFeatures`, `ScoreResponse`, `WorklistItem`, `WorklistResponse`, `HealthResponse`) |
| `src/rcm/api/artifacts.py` | Finds and loads the model and worklist. The folder comes from the argument, then `$RCM_ARTIFACTS_DIR`, then `models/artifacts`. |
| `src/rcm/api/main.py` | `create_app()` builds the app, and `app` is what uvicorn runs |
| `pyproject.toml` | Adds `fastapi` and `uvicorn` (runtime), and `httpx` (dev, needed by `TestClient`) |

## Tests (written first)

We wrote the tests first and ran them. They failed at import, because `rcm.api` did not exist yet. Then we wrote the code until they passed.

| Test file | What it checks |
|---|---|
| `tests/unit/test_api_schemas.py` | Request fields are **exactly** the model's features (plus an optional `claim_id`). Coded fields match `reference.py`. Bad values are rejected. Outcome fields are rejected. Worklist fields match the CSV columns. |
| `tests/integration/test_api.py` | Runs the **real Step 6 pipeline** once (generate 20k claims, dbt build, train), then calls the API through FastAPI's `TestClient` |

The integration tests check:

- **`/health`:** it reports ready, and gives 503 with no artifacts.
- **`/score`:** the score equals the saved model's own prediction (to 1e-9) and matches the worklist's `p_deny` for the same claim. Priority = p × charge. An unseen CPT code works. Bad, missing and leaky inputs give 422. No model gives 503.
- **`/worklist`:** the default page is ranks 1 to 50 in priority order, with the right total. `limit` and `offset` work. A page past the end is empty. Bad paging gives 422. Codes stay text. There are no outcome fields. No artifacts gives 503.
- **Wiring:** OpenAPI lists all 3 endpoints, the env var sets the artifacts folder, and the module-level `app` exists for uvicorn.

## Manual check with the real server

We started `uvicorn` on the full 100,000-claim artifacts and called each endpoint:

```
GET  /health              -> {"status":"ok","model_loaded":true,"model":"baseline_logreg","worklist_rows":16614}
GET  /worklist?limit=2    -> rank 1: SYN-CLM-0054061, cataract surgery, $6,491.27, p_deny 0.7355, priority 4774.31
POST /score (that claim)  -> p_deny 0.735497..., priority 4774.31   (same as the worklist)
POST /score + paid_amount -> 422 "Extra inputs are not permitted"
```

## How to run it

```bash
source .venv/bin/activate
python -m rcm.generator --seed 42 --claims 100000 --months 18
dbt build --project-dir dbt --profiles-dir dbt
python -m rcm.models.train
uvicorn rcm.api.main:app --reload          # http://127.0.0.1:8000/docs
```

```bash
curl http://127.0.0.1:8000/health
curl "http://127.0.0.1:8000/worklist?limit=10"
```

## Results

- `ruff check .` and `ruff format --check .`: passed
- `pytest -q`: **268 passed** (212 unit, 56 integration), with 99% coverage on `src/` and 100% on `src/rcm/api/`
- `dbt build`: PASS=176, WARN=0, ERROR=0

**One known warning:** Starlette 1.10 prints `Using httpx with starlette.testclient is deprecated; install httpx2 instead`. Tests work fine with `httpx`. Switching the dev dependency to `httpx2` is a separate decision.

## What is next

**Step 8: Streamlit v1 + docker compose.** A Streamlit worklist page that calls this API, and `docker compose up` to start both. That completes the **thin slice**.
