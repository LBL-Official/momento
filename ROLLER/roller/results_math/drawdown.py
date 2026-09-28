"""Chronological peak-to-trough. Ordering rule is recorded. Not live equity."""

from __future__ import annotations

from typing import Any

from roller.results_math.models import OBSERVED, UNAVAILABLE


def max_drawdown(pnls: list[float] | list[int]) -> dict[str, Any]:
    if not pnls:
        return {"status": UNAVAILABLE, "reason": "No observed return sequence."}
    peak = 0.0
    equity = 0.0
    max_dd = 0.0
    trough_i = 0
    peak_i = 0
    cur_peak_i = 0
    for i, pnl in enumerate(pnls):
        equity += pnl
        if equity > peak:
            peak = equity
            cur_peak_i = i
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd
            trough_i = i
            peak_i = cur_peak_i
    return {
        "status": OBSERVED,
        "label": "OBSERVED PATH DRAWDOWN · chronological observation order",
        "max_drawdown_cents": float(max_dd),
        "ordering": "entry_ts ascending · not outcome-sorted",
        "peak_index": peak_i,
        "trough_index": trough_i,
        "n": len(pnls),
    }
