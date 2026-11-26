"""Request and response shapes. Requests reject unknown fields, so no outcome column
(paid_amount, is_denied, carc_code, ...) can be sent in as a feature."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PayerType = Literal["commercial", "medicare", "medicare_advantage", "medicaid", "self_pay"]
Specialty = Literal[
    "family_medicine",
    "cardiology",
    "orthopedics",
    "gastroenterology",
    "ophthalmology",
    "physical_therapy",
]
PlaceOfService = Literal["11", "22", "24"]
Sex = Literal["F", "M", "U"]
State = Literal["MA", "NY", "NJ", "PA", "CT", "RI", "NH"]


class ClaimFeatures(BaseModel):
    """One claim as it looks on the day it is submitted."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str | None = Field(default=None, description="Echoed back; not used to score.")

    payer_id: str
    payer_type: PayerType
    provider_specialty: Specialty
    provider_state: State
    place_of_service: PlaceOfService
    primary_icd10: str
    primary_cpt_code: str
    patient_sex: Sex

    timely_filing_days: int = Field(gt=0)
    line_count: int = Field(ge=1)
    distinct_cpt_count: int = Field(ge=1)
    total_units: int = Field(ge=1)
    total_charge: float = Field(ge=0)
    max_line_charge: float = Field(ge=0)
    days_to_submit: int = Field(ge=0)
    share_of_timely_limit_used: float = Field(ge=0)
    patient_age_at_service: int = Field(ge=0, le=120)

    requires_prior_auth: bool
    prior_auth_obtained: bool
    missing_prior_auth: bool
    past_timely_filing_limit: bool
    has_z_code_dx: bool


class ScoreResponse(BaseModel):
    claim_id: str | None
    p_deny: float = Field(ge=0, le=1, description="Chance the first remit denies the claim.")
    recoverability: float = Field(description="1.0 for every claim until Step 11.")
    priority_score: float = Field(description="p_deny x total_charge x recoverability")
    model: str


class WorklistItem(BaseModel):
    rank: int
    claim_id: str
    submission_date: str
    payer_id: str
    payer_type: str
    provider_id: str
    provider_specialty: str
    primary_cpt_code: str
    total_charge: float
    p_deny: float
    recoverability: float
    priority_score: float


class WorklistResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[WorklistItem]


class HealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    model_loaded: bool
    model: str | None
    worklist_rows: int
