"""Central as_of choke point. Half-open: available_at < cutoff."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from roller.timeutil import apply_as_of, parse_utc, resolve_cutoff

RESULT_COLS = [
    "final_home_score",
    "final_away_score",
    "home_win",
    "away_win",
    "result",
    "settlement_value_e4",
    "kalshi_yes_settled",
]


class AsOfRequiredError(ValueError):
    pass


class FutureInformationError(ValueError):
    """Public dataset() refused a table that contains future information."""


FUTURE_DATASET_NAMES = frozenset(
    {
        "game_state_features",
        "terminal_labels",
        "horizon_labels",
        "path_labels",
        "barrier_labels",
        "possession_labels",
        "labels",
        "response_corpus",
        "market_response",
        "score_response",
        "baseline",
        "residual",
        "fundamental",
        "v4a_fundamental_state_corpus",
        "greek_observations",
        "greek_baselines",
        "v4b_greek_observations",
        "v4c_greek_observations",
        "v4c_catalog",
        "first80_triggers",
        "first80",
    }
)


def dataset_is_v4b(dataset: str) -> bool:
    """V4B names only. Do not steal V3 greek_* wrapper names."""
    name = str(dataset or "").strip()
    if name.startswith("v4b_"):
        return True
    if name in {"greek_observations", "greek_baselines"}:
        return True
    return False


def dataset_is_v4c(dataset: str) -> bool:
    """V4C architecture objects are query-time. Use db.greeks()."""
    name = str(dataset or "").strip()
    return name.startswith("v4c_")


def dataset_is_fundamental(dataset: str) -> bool:
    """Exact / prefix / suffix only. Do not substring-match canonical tables."""
    name = str(dataset or "").strip()
    if name == "fundamental":
        return True
    if name.startswith("fundamental_"):
        return True
    if name.endswith("_fundamental"):
        return True
    if name.startswith("v4a_fundamental"):
        return True
    return False


def dataset_contains_future_information(dataset: str, schemas: dict | None = None) -> bool:
    name = str(dataset or "").strip()
    if name in FUTURE_DATASET_NAMES:
        return True
    if dataset_is_fundamental(name) or dataset_is_v4b(name) or dataset_is_v4c(name):
        return True
    if name.startswith("first80"):
        return True
    if name.endswith("_labels") or name.endswith("_terminal"):
        return True
    if "_response" in name or name.endswith("_baseline") or name.endswith("_residual"):
        return True
    if name.endswith("_greek") or name.startswith("greek_") or name.startswith("measurement_"):
        return True
    if "response_corpus" in name:
        return True
    if schemas:
        schema = (schemas.get("datasets") or {}).get(name) or {}
        if schema.get("contains_future_information"):
            return True
    return False


def public_filter(
    df: pd.DataFrame,
    *,
    as_of=None,
    end_of_day: bool = False,
    full_history: bool = False,
    mask_results: bool = False,
) -> pd.DataFrame:
    if full_history:
        return df.copy()
    if as_of is None:
        raise AsOfRequiredError("public dataset() requires as_of or full_history=True")
    cutoff = resolve_cutoff(as_of, end_of_day=end_of_day)
    out = apply_as_of(df, cutoff)
    if mask_results and "result_available_at" in out.columns:
        out = mask_unready_results(out, cutoff)
    return out


def mask_unready_results(df: pd.DataFrame, cutoff: datetime) -> pd.DataFrame:
    out = df.copy()
    ready = []
    for v in out["result_available_at"].tolist():
        ts = parse_utc(v) if str(v).strip() else None
        ready.append(ts is not None and ts < cutoff)
    for col in RESULT_COLS:
        if col in out.columns:
            out.loc[[not r for r in ready], col] = ""
    return out
