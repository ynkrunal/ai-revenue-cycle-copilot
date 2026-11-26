"""Schema tests: every generated table has the agreed columns, types, keys and values."""

import pandas as pd
import pytest
from pandas.api import types as ptypes

from rcm.generator import reference
from rcm.generator.schema import PRIMARY_KEYS, SCHEMAS

DTYPE_CHECKS = {
    "string": ptypes.is_string_dtype,
    "int": ptypes.is_integer_dtype,
    "float": ptypes.is_float_dtype,
    "bool": ptypes.is_bool_dtype,
    "date": ptypes.is_datetime64_any_dtype,
}


def test_generate_returns_exactly_the_schema_tables(tables: dict[str, pd.DataFrame]) -> None:
    assert set(tables) == set(SCHEMAS)


@pytest.mark.parametrize("table", sorted(SCHEMAS))
def test_columns_match_schema_in_order(tables: dict[str, pd.DataFrame], table: str) -> None:
    assert list(tables[table].columns) == list(SCHEMAS[table])


@pytest.mark.parametrize("table", sorted(SCHEMAS))
def test_column_types_match_schema(tables: dict[str, pd.DataFrame], table: str) -> None:
    df = tables[table]
    for column, kind in SCHEMAS[table].items():
        assert DTYPE_CHECKS[kind](df[column]), f"{table}.{column} should be {kind}"


@pytest.mark.parametrize("table", sorted(SCHEMAS))
def test_no_nulls(tables: dict[str, pd.DataFrame], table: str) -> None:
    assert not tables[table].isna().any().any()


@pytest.mark.parametrize("table", sorted(SCHEMAS))
def test_primary_key_is_unique(tables: dict[str, pd.DataFrame], table: str) -> None:
    key = PRIMARY_KEYS[table]
    assert tables[table][key].is_unique
    assert len(tables[table]) > 0


def test_accepted_values(tables: dict[str, pd.DataFrame]) -> None:
    assert set(tables["payers"]["payer_type"]) <= reference.PAYER_TYPES
    assert set(tables["patients"]["sex"]) <= reference.SEXES
    assert set(tables["providers"]["specialty"]) <= set(reference.SPECIALTY_CPT)
    assert set(tables["claims"]["place_of_service"]) <= set(reference.PLACES_OF_SERVICE)
    assert set(tables["claim_lines"]["cpt_code"]) <= set(reference.CPT_CODES)
    assert set(tables["claim_lines"]["icd10_code"]) <= set(reference.ICD10_CODES)
    assert set(tables["claims"]["primary_icd10"]) <= set(reference.ICD10_CODES)
