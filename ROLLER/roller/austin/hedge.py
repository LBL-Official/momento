"""41/42 maker-40 hedge lab. Path events, not fills."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from roller.austin.bars_join import (
    first_close_at_or_above,
    first_close_at_or_below,
    first_high_at_or_above,
    parse_entry,
    split_post,
)
from roller.austin.config import DEFAULT
from roller.austin.locks import N_TRADES
from roller.austin.outcomes import hold_pnl_cents, taker_8040_pnl_cents


FILL_RATES = (1.0, 0.75, 0.50, 0.25, 0.0)
SCENARIO_LABEL = "SCENARIO — NOT OBSERVED FILL RATE"


def _after(series: list, when: datetime):
    return [row for row in series if row[0] > when]


def trade_hedge(trade: dict[str, Any], paths: dict[str, Any]) -> dict[str, Any]:
    entry = parse_entry(trade)
    fav = [] if entry is None else split_post(paths["favorite"].get(trade["ticker"], []), entry)
    opp_ticker = paths["opponent_ticker"].get(trade["ticker"])
    opp = [] if entry is None or not opp_ticker else split_post(paths["favorite"].get(opp_ticker, []), entry)
    won = bool(trade["w"])
    hold = hold_pnl_cents(won=won)
    taker = taker_8040_pnl_cents(won=won, hit_40=bool(trade["t40"]))
    rows: dict[str, Any] = {}
    for trigger in DEFAULT.hedge_triggers:
        fav_hit = first_close_at_or_below(fav, float(trigger))
        triggered = fav_hit is not None
        later = [] if fav_hit is None else _after(opp, fav_hit[0])
        reached = first_close_at_or_above(later, 40.0) is not None
        wick = first_high_at_or_above(later, 40.0) is not None
        lock = -20
        path_pnl = lock if reached else hold
        scenarios = []
        for rate in FILL_RATES:
            # fill only if path reached opponent 40; otherwise no fill possible
            p = rate if reached else 0.0
            ev = p * lock + (1.0 - p) * hold
            scenarios.append(
                {
                    "fill_rate": rate,
                    "label": SCENARIO_LABEL,
                    "net_pnl_cents": ev,
                    "applied_fill_rate": p,
                }
            )
        rows[str(trigger)] = {
            "trigger": trigger,
            "hedge_price": 40,
            "hedge_triggered_path": triggered,
            "hedge_price_reached": reached,
            "hedge_wick_reached": wick,
            "hedge_fill_observed": False,
            "hedge_fill_status": DEFAULT.fill_status,
            "path_based_hedge_pnl_cents": path_pnl,
            "hold_pnl_cents": hold,
            "taker_8040_pnl_cents": taker,
            "scenarios": scenarios,
        }
    return {
        "trade_id": trade["trade_id"],
        "won": won,
        "csv_t40": bool(trade["t40"]),
        "triggers": rows,
        "fee_model_status": DEFAULT.fee_status,
        "fill_model_status": DEFAULT.fill_status,
        "candle_path_not_fill": True,
        "reference_only_n": DEFAULT.reference_hedge_n,
    }


def trigger_resolution_audit(trades: list[dict[str, Any]], paths: dict[str, Any]) -> dict[str, Any]:
    """1m close cannot always separate 41 from 42. Measure, do not invent."""
    n_first_le_42 = 0
    n_first_le_41 = 0
    n_42_without_41 = 0
    n_same_bar_42_and_41 = 0
    for trade in trades:
        entry = parse_entry(trade)
        fav = [] if entry is None else split_post(paths["favorite"].get(trade["ticker"], []), entry)
        hit42 = first_close_at_or_below(fav, 42.0)
        hit41 = first_close_at_or_below(fav, 41.0)
        if hit42 is not None:
            n_first_le_42 += 1
            if hit42[1] > 41.0:
                n_42_without_41 += 1
        if hit41 is not None:
            n_first_le_41 += 1
        if hit42 is not None and hit41 is not None and hit42[0] == hit41[0]:
            n_same_bar_42_and_41 += 1
    return {
        "TRIGGER_RESOLUTION": "1m_close",
        "definition_42": "first favorite yes_bid_close <= 42 after entry",
        "definition_41": "first favorite yes_bid_close <= 41 after entry",
        "n_first_le_42": n_first_le_42,
        "n_first_le_41": n_first_le_41,
        "n_42_without_41": n_42_without_41,
        "n_same_bar_42_and_41": n_same_bar_42_and_41,
        "note": "If n_42_without_41=0, 1m closes skip 42-only prints. Do not invent separated hedge economics.",
    }


def summarize_hedge(rows: list[dict[str, Any]], *, resolution: dict[str, Any] | None = None) -> dict[str, Any]:
    n = len(rows)
    out: dict[str, Any] = {
        "n_trades": n,
        "n_lock": N_TRADES,
        "fee_model_status": DEFAULT.fee_status,
        "fill_model_status": DEFAULT.fill_status,
        "scenario_label": SCENARIO_LABEL,
        "reference_only": {
            "book": "NBA FULL FIRST80 hedge V1",
            "n": DEFAULT.reference_hedge_n,
            "close_path_ev_cents": 5.17,
            "taker_ev_cents": 4.39,
            "note": "Do not mix 1230 with Austin 604.",
        },
        "triggers": {},
        "resolution": resolution or {},
    }
    if n == 0:
        return out
    taker = sum(float(row["triggers"]["42"]["taker_8040_pnl_cents"]) for row in rows) / n
    hold = sum(float(row["triggers"]["42"]["hold_pnl_cents"]) for row in rows) / n
    for trigger in DEFAULT.hedge_triggers:
        key = str(trigger)
        trig = sum(1 for row in rows if row["triggers"][key]["hedge_triggered_path"])
        reached = sum(1 for row in rows if row["triggers"][key]["hedge_price_reached"])
        path_ev = sum(float(row["triggers"][key]["path_based_hedge_pnl_cents"]) for row in rows) / n
        scenarios = []
        for i, rate in enumerate(FILL_RATES):
            ev = sum(float(row["triggers"][key]["scenarios"][i]["net_pnl_cents"]) for row in rows) / n
            scenarios.append({"fill_rate": rate, "label": SCENARIO_LABEL, "mean_net_pnl_cents": ev})
        out["triggers"][key] = {
            "trigger": trigger,
            "hedge_price": 40,
            "n_triggered_path": trig,
            "n_price_reached": reached,
            "path_based_mean_pnl_cents": path_ev,
            "taker_8040_mean_pnl_cents": taker,
            "hold_mean_pnl_cents": hold,
            "scenarios": scenarios,
            "hedge_fill_status": DEFAULT.fill_status,
        }
    return out
