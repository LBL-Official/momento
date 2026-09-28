"""69/68 path events resolving toward a 67¢ hedge. Not a fill."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from roller.austin.bars_join import first_close_at_or_above, first_close_at_or_below, first_high_at_or_above, parse_entry, split_post
from roller.austin.config import DEFAULT
from roller.austin_first78.config import CFG, STOP_CENTS
from roller.austin_first78.outcomes import official_pnl_cents

FILL_RATES = (1.0, 0.75, 0.50, 0.25, 0.0)
SCENARIO_LABEL = "SCENARIO — NOT OBSERVED FILL RATE"
LOCK = int(STOP_CENTS) - 78


def trade_hedge(trade: dict[str, Any], paths: dict[str, Any]) -> dict[str, Any]:
    entry = parse_entry(trade)
    fav = [] if entry is None else split_post(paths["favorite"].get(trade["ticker"], []), entry)
    opp_ticker = paths["opponent_ticker"].get(trade["ticker"])
    opp = [] if entry is None or not opp_ticker else split_post(paths["favorite"].get(opp_ticker, []), entry)
    won = bool(trade["w"])
    hold = official_pnl_cents(won=won, stopped=False)
    path_trade = official_pnl_cents(won=won, stopped=bool(trade["t67"]))
    rows: dict[str, Any] = {}
    for trigger in CFG.hedge_triggers:
        fav_hit = first_close_at_or_below(fav, float(trigger))
        later = [] if fav_hit is None else [row for row in opp if row[0] > fav_hit[0]]
        reached = first_close_at_or_above(later, float(STOP_CENTS)) is not None
        wick = first_high_at_or_above(later, float(STOP_CENTS)) is not None
        path_pnl = LOCK if reached else hold
        scenarios = []
        for rate in FILL_RATES:
            applied = rate if reached else 0.0
            scenarios.append(
                {
                    "fill_rate": rate,
                    "label": SCENARIO_LABEL,
                    "net_pnl_cents": applied * LOCK + (1.0 - applied) * hold,
                    "applied_fill_rate": applied,
                }
            )
        rows[str(trigger)] = {
            "trigger": trigger,
            "hedge_price": STOP_CENTS,
            "hedge_triggered_path": fav_hit is not None,
            "hedge_price_reached": reached,
            "hedge_wick_reached": wick,
            "hedge_fill_observed": False,
            "hedge_fill_status": DEFAULT.fill_status,
            "path_based_hedge_pnl_cents": path_pnl,
            "hold_pnl_cents": hold,
            "taker_7867_pnl_cents": path_trade,
            "scenarios": scenarios,
        }
    return {"trade_id": trade["trade_id"], "won": won, "t67": bool(trade["t67"]), "triggers": rows}


def trigger_resolution_audit(trades: list[dict[str, Any]], paths: dict[str, Any]) -> dict[str, Any]:
    n_69 = n_68 = n_69_without_68 = n_same = 0
    for trade in trades:
        entry = parse_entry(trade)
        fav = [] if entry is None else split_post(paths["favorite"].get(trade["ticker"], []), entry)
        hit69 = first_close_at_or_below(fav, 69.0)
        hit68 = first_close_at_or_below(fav, 68.0)
        if hit69 is not None:
            n_69 += 1
            if hit69[1] > 68.0:
                n_69_without_68 += 1
        if hit68 is not None:
            n_68 += 1
        if hit69 is not None and hit68 is not None and hit69[0] == hit68[0]:
            n_same += 1
    return {
        "TRIGGER_RESOLUTION": "1m_close",
        "definition_69": "first favorite close <= 69 after the 78 entry",
        "definition_68": "first favorite close <= 68 after the 78 entry",
        "n_first_le_69": n_69,
        "n_first_le_68": n_68,
        "n_69_without_68": n_69_without_68,
        "n_same_bar_69_and_68": n_same,
        "note": "1m closes can skip a 69-only print. Hedge price is 67. Candle path is not a fill.",
    }


def summarize_hedge(rows: list[dict[str, Any]], *, resolution: dict[str, Any] | None = None) -> dict[str, Any]:
    n = len(rows)
    out: dict[str, Any] = {
        "n_trades": n,
        "fee_model_status": DEFAULT.fee_status,
        "fill_model_status": DEFAULT.fill_status,
        "scenario_label": SCENARIO_LABEL,
        "hedge_price_cents": STOP_CENTS,
        "triggers": {},
        "resolution": resolution or {},
        "candle_path_not_fill": True,
    }
    if n == 0:
        return out
    for trigger in CFG.hedge_triggers:
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
            "hedge_price": STOP_CENTS,
            "n_triggered_path": trig,
            "n_price_reached": reached,
            "path_based_mean_pnl_cents": path_ev,
            "scenarios": scenarios,
            "hedge_fill_status": DEFAULT.fill_status,
        }
    return out
