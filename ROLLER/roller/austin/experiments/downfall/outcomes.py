"""Attach OUTCOME_* after state assignment. Never used to assign state."""

from __future__ import annotations

from typing import Any

from roller.austin.experiments.persistence.util import as_float, clock_minutes_between
from roller.austin.experiments.persistence.warning import _first_t40, _worst_price_row


def _later(timeline: list[dict[str, Any]], entry: dict[str, Any]) -> list[dict[str, Any]]:
    started = False
    out = []
    for row in timeline:
        if row is entry or (
            row.get("state_sequence_number") == entry.get("state_sequence_number")
            and row.get("trade_id") == entry.get("trade_id")
        ):
            started = True
            continue
        if started:
            out.append(row)
    return out


def attach_entry_outcomes(
    entry: dict[str, Any],
    timeline: list[dict[str, Any]],
    trade: dict[str, Any],
) -> dict[str, Any]:
    later = _later(timeline, entry)
    first = entry.get("_row") or {}
    later_rows = [r.get("_row") or {} for r in later]
    prices = [int(r["current_price_cents"]) for r in later_rows if r.get("current_price_cents") is not None]
    price0 = entry.get("current_price")
    if price0 is None:
        price0 = first.get("current_price_cents")
    mae = None if price0 is None or not prices else int(price0) - min(prices)
    mfe = None if price0 is None or not prices else max(prices) - int(price0)
    min_px = None if not prices else min(prices)
    max_px = None if not prices else max(prices)
    t40 = bool(first.get("t40_already")) or any(r.get("t40_already") or r.get("hit_40_after") for r in later_rows)
    fake_event = {"_first": first, "_later": later_rows}
    t40_row = _first_t40(fake_event)
    worst = _worst_price_row(fake_event)
    settle = later_rows[-1] if later_rows else first
    won = bool(trade.get("won"))
    out = dict(entry)
    out["OUTCOME_eventual_result"] = "WIN" if won else "LOSS"
    out["won"] = won
    out["OUTCOME_pnl_hold_after_state"] = as_float(first.get("pnl_hold_after_t"))
    out["OUTCOME_future_T40"] = t40
    out["OUTCOME_future_MAE"] = mae
    out["OUTCOME_future_MFE"] = mfe
    out["OUTCOME_future_min_price"] = min_px
    out["OUTCOME_future_max_price"] = max_px
    out["OUTCOME_recover_ge_50"] = None if max_px is None else max_px >= 50
    out["OUTCOME_recover_ge_60"] = None if max_px is None else max_px >= 60
    out["OUTCOME_recover_ge_70"] = None if max_px is None else max_px >= 70
    out["OUTCOME_recover_ge_80"] = None if max_px is None else max_px >= 80
    out["OUTCOME_minutes_to_T40"] = clock_minutes_between(first, t40_row)
    out["OUTCOME_minutes_to_worst_price"] = clock_minutes_between(first, worst)
    out["OUTCOME_minutes_to_settlement"] = clock_minutes_between(first, settle)
    out["adverse_cents_remaining"] = None if price0 is None or min_px is None else int(price0) - int(min_px)
    return out


ENTRY_FIELDS = [
    "phase_id",
    "model_id",
    "source_experiment_id",
    "trade_id",
    "internal_game_id",
    "ticker",
    "slice",
    "state_sequence_number",
    "timestamp",
    "period",
    "game_clock",
    "core_state",
    "negative_streak_length",
    "CI_state",
    "support_state",
    "EV",
    "CI_lower",
    "CI_upper",
    "current_price",
    "price_travel",
    "ESS",
    "mean_distance",
    "median_distance",
    "feature_coverage",
    "OUTCOME_eventual_result",
    "OUTCOME_pnl_hold_after_state",
    "OUTCOME_future_T40",
    "OUTCOME_future_MAE",
    "OUTCOME_future_MFE",
    "OUTCOME_future_min_price",
    "OUTCOME_future_max_price",
    "OUTCOME_recover_ge_50",
    "OUTCOME_recover_ge_60",
    "OUTCOME_recover_ge_70",
    "OUTCOME_recover_ge_80",
    "OUTCOME_minutes_to_T40",
    "OUTCOME_minutes_to_worst_price",
    "OUTCOME_minutes_to_settlement",
    "adverse_cents_remaining",
]
