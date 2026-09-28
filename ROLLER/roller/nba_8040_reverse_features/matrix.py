"""Predictive matrix builder. Labels and event_path are not importable here."""

from __future__ import annotations

import numpy as np
import pandas as pd

from roller.nba_8040_reverse_features.catalog import matrix_specs
from roller.nba_8040_reverse_features.errors import ReverseFeaturesError
from roller.nba_8040_reverse_features.leakage import assert_predictive_columns

STATUS_OK = "OBSERVED"


def predictive_frame(features: pd.DataFrame, names: list[str] | None = None) -> pd.DataFrame:
    specs = matrix_specs()
    wanted = [spec.name for spec in specs] if names is None else list(names)
    allowed = {spec.name for spec in specs}
    unknown = [name for name in wanted if name not in allowed]
    if unknown:
        raise ReverseFeaturesError("LEAKAGE", f"matrix requested unregistered {unknown}")
    assert_predictive_columns(wanted)
    missing = [name for name in wanted if name not in features.columns]
    if missing:
        raise ReverseFeaturesError("DATA_REQUIRED", f"features missing {missing}")
    return features.loc[:, wanted].copy()


def complete_mask(features: pd.DataFrame, names: list[str]) -> pd.Series:
    mask = pd.Series(True, index=features.index)
    for name in names:
        status = features.get(f"{name}__status")
        if status is not None:
            mask &= status.eq(STATUS_OK)
        mask &= features[name].notna()
    return mask


def coverage_names(
    features: pd.DataFrame,
    names: list[str] | None = None,
    *,
    min_frac: float = 0.90,
) -> list[str]:
    wanted = names or [spec.name for spec in matrix_specs()]
    assert_predictive_columns(wanted)
    out: list[str] = []
    for name in wanted:
        if name not in features.columns:
            raise ReverseFeaturesError("DATA_REQUIRED", f"features missing {name}")
        frac = float(complete_mask(features, [name]).mean())
        if frac >= min_frac:
            out.append(name)
    if not out:
        raise ReverseFeaturesError(
            "DATA_REQUIRED", f"no matrix features meet coverage {min_frac}"
        )
    return out


def standardized_matrix(features: pd.DataFrame, names: list[str]) -> tuple[np.ndarray, list[str], pd.Index]:
    assert_predictive_columns(names)
    keep = complete_mask(features, names)
    block = features.loc[keep, names].astype(float)
    if block.empty:
        raise ReverseFeaturesError("DATA_REQUIRED", "no complete rows for matrix")
    values = block.to_numpy(dtype=float)
    mean = values.mean(axis=0)
    std = values.std(axis=0, ddof=0)
    std = np.where(std < 1e-12, 1.0, std)
    return (values - mean) / std, names, block.index
