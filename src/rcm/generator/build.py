"""Top-level entry point: one seed in, a full set of linked tables out."""

import numpy as np
import pandas as pd

from rcm.generator.claims import make_claims
from rcm.generator.config import GeneratorConfig
from rcm.generator.entities import make_patients, make_payers, make_providers
from rcm.generator.remits import make_remits
from rcm.generator.schema import SCHEMAS


def generate(config: GeneratorConfig) -> dict[str, pd.DataFrame]:
    """Build payers, providers, patients, claims, claim lines and remits from one seed.

    Every random draw comes from one ``numpy`` generator in a fixed order, so the
    same config always gives identical tables.
    """
    rng = np.random.default_rng(config.seed)
    payers = make_payers()
    providers = make_providers(rng, config.n_providers)
    patients = make_patients(rng, config.patient_count, payers, config.start_date.year)
    claims, claim_lines = make_claims(rng, config, patients, providers)
    remits, remit_adjustments = make_remits(rng, claims, claim_lines, payers)

    tables = {
        "payers": payers,
        "providers": providers,
        "patients": patients,
        "claims": claims,
        "claim_lines": claim_lines,
        "remits": remits,
        "remit_adjustments": remit_adjustments,
    }
    return {name: tables[name][list(columns)] for name, columns in SCHEMAS.items()}
