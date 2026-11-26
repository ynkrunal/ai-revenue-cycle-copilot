"""Claim headers and claim lines (837-like). No remits or denials here: that is Step 3."""

import numpy as np
import pandas as pd

from rcm.generator import reference as ref
from rcm.generator.config import GeneratorConfig
from rcm.generator.entities import synthetic_ids

PRIOR_AUTH_OBTAINED_RATE = 0.88
PRIMARY_ICD_REUSE_RATE = 0.7


def make_claims(
    rng: np.random.Generator,
    config: GeneratorConfig,
    patients: pd.DataFrame,
    providers: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    n = config.n_claims

    # Who: some patients and providers are much busier than others.
    patient_idx = rng.choice(len(patients), size=n, p=_skewed_weights(rng, len(patients)))
    provider_idx = rng.choice(len(providers), size=n, p=_skewed_weights(rng, len(providers)))
    specialty = providers["specialty"].to_numpy()[provider_idx]

    # When: service dates spread evenly over the window; most claims go out within a week.
    start = pd.Timestamp(config.start_date)
    window_days = ((start + pd.DateOffset(months=config.months)) - start).days
    service_date = start + pd.to_timedelta(rng.integers(0, window_days, size=n), unit="D")
    service_date = pd.Series(service_date)
    submission_date = service_date + pd.to_timedelta(_submission_lags(rng, n), unit="D")

    # What: claim lines.
    line_count = rng.choice(
        np.arange(1, ref.MAX_LINES_PER_CLAIM + 1), size=n, p=ref.LINE_COUNT_PROBS
    ).astype("int64")
    claim_idx = np.repeat(np.arange(n), line_count)
    line_starts = np.repeat(np.cumsum(line_count) - line_count, line_count)
    line_number = (np.arange(len(claim_idx)) - line_starts + 1).astype("int64")

    line_specialty = specialty[claim_idx]
    cpt = _pick_by_specialty(rng, line_specialty, ref.SPECIALTY_CPT, cpt_weights=True)
    primary_icd = _pick_by_specialty(rng, specialty, ref.SPECIALTY_ICD10)
    other_icd = _pick_by_specialty(rng, line_specialty, ref.SPECIALTY_ICD10)
    reuse = (line_number == 1) | (rng.random(len(claim_idx)) < PRIMARY_ICD_REUSE_RATE)
    icd = np.where(reuse, primary_icd[claim_idx], other_icd)

    max_units = np.array([ref.CPT_CODES[c].max_units for c in cpt])
    units = (1 + np.floor(rng.random(len(cpt)) * max_units)).astype("int64")
    base = np.array([ref.CPT_CODES[c].base_charge for c in cpt])
    line_charge = np.round(base * units * rng.lognormal(0.0, 0.15, size=len(cpt)), 2)
    total_charge = np.round(np.bincount(claim_idx, weights=line_charge, minlength=n), 2)

    # Claim-level flags derived from the lines.
    requires_auth = np.bincount(claim_idx, weights=np.isin(cpt, list(ref.AUTH_REQUIRED_CPT)))
    requires_auth = requires_auth.astype(bool)
    auth_obtained = requires_auth & (rng.random(n) < PRIOR_AUTH_OBTAINED_RATE)
    has_facility = np.bincount(claim_idx, weights=np.isin(cpt, list(ref.FACILITY_CPT))) > 0
    place_of_service = np.where(
        has_facility,
        np.where(rng.random(n) < 0.6, "24", "22"),
        np.where(rng.random(n) < 0.92, "11", "22"),
    )

    claim_id = synthetic_ids("CLM", n, 7)
    claims = pd.DataFrame(
        {
            "claim_id": claim_id,
            "patient_id": patients["patient_id"].to_numpy()[patient_idx],
            "provider_id": providers["provider_id"].to_numpy()[provider_idx],
            "payer_id": patients["payer_id"].to_numpy()[patient_idx],
            "service_date": service_date,
            "submission_date": submission_date,
            "place_of_service": place_of_service,
            "primary_icd10": primary_icd,
            "requires_prior_auth": requires_auth,
            "prior_auth_obtained": auth_obtained,
            "line_count": line_count,
            "total_charge": total_charge,
        }
    )
    line_claim_id = claim_id.to_numpy()[claim_idx]
    lines = pd.DataFrame(
        {
            "claim_line_id": [
                f"{c}-L{k:02d}" for c, k in zip(line_claim_id, line_number, strict=True)
            ],
            "claim_id": line_claim_id,
            "line_number": line_number,
            "cpt_code": cpt,
            "icd10_code": icd,
            "units": units,
            "line_charge": line_charge,
        }
    )
    string_cols = ["patient_id", "provider_id", "payer_id", "place_of_service", "primary_icd10"]
    claims = claims.astype(dict.fromkeys(string_cols, "str"))
    lines = lines.astype(
        dict.fromkeys(["claim_line_id", "claim_id", "cpt_code", "icd10_code"], "str")
    )
    return claims, lines


def _skewed_weights(rng: np.random.Generator, count: int) -> np.ndarray:
    weights = rng.gamma(shape=1.5, scale=1.0, size=count)
    return weights / weights.sum()


def _submission_lags(rng: np.random.Generator, n: int) -> np.ndarray:
    """Days from service to submission: usually under a week, with a long late tail."""
    typical = rng.geometric(1 / 6, size=n) - 1
    late = rng.integers(30, ref.MAX_SUBMISSION_LAG_DAYS + 1, size=n)
    lag = np.where(rng.random(n) < 0.05, late, typical)
    return np.minimum(lag, ref.MAX_SUBMISSION_LAG_DAYS)


def _pick_by_specialty(
    rng: np.random.Generator,
    specialties: np.ndarray,
    options: dict[str, tuple[str, ...]],
    *,
    cpt_weights: bool = False,
) -> np.ndarray:
    out = np.empty(len(specialties), dtype=object)
    for name, codes in options.items():
        mask = specialties == name
        if not mask.any():
            continue
        if cpt_weights:
            w = np.array([ref.CPT_CODES[c].weight for c in codes])
            p = w / w.sum()
        else:
            p = None
        out[mask] = rng.choice(codes, size=int(mask.sum()), p=p)
    return out
