"""Remits (835-like): the payer's answer to each claim, with CARC/RARC adjustments.

Each claim gets one first remit. Denials come from planted drivers (missing prior
auth, late submission, diagnosis/procedure mismatch, strict payers) plus random
background noise. One claim has at most one denial reason; when several drivers
fire, the order is: late submission, missing auth, dx mismatch, noise.
"""

import numpy as np
import pandas as pd

from rcm.generator import reference as ref
from rcm.generator.entities import synthetic_ids

NOISE_WHOLE_CLAIM_RATE = 0.6  # otherwise a noise denial hits one random line
DEDUCTIBLE_MONTHS = (1, 2, 3)  # deductibles reset in January
DEDUCTIBLE_RATE = 0.5


def make_remits(
    rng: np.random.Generator,
    claims: pd.DataFrame,
    lines: pd.DataFrame,
    payers: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    n = len(claims)
    pos = pd.Index(claims["claim_id"]).get_indexer(lines["claim_id"])  # line -> claim row

    payer = payers.set_index("payer_id")
    payer_type = claims["payer_id"].map(payer["payer_type"]).to_numpy()
    terms = {field: _per_claim(payer_type, field) for field in ref.PayerTerms._fields}
    timely_limit = claims["payer_id"].map(payer["timely_filing_days"]).to_numpy()
    lag = (claims["submission_date"] - claims["service_date"]).dt.days.to_numpy()

    cpt = lines["cpt_code"].to_numpy()
    icd = lines["icd10_code"].to_numpy()
    auth_line = np.isin(cpt, list(ref.AUTH_REQUIRED_CPT))
    mismatch_line = np.zeros(len(lines), dtype=bool)
    for dx, cpts in ref.DX_PROCEDURE_MISMATCH.items():
        mismatch_line |= (icd == dx) & np.isin(cpt, list(cpts))

    # Which cause (if any) fires for each claim. All draws happen up front, in a fixed order.
    p = ref.DRIVER_DENIAL_PROB
    late = lag > timely_limit
    missing_auth = (
        claims["requires_prior_auth"].to_numpy() & ~claims["prior_auth_obtained"].to_numpy()
    )
    mismatch = np.bincount(pos, weights=mismatch_line, minlength=n) > 0
    fire_late = late & (rng.random(n) < p["late_submission"])
    fire_auth = missing_auth & (rng.random(n) < p["missing_prior_auth"])
    fire_dx = mismatch & (rng.random(n) < p["dx_procedure_mismatch"])
    fire_noise = rng.random(n) < terms["noise_denial_rate"]
    noise_codes = list(ref.NOISE_DENIAL_WEIGHTS)
    noise_w = np.array(list(ref.NOISE_DENIAL_WEIGHTS.values()))
    noise_carc = rng.choice(noise_codes, size=n, p=noise_w / noise_w.sum())
    noise_whole = rng.random(n) < NOISE_WHOLE_CLAIM_RATE
    line_count = claims["line_count"].to_numpy()
    noise_line = 1 + np.floor(rng.random(n) * line_count).astype(int)

    cause = np.select(
        [fire_late, fire_auth, fire_dx, fire_noise], ["late", "auth", "dx", "noise"], "none"
    )

    # Spread the claim's cause onto its lines.
    line_cause = cause[pos]
    line_no = lines["line_number"].to_numpy()
    noise_hits_line = noise_whole[pos] | (line_no == noise_line[pos])
    denial_carc = np.select(
        [
            line_cause == "late",
            (line_cause == "auth") & auth_line,
            (line_cause == "dx") & mismatch_line,
            (line_cause == "noise") & noise_hits_line,
        ],
        ["29", "197", "11", noise_carc[pos]],
        "",
    )
    denied = denial_carc != ""

    # Money on lines the payer accepted.
    charge = lines["line_charge"].to_numpy()
    ratio = np.minimum(terms["allowed_ratio"][pos] * rng.lognormal(0.0, 0.05, len(lines)), 1.0)
    allowed = np.where(denied, 0.0, np.round(charge * ratio, 2))
    patient = np.round(allowed * terms["patient_share"][pos], 2)
    paid = np.round(allowed - patient, 2)
    contractual = np.where(denied, 0.0, np.round(charge - allowed, 2))
    service_month = claims["service_date"].dt.month.to_numpy()[pos]
    deductible = np.isin(service_month, DEDUCTIBLE_MONTHS) & (
        rng.random(len(lines)) < DEDUCTIBLE_RATE
    )
    patient_carc = np.where(deductible, "1", "2")

    # Remit headers.
    remit_id = synthetic_ids("RMT", n, 7)
    denied_lines = np.bincount(pos, weights=denied, minlength=n)
    status = np.where(
        denied_lines == 0,
        "paid",
        np.where(denied_lines == line_count, "denied", "partially_denied"),
    )
    adjudication = claims["submission_date"] + pd.to_timedelta(
        rng.integers(ref.MIN_ADJUDICATION_DAYS, ref.MAX_ADJUDICATION_DAYS + 1, size=n), unit="D"
    )
    remits = pd.DataFrame(
        {
            "remit_id": remit_id,
            "claim_id": claims["claim_id"].to_numpy(),
            "adjudication_date": adjudication.to_numpy(),
            "claim_status": status,
            "allowed_amount": _claim_sum(pos, allowed, n),
            "paid_amount": _claim_sum(pos, paid, n),
            "patient_responsibility": _claim_sum(pos, patient, n),
        }
    ).astype({"claim_id": "str", "claim_status": "str"})

    # Adjustment rows (CAS segments): denial, contractual (CO-45), patient share (PR-1/2).
    line_remit = remit_id.to_numpy()[pos]
    line_id = lines["claim_line_id"].to_numpy()
    parts = [
        _adjustments(denied, 0, line_remit, line_id, "CO", denial_carc, charge),
        _adjustments(~denied & (contractual > 0), 1, line_remit, line_id, "CO", "45", contractual),
        _adjustments(~denied & (patient > 0), 2, line_remit, line_id, "PR", patient_carc, patient),
    ]
    adj = pd.concat(parts, ignore_index=True).sort_values(["_line", "_kind"], kind="stable")
    adj = adj.drop(columns=["_line", "_kind"]).reset_index(drop=True)
    adj.insert(0, "adjustment_id", synthetic_ids("ADJ", len(adj), 8))
    rarc = [ref.CARC_CODES[c].rarc for c in adj["carc_code"]]
    adj.insert(5, "rarc_code", pd.Series(rarc, dtype="str"))
    return remits, adj


def _per_claim(payer_type: np.ndarray, field: str) -> np.ndarray:
    lookup = {k: getattr(v, field) for k, v in ref.PAYER_TERMS.items()}
    return np.array([lookup[t] for t in payer_type], dtype=float)


def _claim_sum(pos: np.ndarray, values: np.ndarray, n: int) -> np.ndarray:
    return np.round(np.bincount(pos, weights=values, minlength=n), 2)


def _adjustments(
    mask: np.ndarray,
    kind: int,
    remit_ids: np.ndarray,
    line_ids: np.ndarray,
    group: str,
    carc: np.ndarray | str,
    amount: np.ndarray,
) -> pd.DataFrame:
    idx = np.flatnonzero(mask)
    carc_values = np.broadcast_to(np.asarray(carc, dtype=object), mask.shape)[idx]
    return pd.DataFrame(
        {
            "remit_id": pd.Series(remit_ids[idx], dtype="str"),
            "claim_line_id": pd.Series(line_ids[idx], dtype="str"),
            "group_code": pd.Series([group] * len(idx), dtype="str"),
            "carc_code": pd.Series(carc_values, dtype="str"),
            "adjustment_amount": amount[idx].astype(float),
            "_line": idx,
            "_kind": kind,
        }
    )
