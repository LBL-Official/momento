"""TK Ultra's own Choosin Texas adapter. STATIC prior. Not Ballhog's."""

from __future__ import annotations

from typing import Any

from roller.dre.adapters.choosin import get_trade_context as dre_get_trade_context

CHOOSIN_ADAPTER = "roller.tk_ultra.adapters.choosin.get_trade_context"


def get_trade_context() -> dict[str, Any]:
    return dre_get_trade_context()


def extract_benchmark(ctx: dict[str, Any] | None) -> dict[str, Any]:
    body = ctx if isinstance(ctx, dict) else {}
    entry = body.get("entry_definition") if isinstance(body.get("entry_definition"), dict) else {}
    return {
        "availability": body.get("availability") or "UNAVAILABLE",
        "universe": body.get("universe"),
        "historical_n": body.get("historical_n"),
        "entry_cents": entry.get("entry_cents"),
        "loss_barrier_cents": entry.get("loss_barrier_cents"),
        "gain_cents": entry.get("gain_cents"),
        "historical_survival_rate": body.get("historical_survival_rate"),
        "historical_win_rate": body.get("historical_win_rate"),
        "historical_ev": body.get("historical_ev"),
        "baseline_path_profile": body.get("baseline_path_profile"),
        "pit_kind": body.get("pit_kind") or "STATIC",
        "source": "CHOOSIN_TEXAS",
        "note": "Population prior. Not Austin 604. Not as_of path EV.",
    }
