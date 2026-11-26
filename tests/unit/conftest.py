"""Shared fixtures for unit tests."""

from datetime import date

import pandas as pd
import pytest

from rcm.generator import GeneratorConfig, generate

SMALL_CONFIG = GeneratorConfig(seed=7, n_claims=2_000, months=6, start_date=date(2025, 1, 1))


@pytest.fixture(scope="session")
def small_config() -> GeneratorConfig:
    return SMALL_CONFIG


@pytest.fixture(scope="session")
def tables() -> dict[str, pd.DataFrame]:
    return generate(SMALL_CONFIG)
