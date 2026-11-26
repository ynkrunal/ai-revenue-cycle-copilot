"""Top-level entry point: one seed in, a full set of linked tables out."""

import numpy as np
import pandas as pd

from rcm.generator.claims import make_claims
from rcm.generator.config import GeneratorConfig
from rcm.generator.entities import make_patients, make_payers, make_providers
from rcm.generator.schema import SCHEMAS


def generate(config: GeneratorConfig) -> dict[str, pd.DataFrame]:
    """Build payers, providers, patients, claims and claim lines from a single seed.

    Every random draw comes from one ``numpy`` generator in a fixed order, so the
    same config always gives identical tables.
    """
    rng = np.random.default_rng(config.seed)
    payers = make_payers()
    providers = make_providers(rng, config.n_providers)
    patients = make_patients(rng, config.patient_count, payers, config.start_date.year)
    claims, claim_lines = make_claims(rng, config, patients, providers)

    tables = {
        "payers": payers,
        "providers": providers,
        "patients": patients,
        "claims": claims,
        "claim_lines": claim_lines,
    }
    return {name: tables[name][list(columns)] for name, columns in SCHEMAS.items()}
