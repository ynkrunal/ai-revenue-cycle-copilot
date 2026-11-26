# Stage 1: Scaffold

**Date:** 2026-11-26 · **Status:** Done (waiting for review)

## What we did

We set up the empty Python project so that later steps have a place to put code, a linter, a test runner, and an automatic check on GitHub. There is no product logic yet.

## What we built

| File | What it is | Why it matters |
|---|---|---|
| `pyproject.toml` | Project settings: name `rcm`, Python 3.12 only, `[dev]` extras (pytest, pytest-cov, ruff) | One command installs everything we need |
| `src/rcm/__init__.py` | The empty package, with a version number | The "src layout" keeps tests honest: they test the installed package |
| `tests/unit/test_smoke.py` | Two tiny tests: the package imports and has a version, and we are on Python 3.12 | Proves the setup works before any real code exists |
| Ruff config (inside `pyproject.toml`) | Lint and format rules, 100-character lines | Keeps code style consistent and catches common bugs |
| `.github/workflows/ci.yml` | GitHub Actions job: install, `ruff check`, `ruff format --check`, `pytest` | Every push and pull request is checked automatically |

## How we built it (test-first)

1. **Red:** wrote `tests/unit/test_smoke.py` first and ran it. It failed with `ModuleNotFoundError: No module named 'rcm'`, as expected.
2. **Green:** added `pyproject.toml` and `src/rcm/__init__.py`, installed the package, and the tests passed.
3. **Refactor:** nothing to clean up yet.

## How to run it

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

ruff check . && ruff format --check .
pytest -q
pytest -q --cov=src --cov-report=term-missing
```

**Note for this Mac:** Homebrew could not install Python 3.12 (its folders belong to another macOS user). We installed Python 3.12.16 just for this user with `uv` instead. It lives at `~/.local/bin/python3.12`. Add `~/.local/bin` to your `PATH` so the `python3.12` command works.

## Results

- `ruff check .`: all checks passed
- `ruff format --check .`: all files already formatted
- `pytest -q`: 2 passed
- Coverage on `src/`: 100% (only one line of code so far)
- GitHub Actions: runs after the first push. We will confirm it is green then.

## What is next

**Step 2: Generator v1.** A seeded script that makes fake payers, providers, patients, and claims, with tests that the same seed always gives the same output.
