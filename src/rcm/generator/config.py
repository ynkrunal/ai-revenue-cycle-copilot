"""Generator settings."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class GeneratorConfig:
    """How much synthetic data to make, and from which seed.

    The same config (including the seed) always produces identical tables.
    """

    seed: int = 42
    n_claims: int = 100_000
    months: int = 18
    start_date: date = date(2025, 1, 1)
    n_providers: int = 200
    n_patients: int | None = None  # default: one patient per 4 claims

    def __post_init__(self) -> None:
        for name in ("n_claims", "months", "n_providers"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be at least 1")
        if self.n_patients is not None and self.n_patients < 1:
            raise ValueError("n_patients must be at least 1")

    @property
    def patient_count(self) -> int:
        return self.n_patients if self.n_patients is not None else max(1, self.n_claims // 4)
