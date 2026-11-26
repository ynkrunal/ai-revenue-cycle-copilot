"""Static checks on the dbt project: it covers every raw table and its tests stay in
sync with the generator's schema and reference codes."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from rcm.generator import reference
from rcm.generator.schema import NULLABLE_COLUMNS, PRIMARY_KEYS, SCHEMAS

DBT = Path(__file__).resolve().parents[2] / "dbt"
STAGING = DBT / "models" / "staging"

FOREIGN_KEYS = {
    ("patients", "payer_id"): ("payers", "payer_id"),
    ("claims", "patient_id"): ("patients", "patient_id"),
    ("claims", "provider_id"): ("providers", "provider_id"),
    ("claims", "payer_id"): ("payers", "payer_id"),
    ("claim_lines", "claim_id"): ("claims", "claim_id"),
    ("remits", "claim_id"): ("claims", "claim_id"),
    ("remit_adjustments", "remit_id"): ("remits", "remit_id"),
    ("remit_adjustments", "claim_line_id"): ("claim_lines", "claim_line_id"),
}

ACCEPTED_VALUES = {
    ("payers", "payer_type"): reference.PAYER_TYPES,
    ("providers", "specialty"): set(reference.SPECIALTY_CPT),
    ("providers", "state"): set(reference.STATES),
    ("patients", "sex"): reference.SEXES,
    ("patients", "state"): set(reference.STATES),
    ("claims", "place_of_service"): set(reference.PLACES_OF_SERVICE),
    ("claims", "primary_icd10"): set(reference.ICD10_CODES),
    ("claim_lines", "cpt_code"): set(reference.CPT_CODES),
    ("claim_lines", "icd10_code"): set(reference.ICD10_CODES),
    ("remits", "claim_status"): reference.CLAIM_STATUSES,
    ("remit_adjustments", "group_code"): reference.GROUP_CODES,
    ("remit_adjustments", "carc_code"): set(reference.CARC_CODES),
    ("remit_adjustments", "rarc_code"): reference.RARC_CODES,
}


def _load(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text())


@pytest.fixture(scope="module")
def models() -> dict[str, dict[str, Any]]:
    doc = _load(STAGING / "_stg_models.yml")
    return {m["name"]: m for m in doc["models"]}


def _column_tests(model: dict[str, Any], column: str) -> dict[str, Any]:
    """Map test name -> its arguments (or None) for one column."""
    col = next(c for c in model["columns"] if c["name"] == column)
    out: dict[str, Any] = {}
    for test in col.get("data_tests", []):
        if isinstance(test, str):
            out[test] = None
        else:
            ((name, body),) = test.items()
            out[name] = (body or {}).get("arguments", body)
    return out


def test_project_and_profile_exist() -> None:
    project = _load(DBT / "dbt_project.yml")
    assert project["profile"] == "rcm"
    profile = _load(DBT / "profiles.yml")
    assert "duckdb" in profile["rcm"]["outputs"]


def test_profile_reads_paths_from_env_vars() -> None:
    text = (DBT / "profiles.yml").read_text()
    assert "env_var('RCM_DUCKDB_PATH'" in text
    sources = (STAGING / "_sources.yml").read_text()
    assert "env_var('RCM_RAW_DIR'" in sources


def test_every_raw_table_is_a_source() -> None:
    doc = _load(STAGING / "_sources.yml")
    (raw,) = [s for s in doc["sources"] if s["name"] == "raw"]
    assert {t["name"] for t in raw["tables"]} == set(SCHEMAS)


@pytest.mark.parametrize("table", sorted(SCHEMAS))
def test_every_raw_table_has_a_staging_model(models: dict[str, dict[str, Any]], table: str) -> None:
    name = f"stg_{table}"
    assert (STAGING / f"{name}.sql").is_file()
    assert name in models
    sql = (STAGING / f"{name}.sql").read_text()
    assert f"source('raw', '{table}')" in sql


@pytest.mark.parametrize("table", sorted(SCHEMAS))
def test_staging_columns_match_generator_schema(
    models: dict[str, dict[str, Any]], table: str
) -> None:
    documented = [c["name"] for c in models[f"stg_{table}"]["columns"]]
    assert documented == list(SCHEMAS[table])


@pytest.mark.parametrize("table", sorted(SCHEMAS))
def test_primary_keys_are_unique_and_not_null(
    models: dict[str, dict[str, Any]], table: str
) -> None:
    tests = _column_tests(models[f"stg_{table}"], PRIMARY_KEYS[table])
    assert "unique" in tests
    assert "not_null" in tests


@pytest.mark.parametrize("table", sorted(SCHEMAS))
def test_required_columns_are_not_null(models: dict[str, dict[str, Any]], table: str) -> None:
    nullable = NULLABLE_COLUMNS.get(table, set())
    for column in SCHEMAS[table]:
        tests = _column_tests(models[f"stg_{table}"], column)
        assert ("not_null" in tests) == (column not in nullable), f"{table}.{column}"


@pytest.mark.parametrize(("table", "column"), sorted(ACCEPTED_VALUES))
def test_accepted_values_match_reference(
    models: dict[str, dict[str, Any]], table: str, column: str
) -> None:
    tests = _column_tests(models[f"stg_{table}"], column)
    assert "accepted_values" in tests, f"{table}.{column}"
    values = {str(v) for v in tests["accepted_values"]["values"]}
    assert values == {str(v) for v in ACCEPTED_VALUES[(table, column)]}


@pytest.mark.parametrize(("child", "parent"), sorted(FOREIGN_KEYS.items()))
def test_foreign_keys_have_relationship_tests(
    models: dict[str, dict[str, Any]], child: tuple[str, str], parent: tuple[str, str]
) -> None:
    tests = _column_tests(models[f"stg_{child[0]}"], child[1])
    assert "relationships" in tests, f"{child} -> {parent}"
    args = tests["relationships"]
    assert args["to"] == f"ref('stg_{parent[0]}')"
    assert args["field"] == parent[1]
