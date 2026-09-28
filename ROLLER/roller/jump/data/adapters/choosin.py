"""Choosin Texas read adapter. STATIC prior. Does not copy N=936."""

from __future__ import annotations

from typing import Any

from roller.jump.adapters.choosin import research_context
from roller.jump.data.models import CHOOSIN_N, CHOOSIN_UNIVERSE, LIVE_EXECUTION, UNAVAILABLE


def trade_context(_params: dict[str, Any] | None = None) -> dict[str, Any]:
    body = research_context()
    availability = body.get("availability") or UNAVAILABLE
    return {
        "availability": availability,
        "source_system": "choosin_texas",
        "source": "CHOOSIN_TEXAS",
        "universe": body.get("universe") or CHOOSIN_UNIVERSE,
        "n": body.get("n") or CHOOSIN_N,
        "permission": "QUERY",
        "write": "DENY",
        "pit_kind": "STATIC",
        "data_mode": "STATIC",
        "choosin.population_survival": body.get("historical_survival_rate"),
        "historical_survival_rate": body.get("historical_survival_rate"),
        "entry_cents": body.get("entry_cents"),
        "loss_barrier_cents": body.get("loss_barrier_cents"),
        "articulation": "FIRST80 80→40",
        "live_execution": LIVE_EXECUTION,
        "raw": body,
    }
