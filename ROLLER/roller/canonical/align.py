"""Backward-only market ↔ game alignment.

state(t) = latest PBP row with available_at < t
"""

from __future__ import annotations

import pandas as pd

from roller.timeutil import apply_as_of, parse_utc, resolve_cutoff, series_to_utc


def latest_pbp(pbp: pd.DataFrame, as_of, end_of_day: bool = False) -> pd.Series | None:
    cutoff = resolve_cutoff(as_of, end_of_day=end_of_day)
    sub = apply_as_of(pbp, cutoff)
    if sub.empty:
        return None
    ts = series_to_utc(sub["available_at"])
    return sub.loc[ts.idxmax()]


def latest_candle(candles: pd.DataFrame, as_of, end_of_day: bool = False) -> pd.Series | None:
    cutoff = resolve_cutoff(as_of, end_of_day=end_of_day)
    sub = apply_as_of(candles, cutoff)
    if sub.empty:
        return None
    ts = series_to_utc(sub["available_at"])
    return sub.loc[ts.idxmax()]


def align_candles_to_pbp(candles: pd.DataFrame, pbp: pd.DataFrame) -> pd.DataFrame:
    """merge_asof backward: each candle gets the latest PBP with available_at < candle.available_at."""
    if candles.empty:
        return candles.copy()
    left = candles.copy()
    right = pbp.copy()
    left["_t"] = series_to_utc(left["available_at"])
    right["_t"] = series_to_utc(right["available_at"])
    left = left.dropna(subset=["_t"]).sort_values("_t")
    right = right.dropna(subset=["_t"]).sort_values("_t")
    if left.empty:
        return candles.iloc[0:0].copy()
    merged = pd.merge_asof(
        left,
        right,
        on="_t",
        direction="backward",
        suffixes=("", "_pbp"),
        allow_exact_matches=False,
    )
    return merged.drop(columns=["_t"])


def assert_no_future_pbp(aligned: pd.DataFrame) -> list[str]:
    errors = []
    if "available_at" not in aligned.columns or "available_at_pbp" not in aligned.columns:
        return errors
    for i, rec in aligned.iterrows():
        c = parse_utc(rec.get("available_at"))
        p = parse_utc(rec.get("available_at_pbp"))
        if c is None or p is None:
            continue
        if not (p < c):
            errors.append(f"future or equal PBP attached at row {i}: pbp={p} candle={c}")
    return errors
