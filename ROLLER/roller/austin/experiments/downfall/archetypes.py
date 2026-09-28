"""Frozen mutually exclusive path archetypes. Outcome-blind assignment."""

from __future__ import annotations

from typing import Any

from roller.austin.experiments.downfall.economics import summarize_entries
from roller.austin.experiments.outcomes_ncaab import baseline_hold_cents
from roller.austin.experiments.downfall.ids import (
    ARCHETYPE_NEG_RECOVERY,
    ARCHETYPE_PERS_RECOVERY,
    ARCHETYPE_SINGLE,
    ARCHETYPE_STABLE,
    ARCHETYPE_TO_P2,
    ARCHETYPE_TO_P3,
    ARCHETYPE_UNRESOLVED,
    PERSISTENCE_2,
    PERSISTENCE_3PLUS,
    RECOVERING,
    STATE_DEPTH,
    UNRESOLVED,
    WATCH_NEGATIVE,
)


def assign_archetype(timeline: list[dict[str, Any]]) -> str:
    states = [r["core_state"] for r in timeline]
    valid = [s for s in states if s != UNRESOLVED]
    if not valid:
        return ARCHETYPE_UNRESOLVED
    saw_watch = WATCH_NEGATIVE in valid
    saw_p2 = PERSISTENCE_2 in valid
    saw_p3 = PERSISTENCE_3PLUS in valid
    saw_rec = RECOVERING in valid
    if not saw_watch:
        return ARCHETYPE_STABLE
    if (saw_p2 or saw_p3) and saw_rec:
        return ARCHETYPE_PERS_RECOVERY
    if saw_p3 and not saw_rec:
        return ARCHETYPE_TO_P3
    if saw_p2 and not saw_p3 and not saw_rec:
        return ARCHETYPE_TO_P2
    if saw_watch and saw_rec and not saw_p2:
        return ARCHETYPE_SINGLE
    if saw_watch and saw_rec:
        return ARCHETYPE_NEG_RECOVERY
    return ARCHETYPE_UNRESOLVED


def trade_archetype_row(trade: dict[str, Any], timeline: list[dict[str, Any]], entries: list[dict[str, Any]]) -> dict[str, Any]:
    label = assign_archetype(timeline)
    depths = [STATE_DEPTH[s] for s in (r["core_state"] for r in timeline) if s in STATE_DEPTH]
    neg_rows = [r for r in timeline if r["core_state"] in {WATCH_NEGATIVE, PERSISTENCE_2, PERSISTENCE_3PLUS}]
    watch = next((e for e in entries if e["core_state"] == WATCH_NEGATIVE), None)
    ref = watch or (entries[0] if entries else None)
    won = bool(trade.get("won"))
    return {
        "trade_id": trade["trade_id"],
        "internal_game_id": trade.get("internal_game_id"),
        "source_experiment_id": timeline[0]["source_experiment_id"] if timeline else None,
        "archetype": label,
        "won": won,
        "maximum_state_depth": None if not depths else max(depths),
        "time_spent_negative": len(neg_rows),
        "OUTCOME_pnl_hold_after_state": baseline_hold_cents(trade),
        "OUTCOME_future_T40": None if not ref else ref.get("OUTCOME_future_T40"),
        "OUTCOME_future_MAE": None if not ref else ref.get("OUTCOME_future_MAE"),
        "OUTCOME_future_MFE": None if not ref else ref.get("OUTCOME_future_MFE"),
        "OUTCOME_recover_ge_80": None if not ref else ref.get("OUTCOME_recover_ge_80"),
    }


def archetype_economics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for label in (
        ARCHETYPE_STABLE,
        ARCHETYPE_SINGLE,
        ARCHETYPE_NEG_RECOVERY,
        ARCHETYPE_TO_P2,
        ARCHETYPE_TO_P3,
        ARCHETYPE_PERS_RECOVERY,
        ARCHETYPE_UNRESOLVED,
    ):
        group = [r for r in rows if r["archetype"] == label]
        mapped = [
            {
                "won": r.get("won"),
                "OUTCOME_pnl_hold_after_state": r.get("OUTCOME_pnl_hold_after_state"),
                "OUTCOME_future_T40": r.get("OUTCOME_future_T40"),
                "OUTCOME_future_MAE": r.get("OUTCOME_future_MAE"),
                "OUTCOME_future_MFE": r.get("OUTCOME_future_MFE"),
                "OUTCOME_recover_ge_80": r.get("OUTCOME_recover_ge_80"),
                "OUTCOME_recover_ge_50": None,
                "OUTCOME_recover_ge_60": None,
                "OUTCOME_recover_ge_70": None,
                "current_price": None,
                "price_travel": None,
                "OUTCOME_minutes_to_worst_price": None,
                "OUTCOME_minutes_to_settlement": None,
            }
            for r in group
        ]
        row = summarize_entries(mapped)
        row["archetype"] = label
        row["mean_maximum_state_depth"] = None
        depths = [r.get("maximum_state_depth") for r in group if r.get("maximum_state_depth") is not None]
        if depths:
            row["mean_maximum_state_depth"] = sum(float(d) for d in depths) / len(depths)
        row["mean_time_spent_negative"] = None
        times = [r.get("time_spent_negative") for r in group if r.get("time_spent_negative") is not None]
        if times:
            row["mean_time_spent_negative"] = sum(float(t) for t in times) / len(times)
        out.append(row)
    return out


def depth_analysis(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for state, depth in STATE_DEPTH.items():
        group = [e for e in entries if e["core_state"] == state]
        row = summarize_entries(group)
        row["core_state"] = state
        row["state_depth"] = depth
        out.append(row)
    pnls = [(STATE_DEPTH[s], summarize_entries([e for e in entries if e["core_state"] == s])["mean_pnl_hold_after_state"]) for s in STATE_DEPTH]
    vals = [p for _d, p in pnls if p is not None]
    ordered = all(a >= b for a, b in zip(vals, vals[1:])) if len(vals) >= 2 else False
    return [
        {
            **row,
            "economically_ordered": ordered,
            "note": None if ordered else "STATE DEPTH NOT ECONOMICALLY ORDERED",
        }
        for row in out
    ]


ARCHETYPE_FIELDS = [
    "trade_id",
    "internal_game_id",
    "source_experiment_id",
    "archetype",
    "won",
    "maximum_state_depth",
    "time_spent_negative",
    "OUTCOME_pnl_hold_after_state",
    "OUTCOME_future_T40",
    "OUTCOME_future_MAE",
    "OUTCOME_future_MFE",
    "OUTCOME_recover_ge_80",
]
ARCH_ECON_FIELDS = [
    "source_experiment_id",
    "archetype",
    "N_trades",
    "win_rate",
    "loss_rate",
    "mean_pnl_hold_after_state",
    "T40_rate",
    "mean_future_MAE",
    "mean_future_MFE",
    "recover_ge_80",
    "mean_maximum_state_depth",
    "mean_time_spent_negative",
]
DEPTH_FIELDS = [
    "source_experiment_id",
    "core_state",
    "state_depth",
    "N_trades",
    "loss_rate",
    "mean_pnl_hold_after_state",
    "mean_future_MAE",
    "mean_future_MFE",
    "recover_ge_80",
    "economically_ordered",
    "note",
]
