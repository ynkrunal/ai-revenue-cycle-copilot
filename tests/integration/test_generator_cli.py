"""Acceptance run: the real CLI, full size (100k claims, 18 months) to Parquet."""

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from rcm.generator.io import read_tables
from rcm.generator.schema import SCHEMAS


@pytest.fixture(scope="module")
def raw(tmp_path_factory: pytest.TempPathFactory) -> dict[str, pd.DataFrame]:
    out = tmp_path_factory.mktemp("raw")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "rcm.generator",
            "--seed",
            "42",
            "--claims",
            "100000",
            "--months",
            "18",
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    assert result.returncode == 0, result.stderr
    assert sorted(p.name for p in Path(out).glob("*.parquet")) == sorted(
        f"{t}.parquet" for t in SCHEMAS
    )
    return read_tables(out)


def test_full_run_has_100k_claims_over_18_months(raw: dict[str, pd.DataFrame]) -> None:
    claims = raw["claims"]
    assert len(claims) == 100_000
    assert claims["service_date"].dt.to_period("M").nunique() == 18


def test_full_run_denial_rate_between_8_and_15_percent(raw: dict[str, pd.DataFrame]) -> None:
    rate = (raw["remits"]["claim_status"] != "paid").mean()
    assert 0.08 <= rate <= 0.15


def test_full_run_every_remit_links_back(raw: dict[str, pd.DataFrame]) -> None:
    assert raw["remits"]["claim_id"].isin(raw["claims"]["claim_id"]).all()
    adj = raw["remit_adjustments"]
    assert adj["remit_id"].isin(raw["remits"]["remit_id"]).all()
    assert adj["claim_line_id"].isin(raw["claim_lines"]["claim_line_id"]).all()
