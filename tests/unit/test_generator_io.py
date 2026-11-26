"""Parquet output and the command-line tool."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from rcm.generator import GeneratorConfig, generate
from rcm.generator.__main__ import main
from rcm.generator.io import read_tables, resolve_out_dir, write_tables
from rcm.generator.schema import SCHEMAS


def test_write_then_read_round_trips(tmp_path: Path) -> None:
    tables = generate(GeneratorConfig(seed=3, n_claims=500, months=3))
    paths = write_tables(tables, tmp_path)
    assert sorted(p.name for p in paths) == sorted(f"{t}.parquet" for t in SCHEMAS)
    back = read_tables(tmp_path)
    for name in SCHEMAS:
        pd.testing.assert_frame_equal(back[name], tables[name], check_dtype=False)


def test_out_dir_uses_env_var_then_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RCM_RAW_DIR", raising=False)
    assert resolve_out_dir(None) == Path("data/raw")
    monkeypatch.setenv("RCM_RAW_DIR", "/tmp/elsewhere")
    assert resolve_out_dir(None) == Path("/tmp/elsewhere")
    assert resolve_out_dir("given") == Path("given")


def test_cli_writes_parquet_and_reports(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    out = tmp_path / "raw"
    code = main(
        [
            "--seed",
            "5",
            "--claims",
            "800",
            "--months",
            "4",
            "--start-date",
            "2025-03-01",
            "--out",
            str(out),
        ]
    )
    assert code == 0
    back = read_tables(out)
    assert len(back["claims"]) == 800
    assert back["claims"]["service_date"].min() >= pd.Timestamp(date(2025, 3, 1))
    printed = capsys.readouterr().out
    assert "denial rate" in printed.lower()
    assert str(out) in printed


def test_cli_output_matches_library_for_same_seed(tmp_path: Path) -> None:
    main(["--seed", "9", "--claims", "300", "--months", "2", "--out", str(tmp_path)])
    expected = generate(GeneratorConfig(seed=9, n_claims=300, months=2))
    back = read_tables(tmp_path)
    pd.testing.assert_frame_equal(back["remits"], expected["remits"], check_dtype=False)


def test_cli_rejects_bad_arguments(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(["--claims", "0", "--out", str(tmp_path)])
