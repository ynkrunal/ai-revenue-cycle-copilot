"""Payers, providers and synthetic patients."""

import numpy as np
import pandas as pd

from rcm.generator import reference as ref


def synthetic_ids(prefix: str, count: int, width: int) -> pd.Series:
    """IDs like SYN-MRN-000123: an obvious synthetic prefix, never a bare number."""
    return pd.Series([f"SYN-{prefix}-{i:0{width}d}" for i in range(1, count + 1)], dtype="str")


def make_payers() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "payer_id": synthetic_ids("PAY", len(ref.PAYERS), 4),
            "payer_name": [p.name for p in ref.PAYERS],
            "payer_type": [p.payer_type for p in ref.PAYERS],
            "timely_filing_days": np.array([p.timely_filing_days for p in ref.PAYERS], "int64"),
        }
    )


def make_providers(rng: np.random.Generator, count: int) -> pd.DataFrame:
    specialties = list(ref.SPECIALTY_MIX)
    probs = np.array(list(ref.SPECIALTY_MIX.values()))
    return pd.DataFrame(
        {
            "provider_id": synthetic_ids("PRV", count, 5),
            "provider_name": [f"Synthetic Clinic {i:05d}" for i in range(1, count + 1)],
            "specialty": rng.choice(specialties, size=count, p=probs / probs.sum()),
            "state": rng.choice(ref.STATES, size=count),
        }
    ).astype({"specialty": "str", "state": "str"})


def make_patients(
    rng: np.random.Generator, count: int, payers: pd.DataFrame, as_of_year: int
) -> pd.DataFrame:
    """Patients carry only coarse attributes: no name, no full birth date, no SSN."""
    ages = np.clip(np.rint(rng.normal(48, 22, size=count)), 0, 95).astype("int64")

    share = np.array([p.market_share for p in ref.PAYERS])
    is_medicare = payers["payer_type"].isin(ref.MEDICARE_TYPES).to_numpy()
    senior_w = share * np.where(is_medicare, 8.0, 1.0)
    younger_w = share * np.where(is_medicare, 0.05, 1.0)

    payer_idx = np.where(
        ages >= 65,
        rng.choice(len(share), size=count, p=senior_w / senior_w.sum()),
        rng.choice(len(share), size=count, p=younger_w / younger_w.sum()),
    )
    return pd.DataFrame(
        {
            "patient_id": synthetic_ids("MRN", count, 6),
            "birth_year": as_of_year - ages,
            "sex": rng.choice(["F", "M", "U"], size=count, p=[0.52, 0.47, 0.01]),
            "state": rng.choice(ref.STATES, size=count),
            "payer_id": payers["payer_id"].to_numpy()[payer_idx],
        }
    ).astype({"sex": "str", "state": "str", "payer_id": "str"})
