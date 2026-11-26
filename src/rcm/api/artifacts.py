"""Load the Step 6 outputs (model, worklist) once, at startup."""

import os
from dataclasses import dataclass
from pathlib import Path

import joblib
import pandas as pd
from sklearn.pipeline import Pipeline

from rcm.models.train import MODEL_NAME

ARTIFACTS_ENV = "RCM_ARTIFACTS_DIR"
DEFAULT_ARTIFACTS_DIR = "models/artifacts"
TEXT_COLUMNS = ["claim_id", "submission_date", "payer_id", "payer_type", "provider_id",
                "provider_specialty", "primary_cpt_code"]  # fmt: skip


def resolve_artifacts_dir(given: Path | None = None) -> Path:
    return Path(given or os.environ.get(ARTIFACTS_ENV) or DEFAULT_ARTIFACTS_DIR)


@dataclass
class Artifacts:
    model: Pipeline | None
    worklist: pd.DataFrame | None
    model_name: str = MODEL_NAME

    @property
    def ready(self) -> bool:
        return self.model is not None and self.worklist is not None


def load_artifacts(directory: Path) -> Artifacts:
    """Missing files are not an error here: /health reports them and the API returns 503."""
    model_path = directory / f"{MODEL_NAME}.joblib"
    worklist_path = directory / "worklist.csv"
    model = joblib.load(model_path) if model_path.is_file() else None
    worklist = None
    if worklist_path.is_file():
        worklist = pd.read_csv(worklist_path, dtype=dict.fromkeys(TEXT_COLUMNS, str))
        worklist = worklist.sort_values("rank", kind="stable").reset_index(drop=True)
    return Artifacts(model=model, worklist=worklist)
