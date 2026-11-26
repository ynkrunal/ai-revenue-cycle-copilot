"""Run a real `dbt build` on a small generated sample and inspect the DuckDB result."""

import subprocess
from pathlib import Path

import pandas as pd
import pytest

from rcm.generator import GeneratorConfig, generate
from rcm.generator.io import read_tables, write_tables
from rcm.generator.schema import SCHEMAS
from tests.integration.dbt_helpers import query as _query
from tests.integration.dbt_helpers import run_dbt_build


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    work = tmp_path_factory.mktemp("dbt")
    raw = work / "raw"
    write_tables(generate(GeneratorConfig(seed=1, n_claims=3_000, months=6)), raw)
    result = run_dbt_build(raw, work)
    assert result.returncode == 0, result.stdout[-4000:]
    return raw, work / "rcm.duckdb"


def test_every_staging_model_has_the_raw_row_count(built: tuple[Path, Path]) -> None:
    raw, db = built
    raw_tables = read_tables(raw)
    for table in SCHEMAS:
        ((count,),) = _query(db, f"select count(*) from main_staging.stg_{table}")
        assert count == len(raw_tables[table]), table


def test_staging_columns_keep_schema_order(built: tuple[Path, Path]) -> None:
    _, db = built
    for table, columns in SCHEMAS.items():
        rows = _query(
            db,
            "select column_name from information_schema.columns "
            f"where table_schema = 'main_staging' and table_name = 'stg_{table}' "
            "order by ordinal_position",
        )
        assert [r[0] for r in rows] == list(columns), table


EXPECTED_SQL_TYPES = {
    "string": "VARCHAR",
    "int": "INTEGER",
    "float": "DECIMAL(12,2)",
    "bool": "BOOLEAN",
    "date": "DATE",
}


def test_staging_casts_to_clean_sql_types(built: tuple[Path, Path]) -> None:
    _, db = built
    for table, columns in SCHEMAS.items():
        rows = dict(
            _query(
                db,
                "select column_name, data_type from information_schema.columns "
                f"where table_schema = 'main_staging' and table_name = 'stg_{table}'",
            )
        )
        for column, kind in columns.items():
            assert rows[column] == EXPECTED_SQL_TYPES[kind], f"{table}.{column}: {rows[column]}"


def test_money_survives_the_cast_exactly(built: tuple[Path, Path]) -> None:
    raw, db = built
    expected = round(float(read_tables(raw)["claims"]["total_charge"].sum()), 2)
    ((actual,),) = _query(db, "select sum(total_charge) from main_staging.stg_claims")
    assert float(actual) == pytest.approx(expected, abs=0.01)


def _corrupt_and_build(tmp_path: Path, table: str, change) -> subprocess.CompletedProcess[str]:
    tables = generate(GeneratorConfig(seed=2, n_claims=300, months=2))
    tables[table] = change(tables[table].copy())
    write_tables(tables, tmp_path / "raw")
    return run_dbt_build(tmp_path / "raw", tmp_path)


def test_build_fails_on_unknown_payer_type(tmp_path: Path) -> None:
    def bad(df: pd.DataFrame) -> pd.DataFrame:
        df.loc[0, "payer_type"] = "bogus"
        return df

    result = _corrupt_and_build(tmp_path, "payers", bad)
    assert result.returncode != 0
    assert "accepted_values_stg_payers_payer_type" in result.stdout


def test_build_fails_on_orphan_remit(tmp_path: Path) -> None:
    def bad(df: pd.DataFrame) -> pd.DataFrame:
        df.loc[0, "claim_id"] = "SYN-CLM-9999999"
        return df

    result = _corrupt_and_build(tmp_path, "remits", bad)
    assert result.returncode != 0
    assert "relationships_stg_remits_claim_id" in result.stdout


def test_build_fails_on_duplicate_claim_id(tmp_path: Path) -> None:
    def bad(df: pd.DataFrame) -> pd.DataFrame:
        df.loc[1, "claim_id"] = df.loc[0, "claim_id"]
        return df

    result = _corrupt_and_build(tmp_path, "claims", bad)
    assert result.returncode != 0
    assert "unique_stg_claims_claim_id" in result.stdout
