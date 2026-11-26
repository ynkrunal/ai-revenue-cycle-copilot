"""Baseline: one-hot categories + scaled log numbers + flags -> logistic regression."""

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from rcm.models.features import BOOLEAN, CATEGORICAL, NUMERIC


def _as_float(x):  # module-level so the fitted pipeline can be pickled
    return np.asarray(x, dtype=float)


def build_baseline() -> Pipeline:
    prep = ColumnTransformer(
        [
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
            (
                "num",
                Pipeline(
                    [
                        # Raw DuckDB rows carry money as Decimal; make everything float first.
                        ("float", FunctionTransformer(_as_float, feature_names_out="one-to-one")),
                        ("log", FunctionTransformer(np.log1p, feature_names_out="one-to-one")),
                        ("scale", StandardScaler()),
                    ]
                ),
                NUMERIC,
            ),
            ("bool", FunctionTransformer(_as_float, feature_names_out="one-to-one"), BOOLEAN),
        ],
        remainder="drop",
    )
    return Pipeline([("prep", prep), ("clf", LogisticRegression(C=1.0, max_iter=2_000))])
