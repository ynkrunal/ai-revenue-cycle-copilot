"""Guard rails: IDs are obviously synthetic and nothing looks like a real SSN or MRN."""

import re

import pandas as pd
import pytest
from pandas.api import types as ptypes

ID_PATTERNS = {
    ("payers", "payer_id"): r"SYN-PAY-\d{4}",
    ("providers", "provider_id"): r"SYN-PRV-\d{5}",
    ("patients", "patient_id"): r"SYN-MRN-\d{6}",
    ("claims", "claim_id"): r"SYN-CLM-\d{7}",
    ("claim_lines", "claim_line_id"): r"SYN-CLM-\d{7}-L\d{2}",
}

# Any 9 digits laid out like an SSN (with dashes, spaces or nothing between groups).
SSN_LIKE = re.compile(r"(?<!\d)\d{3}[- ]?\d{2}[- ]?\d{4}(?!\d)")
# A bare run of 6+ digits is what real MRNs and account numbers usually look like.
BARE_LONG_NUMBER = re.compile(r"^\d{6,}$")


@pytest.mark.parametrize(("table", "column"), sorted(ID_PATTERNS))
def test_ids_use_synthetic_prefixes(
    tables: dict[str, pd.DataFrame], table: str, column: str
) -> None:
    pattern = ID_PATTERNS[(table, column)]
    assert tables[table][column].str.fullmatch(pattern).all()


def test_foreign_key_ids_are_synthetic_too(tables: dict[str, pd.DataFrame]) -> None:
    claims = tables["claims"]
    assert claims["patient_id"].str.startswith("SYN-MRN-").all()
    assert claims["provider_id"].str.startswith("SYN-PRV-").all()
    assert claims["payer_id"].str.startswith("SYN-PAY-").all()
    assert tables["patients"]["payer_id"].str.startswith("SYN-PAY-").all()


def _string_columns(tables: dict[str, pd.DataFrame]):
    for name, df in tables.items():
        for column in df.columns:
            if ptypes.is_string_dtype(df[column]):
                yield name, column, df[column].astype(str)


def test_no_value_looks_like_an_ssn(tables: dict[str, pd.DataFrame]) -> None:
    for name, column, values in _string_columns(tables):
        hits = values[values.str.contains(SSN_LIKE)]
        assert hits.empty, f"{name}.{column} has SSN-shaped values: {hits.head().tolist()}"


def test_no_value_looks_like_a_bare_mrn(tables: dict[str, pd.DataFrame]) -> None:
    for name, column, values in _string_columns(tables):
        hits = values[values.str.fullmatch(BARE_LONG_NUMBER)]
        assert hits.empty, f"{name}.{column} has bare numeric IDs: {hits.head().tolist()}"


def test_names_are_labelled_synthetic(tables: dict[str, pd.DataFrame]) -> None:
    assert tables["payers"]["payer_name"].str.startswith("Synthetic ").all()
    assert tables["providers"]["provider_name"].str.startswith("Synthetic ").all()


def test_patients_have_no_name_or_full_birth_date(tables: dict[str, pd.DataFrame]) -> None:
    columns = set(tables["patients"].columns)
    assert not columns & {"name", "first_name", "last_name", "dob", "birth_date", "ssn"}
