"""Choosin Texas → DRE trade prior. Aggregate FIRST80 80/40, not per-trade EV."""

from __future__ import annotations

from typing import Any

from roller.dre.models import CT_EV_DEFINITION, CT_EV_FORMULA
from roller.dre.pit import Stamped, iso, to_utc


def get_trade_context() -> dict[str, Any]:
    from roller.choosin_texas.api import handle_universe

    body = handle_universe()
    pool = body.get("pool") if isinstance(body.get("pool"), dict) else {}
    trade = pool.get("trade_80_40") if isinstance(pool.get("trade_80_40"), dict) else {}
    paths = pool.get("paths") if isinstance(pool.get("paths"), list) else []
    compact_paths = []
    for row in paths:
        if not isinstance(row, dict):
            continue
        compact_paths.append(
            {
                "key": row.get("key"),
                "stop_cents": row.get("stop_cents"),
                "n": row.get("n"),
                "S_display": row.get("S_display"),
                "ev_display": row.get("ev_display"),
                "ev_per_trade_display": row.get("ev_per_trade_display"),
                "note": row.get("note"),
            }
        )
    generated = to_utc(body.get("generated_at"))
    return {
        "source": "CHOOSIN_TEXAS",
        "availability": "STATIC" if body.get("status") == "OBSERVED" else "UNAVAILABLE",
        "status": body.get("status") or "UNAVAILABLE",
        "product": "Choosin Texas",
        "pit_kind": "STATIC",
        "source_timestamp": iso(generated),
        "articulation": "FIRST80 80→40",
        "population": pool.get("slice_label") or "NBA 2Q+3Q ∪ NCAAB 1H2+2H1",
        "cohort": "derived_four",
        "historical_n": pool.get("n"),
        "W": pool.get("W"),
        "L": pool.get("L"),
        "entry_definition": {
            "rule": body.get("rule") or "FIRST80",
            "entry_cents": 80,
            "loss_barrier_cents": 40,
            "gain_cents": 20,
            "unit": body.get("unit"),
        },
        "historical_win_rate": (pool.get("terminal") or {}).get("p_display"),
        "historical_survival_rate": trade.get("S_display"),
        "historical_ev": {
            "label": "HISTORICAL TRADE PRIOR",
            "estimand": "CHOOSIN_TEXAS_POPULATION_EV",
            "definition": CT_EV_DEFINITION,
            "formula": CT_EV_FORMULA,
            "ev_cents": trade.get("ev_cents"),
            "ev_display": trade.get("ev_display"),
            "ev_per_trade_display": trade.get("ev_per_trade_display"),
            "book_cents": trade.get("book_cents"),
            "note": "Candle-path theoretical population EV. Not Austin conditional EV. Not a fill.",
        },
        "baseline_path_profile": compact_paths,
        "trade_classification": "FIRST80 derived-four 80/40",
        "support": None,
        "confidence": trade.get("S_wilson"),
        "source_object_id": "choosin_texas_universe",
        "source_version": "choosin_texas_v1",
        "universe": "derived_four_936",
        "note": "Texas ledger N=936. Not Austin 604. Same prior for every 604 FIRST80 80/40 row.",
        "verification": body.get("verification"),
        "disclaimers": body.get("disclaimers") or [],
        "per_ticker_path_economics": {
            "value": None,
            "availability": "UNAVAILABLE",
            "detail": "Choosin Texas universe is aggregate. No per-trade EV.",
        },
        "stamp": Stamped(
            field="trade_context",
            value=True,
            source="choosin_texas",
            source_timestamp=generated,
            pit_kind="STATIC",
        ),
    }
