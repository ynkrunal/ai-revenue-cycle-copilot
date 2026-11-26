"""Static checks on the dbt marts: models exist, are documented and tested, and the
feature model cannot see remit data."""

import csv
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from rcm.generator import reference

DBT = Path(__file__).resolve().parents[2] / "dbt"
MARTS = DBT / "models" / "marts"
INTERMEDIATE = DBT / "models" / "intermediate"
MART_MODELS = [
    "fct_claims",
    "dim_payer",
    "dim_provider",
    "feat_claims_at_submission",
    "mart_denial_kpis",
]
REMIT_MODELS = {
    "stg_remits",
    "stg_remit_adjustments",
    "int_claim_outcomes",
    "fct_claims",
    "mart_denial_kpis",
}


def _models(path: Path) -> dict[str, dict[str, Any]]:
    return {m["name"]: m for m in yaml.safe_load(path.read_text())["models"]}


def _refs(sql: str) -> set[str]:
    return set(re.findall(r"ref\(\s*'([^']+)'\s*\)", sql)) | set(
        f"source:{t}" for t in re.findall(r"source\(\s*'raw'\s*,\s*'([^']+)'\s*\)", sql)
    )


def _upstream(model: str) -> set[str]:
    """Every model (and raw source) a model reads from, following refs all the way down."""
    folders = [DBT / "models" / d for d in ("staging", "intermediate", "marts")]
    sql_of = {p.stem: p.read_text() for f in folders for p in f.glob("*.sql")}
    seen: set[str] = set()
    todo = [model]
    while todo:
        for dep in _refs(sql_of.get(todo.pop(), "")):
            if dep not in seen:
                seen.add(dep)
                todo.append(dep)
    return seen


@pytest.mark.parametrize("model", MART_MODELS)
def test_mart_model_exists_and_is_documented(model: str) -> None:
    assert (MARTS / f"{model}.sql").is_file()
    doc = _models(MARTS / "_marts.yml")[model]
    assert doc.get("description")
    assert doc["columns"], f"{model} has no documented columns"


def test_feature_model_never_reads_remit_data() -> None:
    upstream = _upstream("feat_claims_at_submission")
    assert "stg_claims" in upstream  # sanity: the walk works
    assert not upstream & REMIT_MODELS
    assert not upstream & {"source:remits", "source:remit_adjustments"}


def test_leakage_test_exists() -> None:
    sql = (DBT / "tests" / "assert_no_remit_columns_in_features.sql").read_text()
    assert "feat_claims_at_submission" in sql


def test_carc_seed_matches_generator_reference() -> None:
    with (DBT / "seeds" / "carc_reference.csv").open() as f:
        rows = {r["carc_code"]: r for r in csv.DictReader(f)}
    assert set(rows) == set(reference.CARC_CODES)
    for code, carc in reference.CARC_CODES.items():
        assert rows[code]["description"] == carc.description
        assert (rows[code]["is_denial"] == "true") == (code in reference.DENIAL_CARC)
        assert rows[code]["carc_group"]
    non_denial_groups = {rows[c]["carc_group"] for c in rows if c not in reference.DENIAL_CARC}
    denial_groups = {rows[c]["carc_group"] for c in reference.DENIAL_CARC}
    assert not denial_groups & non_denial_groups


def test_planted_drivers_have_their_own_carc_group() -> None:
    with (DBT / "seeds" / "carc_reference.csv").open() as f:
        group = {r["carc_code"]: r["carc_group"] for r in csv.DictReader(f)}
    assert group["197"] == "authorization"
    assert group["29"] == "timely_filing"
    assert group["11"] == "coding"


def test_every_mart_key_is_tested() -> None:
    docs = _models(MARTS / "_marts.yml")
    keys = {
        "fct_claims": "claim_id",
        "dim_payer": "payer_id",
        "dim_provider": "provider_id",
        "feat_claims_at_submission": "claim_id",
    }
    for model, key in keys.items():
        col = next(c for c in docs[model]["columns"] if c["name"] == key)
        names = {t if isinstance(t, str) else next(iter(t)) for t in col["data_tests"]}
        assert {"unique", "not_null"} <= names, model


def test_documented_columns_match_sql_aliases() -> None:
    """Every documented mart column must appear as an output alias in its SQL."""
    docs = _models(MARTS / "_marts.yml")
    for model in MART_MODELS:
        sql = (MARTS / f"{model}.sql").read_text()
        for col in docs[model]["columns"]:
            assert re.search(rf"\b{col['name']}\b", sql), f"{model}.{col['name']}"
