"""Write and read the raw tables as Parquet (one file per table)."""

import os
from pathlib import Path

import pandas as pd

from rcm.generator.schema import SCHEMAS

DEFAULT_RAW_DIR = "data/raw"
RAW_DIR_ENV = "RCM_RAW_DIR"


def resolve_out_dir(cli_value: str | None) -> Path:
    """CLI flag first, then the RCM_RAW_DIR environment variable, then data/raw."""
    return Path(cli_value or os.environ.get(RAW_DIR_ENV) or DEFAULT_RAW_DIR)


def write_tables(tables: dict[str, pd.DataFrame], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in SCHEMAS:
        path = out_dir / f"{name}.parquet"
        tables[name].to_parquet(path, index=False)
        paths.append(path)
    return paths


def read_tables(raw_dir: Path) -> dict[str, pd.DataFrame]:
    return {name: pd.read_parquet(Path(raw_dir) / f"{name}.parquet") for name in SCHEMAS}
