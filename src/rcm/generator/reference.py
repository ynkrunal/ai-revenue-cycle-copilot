"""Static reference data: payers, specialties, CPT and ICD-10 codes.

CPT and ICD-10 codes are public billing codes, not patient data. Charges are
made-up list prices, not any real fee schedule. Payer and provider names are
fictional and always start with "Synthetic".
"""

from typing import NamedTuple


class Cpt(NamedTuple):
    description: str
    base_charge: float  # list price for one unit
    max_units: int
    weight: float  # how often it is billed, relative to others in a specialty


CPT_CODES: dict[str, Cpt] = {
    "99203": Cpt("Office visit, new patient, level 3", 180.0, 1, 4.0),
    "99213": Cpt("Office visit, established patient, level 3", 130.0, 1, 6.0),
    "99214": Cpt("Office visit, established patient, level 4", 190.0, 1, 5.0),
    "93000": Cpt("Electrocardiogram, complete", 60.0, 1, 2.0),
    "80053": Cpt("Comprehensive metabolic panel", 45.0, 1, 3.0),
    "85025": Cpt("Complete blood count with differential", 30.0, 1, 3.0),
    "71046": Cpt("Chest X-ray, 2 views", 120.0, 1, 1.5),
    "73721": Cpt("MRI lower extremity joint, without contrast", 1400.0, 1, 1.0),
    "78452": Cpt("Myocardial perfusion imaging, multiple studies", 1800.0, 1, 1.0),
    "20610": Cpt("Arthrocentesis or injection, major joint", 250.0, 1, 1.5),
    "97161": Cpt("Physical therapy evaluation, low complexity", 150.0, 1, 1.5),
    "97110": Cpt("Therapeutic exercise, each 15 minutes", 45.0, 4, 5.0),
    "97140": Cpt("Manual therapy, each 15 minutes", 45.0, 4, 3.0),
    "45378": Cpt("Colonoscopy, diagnostic", 1600.0, 1, 1.5),
    "66984": Cpt("Cataract removal with lens implant", 2800.0, 1, 1.0),
    "92014": Cpt("Eye exam, established patient, comprehensive", 160.0, 1, 4.0),
}

# High-cost services that payers usually require prior authorization for.
AUTH_REQUIRED_CPT: frozenset[str] = frozenset({"73721", "78452", "45378", "66984"})

# Services normally done in a facility rather than an office.
FACILITY_CPT: frozenset[str] = frozenset({"45378", "66984"})

ICD10_CODES: dict[str, str] = {
    "Z00.00": "General adult medical exam without abnormal findings",
    "I10": "Essential (primary) hypertension",
    "E11.9": "Type 2 diabetes mellitus without complications",
    "E78.5": "Hyperlipidemia, unspecified",
    "J06.9": "Acute upper respiratory infection, unspecified",
    "R07.9": "Chest pain, unspecified",
    "I25.10": "Atherosclerotic heart disease without angina",
    "I48.91": "Unspecified atrial fibrillation",
    "M17.11": "Primary osteoarthritis, right knee",
    "M25.561": "Pain in right knee",
    "M54.50": "Low back pain, unspecified",
    "S83.241A": "Medial meniscus tear, right knee, initial encounter",
    "K21.9": "Gastro-esophageal reflux disease without esophagitis",
    "K57.30": "Diverticulosis of large intestine without bleeding",
    "Z12.11": "Encounter for screening for malignant neoplasm of colon",
    "H25.11": "Age-related nuclear cataract, right eye",
    "H40.11X0": "Primary open-angle glaucoma, stage unspecified",
    "H52.4": "Presbyopia",
}

SPECIALTY_CPT: dict[str, tuple[str, ...]] = {
    "family_medicine": ("99203", "99213", "99214", "93000", "80053", "85025", "71046"),
    "cardiology": ("99203", "99214", "93000", "78452", "71046"),
    "orthopedics": ("99203", "99213", "73721", "20610", "97110"),
    "gastroenterology": ("99203", "99214", "45378", "80053", "85025"),
    "ophthalmology": ("99203", "92014", "66984"),
    "physical_therapy": ("97161", "97110", "97140"),
}

SPECIALTY_ICD10: dict[str, tuple[str, ...]] = {
    "family_medicine": ("Z00.00", "I10", "E11.9", "E78.5", "J06.9", "M54.50"),
    "cardiology": ("R07.9", "I10", "I25.10", "I48.91", "E78.5"),
    "orthopedics": ("M17.11", "M25.561", "M54.50", "S83.241A"),
    "gastroenterology": ("K21.9", "K57.30", "Z12.11"),
    "ophthalmology": ("H25.11", "H40.11X0", "H52.4"),
    "physical_therapy": ("M54.50", "M25.561", "M17.11"),
}

# Share of providers in each specialty.
SPECIALTY_MIX: dict[str, float] = {
    "family_medicine": 0.35,
    "cardiology": 0.12,
    "orthopedics": 0.15,
    "gastroenterology": 0.10,
    "ophthalmology": 0.10,
    "physical_therapy": 0.18,
}

PLACES_OF_SERVICE: dict[str, str] = {
    "11": "Office",
    "22": "On-campus outpatient hospital",
    "24": "Ambulatory surgical center",
}


class Payer(NamedTuple):
    name: str
    payer_type: str
    timely_filing_days: int
    market_share: float


