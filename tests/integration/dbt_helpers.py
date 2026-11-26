"""Shared helpers for tests that run a real `dbt build`."""

import os
import subprocess
import sys
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[2]
DBT_PROJECT = REPO / "dbt"
DBT_BIN = str(Path(sys.executable).parent / "dbt")


def run_dbt_build(
    raw_dir: Path, work: Path, project_dir: Path = DBT_PROJECT
) -> subprocess.CompletedProcess[str]:
    """Build the project against `raw_dir`, keeping every output inside `work`."""
    env = {
        **os.environ,
        "RCM_RAW_DIR": str(raw_dir),
        "RCM_DUCKDB_PATH": str(work / "rcm.duckdb"),
        "DBT_TARGET_PATH": str(work / "target"),
        "DBT_LOG_PATH": str(work / "logs"),
    }
    return subprocess.run(
        [DBT_BIN, "build", "--project-dir", str(project_dir), "--profiles-dir", str(project_dir)],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )


def query(db: Path, sql: str) -> list[tuple]:
    with duckdb.connect(str(db), read_only=True) as con:
        return con.execute(sql).fetchall()
