"""PHASE 1 — inventory every existing column. Nothing silently disappears."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from roller.nba_8040_reverse_features.catalog import (
    FORBIDDEN_NAMES,
    LABEL_SPECS,
    PREDICTIVE_TIMING,
    spec_by_name,
)
from roller.nba_8040_reverse_features.deep_quant.classes import CLASS_LETTER
from roller.nba_8040_reverse_features.instances import load_instances
from roller.nba_8040_reverse_features.locks import (
    NBA_Q2_N,
    NBA_Q2_RS_N,
    NBA_Q2Q3_N,
    NBA_Q3_N,
)
from roller.nba_8040_reverse_features.errors import ReverseFeaturesError

IDENTITY = {
    "instance_id",
    "event_id",
    "game_id",
    "ticker",
    "period",
    "side",
    "home_team",
    "away_team",
    "bought_team",
    "season_phase",
    "dataset_split",
    "game_date",
    "timestamp_utc",
    "alignment_confidence",
}

UNAVAILABLE_PLACEHOLDERS = {
    "score_change_1m": "OPERATION_REQUIRED",
    "possession_team": "SOURCE_UNAVAILABLE",
}


def verify_population(features: pd.DataFrame, labels: pd.DataFrame) -> dict[str, int]:
    rows = load_instances()
    if len(rows) != NBA_Q2Q3_N:
        raise ReverseFeaturesError("LOCK_MISMATCH", f"load_instances N {len(rows)}")
    if len(features) != NBA_Q2Q3_N or len(labels) != NBA_Q2Q3_N:
        raise ReverseFeaturesError("LOCK_MISMATCH", "store N != 604")
    if features["instance_id"].nunique() != NBA_Q2Q3_N:
        raise ReverseFeaturesError("LOCK_MISMATCH", "instance_id not unique")
    if set(features["instance_id"]) != set(labels["instance_id"]):
        raise ReverseFeaturesError("LOCK_MISMATCH", "feature/label instance_id mismatch")
    q2 = int(features["period"].eq("Q2").sum())
    q3 = int(features["period"].eq("Q3").sum())
    if q2 != NBA_Q2_N or q3 != NBA_Q3_N:
        raise ReverseFeaturesError("LOCK_MISMATCH", f"Q2/Q3 {q2}/{q3}")
    rs = int((features["period"].eq("Q2") & features["regular_season"].eq(1.0)).sum())
    if rs != NBA_Q2_RS_N:
        raise ReverseFeaturesError("LOCK_MISMATCH", f"Q2 RS {rs}")
    return {
        "n": NBA_Q2Q3_N,
        "q2": q2,
        "q3": q3,
        "q2_regular_season": rs,
        "unique_instance_id": NBA_Q2Q3_N,
    }


def _missing_kind(name: str, status: str | None, missing_rate: float) -> str:
    if missing_rate <= 0:
        return "observed"
    if name in UNAVAILABLE_PLACEHOLDERS:
        return UNAVAILABLE_PLACEHOLDERS[name]
    if status == "SOURCE_UNAVAILABLE":
        return "source_unavailable"
    if status == "OPERATION_REQUIRED":
        return "operation_required"
    if name.startswith("accel_") or name.startswith("std_") or name.startswith("direction_changes_"):
        return "structurally_undefined_window_too_short"
    if any(name.startswith(prefix) for prefix in ("close_", "delta_", "velocity_", "min_", "max_", "range_")):
        return "window_did_not_exist"
    return "source_coverage_incomplete"


def inventory_rows(features: pd.DataFrame) -> list[dict[str, Any]]:
    specs = spec_by_name()
    labels = {spec.name: spec for spec in LABEL_SPECS}
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for column in features.columns:
        if column.endswith("__status"):
            continue
        seen.add(column)
        spec = specs.get(column)
        status_col = f"{column}__status"
        status_series = features[status_col] if status_col in features.columns else None
        observed_mask = status_series.eq("OBSERVED") if status_series is not None else features[column].notna()
        if spec is not None and spec.kind != "binary" and column in features and pd.api.types.is_numeric_dtype(features[column]):
            observed = features.loc[observed_mask, column]
        else:
            observed = features.loc[observed_mask, column] if column in features else pd.Series(dtype=float)
        n = int(len(features))
        avail = int(observed_mask.sum()) if hasattr(observed_mask, "sum") else int(observed.notna().sum())
        missing = n - avail
        numeric = bool(spec is not None or pd.api.types.is_numeric_dtype(features[column]))
        if column in IDENTITY:
            numeric = column in {"regular_season"}
        unique = int(features[column].nunique(dropna=True))
        variance = None
        if numeric and avail and pd.api.types.is_numeric_dtype(features[column]):
            arr = pd.to_numeric(observed, errors="coerce").dropna().to_numpy(dtype=float)
            if len(arr):
                variance = float(arr.var())
        timing = spec.timing if spec else ("AVAILABLE_AT_ENTRY" if column in IDENTITY else "METADATA")
        if column in UNAVAILABLE_PLACEHOLDERS:
            timing = "UNAVAILABLE"
        future = column in FORBIDDEN_NAMES or column in labels
        usable_pca = bool(
            spec is not None
            and spec.include_in_matrix
            and spec.timing in PREDICTIVE_TIMING
            and avail > 1
            and (variance is None or variance > 0 or spec.kind == "binary")
        )
        if spec is not None and spec.kind == "binary" and avail:
            usable_pca = spec.include_in_matrix and spec.timing in PREDICTIVE_TIMING
        status_mode = None
        if status_series is not None and len(status_series):
            status_mode = str(status_series.mode().iloc[0])
        rows.append(
            {
                "feature_name": column,
                "feature_class": spec.feature_class if spec else ("A" if column in IDENTITY else "META"),
                "class_name": CLASS_LETTER.get(spec.feature_class, "metadata") if spec else "identity_or_metadata",
                "source": spec.source if spec else "asked_six / store key",
                "semantic_basis": spec.semantic_basis if spec else "instance identity",
                "timing": timing,
                "availability_status": status_mode or ("OBSERVED" if missing == 0 else "MIXED"),
                "numeric_or_categorical": "numeric" if numeric else "categorical",
                "encoding": "float/binary 0-1" if numeric else "string identity; not one-hot in ALL PCA",
                "missing_pct": round(100.0 * missing / n, 4),
                "available_n": avail,
                "unique_count": unique,
                "variance": variance,
                "usable_in_pca": usable_pca,
                "usable_in_distance": usable_pca,
                "outcome_or_future": future,
                "missing_kind": _missing_kind(column, status_mode, missing / n),
                "redundant_with": None,
            }
        )
    for spec in LABEL_SPECS:
        rows.append(
            {
                "feature_name": spec.name,
                "feature_class": spec.feature_class,
                "class_name": "labels",
                "source": spec.source,
                "semantic_basis": spec.semantic_basis,
                "timing": spec.timing,
                "availability_status": "ISOLATED_LABELS",
                "numeric_or_categorical": "numeric",
                "encoding": "label parquet only",
                "missing_pct": None,
                "available_n": None,
                "unique_count": None,
                "variance": None,
                "usable_in_pca": False,
                "usable_in_distance": False,
                "outcome_or_future": True,
                "missing_kind": "future_outcome",
                "redundant_with": None,
            }
        )
    _mark_redundancy(rows)
    return rows


def _mark_redundancy(rows: list[dict[str, Any]]) -> None:
    known = {
        "exact_80": "1 - jump_through_80 when entry >= 80",
        "jump_through_80": "complement of exact_80 on this 604",
        "frac_period_remaining": "period_remaining_s / 720",
        "frac_game_elapsed": "1 - game_seconds_remaining / 2880",
        "period_q3": "1 - period_q2",
        "period_q2": "1 - period_q3",
        "abs_margin": "abs(bought_margin)",
        "velocity_5m": "delta_5m / 5",
        "delta_5m": "entry_bid_cents - close_5m_before",
        "score_home": "enters bought_margin with side",
        "score_away": "enters bought_margin with side",
    }
    for row in rows:
        row["redundant_with"] = known.get(row["feature_name"])