PAYERS: tuple[Payer, ...] = (
    Payer("Synthetic Commercial Alpha", "commercial", 90, 0.18),
    Payer("Synthetic Commercial Beta", "commercial", 180, 0.14),
    Payer("Synthetic Commercial Gamma", "commercial", 365, 0.10),
    Payer("Synthetic Commercial Delta", "commercial", 90, 0.08),
    Payer("Synthetic Medicare", "medicare", 365, 0.20),
    Payer("Synthetic Medicare Advantage North", "medicare_advantage", 90, 0.10),
    Payer("Synthetic Medicare Advantage South", "medicare_advantage", 180, 0.06),
    Payer("Synthetic Medicaid State A", "medicaid", 180, 0.08),
    Payer("Synthetic Medicaid State B", "medicaid", 90, 0.04),
    Payer("Synthetic Self-Pay", "self_pay", 365, 0.02),
)

PAYER_TYPES: frozenset[str] = frozenset(p.payer_type for p in PAYERS)
MEDICARE_TYPES: frozenset[str] = frozenset({"medicare", "medicare_advantage"})

SEXES: frozenset[str] = frozenset({"F", "M", "U"})
STATES: tuple[str, ...] = ("MA", "NY", "NJ", "PA", "CT", "RI", "NH")

MAX_LINES_PER_CLAIM = 4
LINE_COUNT_PROBS: tuple[float, ...] = (0.45, 0.30, 0.17, 0.08)  # 1, 2, 3, 4 lines
MAX_SUBMISSION_LAG_DAYS = 120

# ---------------------------------------------------------------------------
# Remits (835-like): adjudication outcomes. Used only to build labels, never as
# model features.
# ---------------------------------------------------------------------------


class Carc(NamedTuple):
    description: str
    rarc: str | None  # remark code sent with this CARC, if any


CARC_CODES: dict[str, Carc] = {
    # Denials
    "197": Carc("Precertification/authorization/notification absent", "M62"),
    "29": Carc("The time limit for filing has expired", None),
    "11": Carc("The diagnosis is inconsistent with the procedure", "M76"),
    "16": Carc("Claim/service lacks information or has submission/billing error(s)", "MA130"),
    "27": Carc("Expenses incurred after coverage terminated", "N30"),
    "50": Carc("Non-covered: not deemed a medical necessity by the payer", "N130"),
    "18": Carc("Exact duplicate claim/service", None),
    "96": Carc("Non-covered charge(s)", "N130"),
    # Normal adjustments on paid lines (not denials)
    "45": Carc("Charge exceeds fee schedule/maximum allowable", None),
    "1": Carc("Deductible amount", None),
    "2": Carc("Coinsurance amount", None),
}

DENIAL_CARC: frozenset[str] = frozenset({"197", "29", "11", "16", "27", "50", "18", "96"})
PATIENT_RESPONSIBILITY_CARC: frozenset[str] = frozenset({"1", "2"})
RARC_CODES: frozenset[str] = frozenset(c.rarc for c in CARC_CODES.values() if c.rarc)
GROUP_CODES: frozenset[str] = frozenset({"CO", "PR"})
CLAIM_STATUSES: frozenset[str] = frozenset({"paid", "partially_denied", "denied"})

# Random "background" denials that no submission-time field explains, by weight.
NOISE_DENIAL_WEIGHTS: dict[str, float] = {
    "16": 0.35,
    "27": 0.20,
    "50": 0.20,
    "18": 0.15,
    "96": 0.10,
}
NOISE_DENIAL_CARC: frozenset[str] = frozenset(NOISE_DENIAL_WEIGHTS)

# Denial drivers planted in the data (all knowable at submission time):
#   missing prior auth  -> CARC 197 on the auth-required lines
#   late submission     -> CARC 29 on the whole claim (lag > payer timely-filing limit)
#   dx/procedure clash  -> CARC 11 on the mismatched lines
#   strict payer type   -> higher background denial rate
DRIVER_DENIAL_PROB: dict[str, float] = {
    "late_submission": 0.95,
    "missing_prior_auth": 0.80,
    "dx_procedure_mismatch": 0.50,
}

# A wellness or screening diagnosis billed with a problem-focused or diagnostic service.
DX_PROCEDURE_MISMATCH: dict[str, frozenset[str]] = {
    "Z00.00": frozenset({"99213", "99214"}),
    "Z12.11": frozenset({"45378"}),
}

STRICT_PAYER_TYPES: frozenset[str] = frozenset({"medicaid", "medicare_advantage"})


class PayerTerms(NamedTuple):
    noise_denial_rate: float  # background denial probability
    allowed_ratio: float  # allowed amount as a share of billed charge
    patient_share: float  # share of allowed amount the patient owes


PAYER_TERMS: dict[str, PayerTerms] = {
    "commercial": PayerTerms(0.050, 0.55, 0.20),
    "medicare": PayerTerms(0.035, 0.40, 0.20),
    "medicare_advantage": PayerTerms(0.120, 0.42, 0.10),
    "medicaid": PayerTerms(0.130, 0.32, 0.02),
    "self_pay": PayerTerms(0.020, 0.60, 1.00),  # the patient owes all of it
}

MIN_ADJUDICATION_DAYS = 7
MAX_ADJUDICATION_DAYS = 45
