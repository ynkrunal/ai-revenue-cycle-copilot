"""Same seed -> identical output; different seed -> different output."""

from dataclasses import replace

import pandas as pd

from rcm.generator import GeneratorConfig, generate


def test_same_seed_gives_identical_tables(small_config: GeneratorConfig) -> None:
    first = generate(small_config)
    second = generate(small_config)
    for name in first:
        pd.testing.assert_frame_equal(first[name], second[name])


def test_different_seed_gives_different_claims(small_config: GeneratorConfig) -> None:
    first = generate(small_config)
    other = generate(replace(small_config, seed=small_config.seed + 1))
    assert not first["claims"].equals(other["claims"])
    assert not first["claim_lines"].equals(other["claim_lines"])
