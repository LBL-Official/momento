"""First-class measurement provenance. Reconstructible, not decorative."""

from __future__ import annotations

from typing import Any

from roller.v4b.types import CandleView, FundamentalView, SharedXt


def latest_iso(*values: str | None) -> str | None:
    present = [v for v in values if v]
    if not present:
        return None
    return max(present)


def candle_pair_prov(xt: SharedXt) -> dict[str, Any]:
    cur = xt.current
    prev = xt.previous
    return {
        "current_available_at": None if cur is None else cur.available_at,
        "previous_available_at": None if prev is None else prev.available_at,
        "interval_seconds": xt.interval_seconds,
        "expected_interval_seconds": xt.expected_interval_seconds,
        "target_cutoff": xt.cutoff_iso,
    }


def fundamental_pair_prov(cur: FundamentalView | None, prev: FundamentalView | None) -> dict[str, Any]:
    return {
        "current_fundamental_cutoff": None if cur is None else cur.cutoff,
        "prior_fundamental_cutoff": None if prev is None else prev.cutoff,
        "current_numerator": None if cur is None else cur.wins,
        "current_denominator": None if cur is None else cur.n,
        "prior_numerator": None if prev is None else prev.wins,
        "prior_denominator": None if prev is None else prev.n,
        "current_observation_id": None if cur is None else cur.observation_id,
        "prior_observation_id": None if prev is None else prev.observation_id,
        "current_available_at": None if cur is None else cur.available_at,
        "prior_available_at": None if prev is None else prev.available_at,
    }


def ohlc_prov(candle: CandleView | None) -> dict[str, Any]:
    if candle is None:
        return {}
    return {
        "current_available_at": candle.available_at,
        "yes_bid_open": candle.yes_bid_open,
        "yes_bid_high": candle.yes_bid_high,
        "yes_bid_low": candle.yes_bid_low,
        "yes_bid_close": candle.yes_bid_close,
    }
