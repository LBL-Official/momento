"""Visible home candles. Half-open: available_at < cutoff."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from roller.measurement.integers import parse_e4
from roller.timeutil import apply_as_of, parse_utc, resolve_cutoff, series_to_utc, to_iso
from roller.v4b.types import CandleView


def _row_view(rec: dict[str, Any]) -> CandleView | None:
    ts = parse_utc(rec.get("available_at"))
    if ts is None:
        return None
    return CandleView(
        available_at=to_iso(ts) if not isinstance(rec.get("available_at"), str) else str(rec.get("available_at")),
        available_at_dt=ts,
        yes_bid_close=parse_e4(rec.get("yes_bid_close")),
        yes_bid_open=parse_e4(rec.get("yes_bid_open")),
        yes_bid_high=parse_e4(rec.get("yes_bid_high")),
        yes_bid_low=parse_e4(rec.get("yes_bid_low")),
    )


def visible_home_candles(candles: pd.DataFrame, cutoff) -> list[CandleView]:
    """Latest-visible ordering: oldest first. Equality at cutoff is hidden."""
    if candles is None or candles.empty:
        return []
    cut = cutoff if isinstance(cutoff, datetime) else resolve_cutoff(cutoff)
    out = apply_as_of(candles, cut)
    if out.empty:
        return []
    if "team_side" in out.columns:
        home = out[out["team_side"].astype(str) == "home"]
        if not home.empty:
            out = home
    ts = series_to_utc(out["available_at"])
    ordered = out.assign(_t=ts).dropna(subset=["_t"]).sort_values("_t")
    views: list[CandleView] = []
    for rec in ordered.to_dict("records"):
        view = _row_view(rec)
        if view is not None:
            views.append(view)
    return views


def interval_seconds(later: CandleView | None, earlier: CandleView | None) -> int | None:
    if later is None or earlier is None:
        return None
    return int((later.available_at_dt - earlier.available_at_dt).total_seconds())


def interval_matches(seconds: int | None, expected: int) -> bool:
    return seconds is not None and int(seconds) == int(expected)
