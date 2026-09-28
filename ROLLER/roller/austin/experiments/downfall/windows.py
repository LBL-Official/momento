"""Descriptive remaining-damage objects. Not an intervention instruction."""

from __future__ import annotations

from typing import Any

from roller.austin.experiments.downfall.economics import summarize_entries
from roller.austin.experiments.downfall.ids import (
    HEALTHY,
    HEALTHY_AFTER_RECOVERY,
    PERSISTENCE_2,
    PERSISTENCE_3PLUS,
    RECOVERING,
    WATCH_NEGATIVE,
)

WINDOW_STATES = (WATCH_NEGATIVE, PERSISTENCE_2, PERSISTENCE_3PLUS, RECOVERING, HEALTHY_AFTER_RECOVERY)


def window_rows(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for entry in entries:
        if entry["core_state"] not in WINDOW_STATES and entry["core_state"] != HEALTHY:
            continue
        out.append(
            {
                "trade_id": entry["trade_id"],
                "internal_game_id": entry.get("internal_game_id"),
                "source_experiment_id": entry.get("source_experiment_id"),
                "core_state": entry["core_state"],
                "price_at_state": entry.get("current_price"),
                "price_travel": entry.get("price_travel"),
                "future_min_price": entry.get("OUTCOME_future_min_price"),
                "adverse_cents_remaining": entry.get("adverse_cents_remaining"),
                "minutes_to_worst_price": entry.get("OUTCOME_minutes_to_worst_price"),
                "minutes_to_T40": entry.get("OUTCOME_minutes_to_T40"),
                "minutes_to_settlement": entry.get("OUTCOME_minutes_to_settlement"),
                "note": "INTERVENTION_WINDOW_REMAINING is descriptive. Not a trading instruction.",
            }
        )
    return out


def timing_rows(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for entry in entries:
        out.append(
            {
                "trade_id": entry["trade_id"],
                "internal_game_id": entry.get("internal_game_id"),
                "source_experiment_id": entry.get("source_experiment_id"),
                "core_state": entry["core_state"],
                "eventual_result": entry.get("OUTCOME_eventual_result"),
                "minutes_to_T40": entry.get("OUTCOME_minutes_to_T40"),
                "minutes_to_worst_price": entry.get("OUTCOME_minutes_to_worst_price"),
                "minutes_to_settlement": entry.get("OUTCOME_minutes_to_settlement"),
                "adverse_cents_remaining": entry.get("adverse_cents_remaining"),
                "note": "STATE TIMING is not validated early warning.",
            }
        )
    return out


WINDOW_FIELDS = [
    "trade_id",
    "internal_game_id",
    "source_experiment_id",
    "core_state",
    "price_at_state",
    "price_travel",
    "future_min_price",
    "adverse_cents_remaining",
    "minutes_to_worst_price",
    "minutes_to_T40",
    "minutes_to_settlement",
    "note",
]
def remaining_damage_summary(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for state in (WATCH_NEGATIVE, PERSISTENCE_2, PERSISTENCE_3PLUS, RECOVERING):
        group = [e for e in entries if e["core_state"] == state]
        row = summarize_entries(group)
        row["core_state"] = state
        row["mean_price_at_state"] = row.get("mean_current_price")
        out.append(row)
    return out


def timing_summary(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for state in WINDOW_STATES:
        for result in ("WIN", "LOSS"):
            group = [e for e in entries if e["core_state"] == state and e.get("OUTCOME_eventual_result") == result]
            row = summarize_entries(group)
            row["core_state"] = state
            row["eventual_result"] = result
            out.append(row)
    return out


TIMING_FIELDS = [
    "trade_id",
    "internal_game_id",
    "source_experiment_id",
    "core_state",
    "eventual_result",
    "minutes_to_T40",
    "minutes_to_worst_price",
    "minutes_to_settlement",
    "adverse_cents_remaining",
    "note",
]
