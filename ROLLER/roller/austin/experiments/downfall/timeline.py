"""PRIMARY_GRID timelines and first state entries. PIT only."""

from __future__ import annotations

from typing import Any

from roller.austin.experiments.downfall.engine import derive_downfall_state
from roller.austin.experiments.downfall.ids import MODEL_ID, PHASE3_PHASE
from roller.austin.experiments.ids import SLICE_BY_EXPERIMENT
from roller.austin.experiments.persistence.events import primary_rows
from roller.austin.experiments.persistence.util import as_float


def _coerce_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for key in (
        "price_travel",
        "time_since_entry",
        "effective_neighbors",
        "effective_sample_size",
        "median_distance",
        "mean_distance",
        "feature_coverage",
        "score_travel",
        "score_diff_travel",
    ):
        if key in out:
            out[key] = as_float(out.get(key))
    for key in ("home_score", "away_score", "current_price_cents", "period", "game_clock_remaining"):
        val = as_float(out.get(key))
        out[key] = None if val is None else int(val)
    return out


def trade_primary(queries: list[dict[str, Any]], trade_id: str) -> list[dict[str, Any]]:
    return [_coerce_row(r) for r in primary_rows(queries, trade_id)]


def build_timeline(
    experiment_id: str,
    trade: dict[str, Any],
    queries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    primary = trade_primary(queries, trade["trade_id"])
    rows = []
    for idx, _row in enumerate(primary):
        history = primary[: idx + 1]
        derived = derive_downfall_state(history)
        now = history[-1]
        rows.append(
            {
                "phase_id": PHASE3_PHASE,
                "model_id": MODEL_ID,
                "source_experiment_id": experiment_id,
                "trade_id": trade["trade_id"],
                "internal_game_id": trade.get("internal_game_id"),
                "ticker": trade.get("ticker"),
                "slice": SLICE_BY_EXPERIMENT[experiment_id],
                "state_sequence_number": idx,
                "timestamp": now.get("timestamp_utc"),
                "period": now.get("period"),
                "game_clock": now.get("game_clock_remaining"),
                "core_state": derived["core_state"],
                "negative_streak_length": derived["negative_streak_length"],
                "CI_state": derived["CI_state"],
                "support_state": derived["support_state"],
                "EV": derived["EV_now"],
                "CI_lower": derived["CI_lower"],
                "CI_upper": derived["CI_upper"],
                "EV_entry": derived["EV_entry"],
                "EV_change_from_entry": derived["EV_change_from_entry"],
                "previous_EV": derived["EV_previous"],
                "EV_change_from_previous": derived["EV_change_from_previous"],
                "EV_velocity": derived["EV_velocity"],
                "EV_acceleration": derived["EV_acceleration"],
                "current_price": derived["price"],
                "price_travel": derived["price_travel"],
                "score": derived["score"],
                "score_diff": derived["score_diff"],
                "score_travel": derived["score_travel"],
                "score_diff_travel": derived["score_diff_travel"],
                "time_since_entry": derived["time_since_entry"],
                "game_time_remaining": derived["game_time_remaining"],
                "ESS": derived["ESS"],
                "effective_neighbors": derived["effective_neighbors"],
                "mean_distance": derived["mean_distance"],
                "median_distance": derived["median_distance"],
                "feature_coverage": derived["feature_coverage"],
                "availability_status": derived["availability_status"],
                "_row": now,
                "_history_len": len(history),
            }
        )
    return rows


def first_entries(timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out = []
    for row in timeline:
        state = str(row["core_state"])
        if state in seen:
            continue
        seen.add(state)
        out.append(dict(row))
    return out


TIMELINE_FIELDS = [
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
    "EV_entry",
    "EV_change_from_entry",
    "previous_EV",
    "EV_change_from_previous",
    "EV_velocity",
    "EV_acceleration",
    "current_price",
    "price_travel",
    "score",
    "score_diff",
    "score_travel",
    "score_diff_travel",
    "time_since_entry",
    "game_time_remaining",
    "ESS",
    "effective_neighbors",
    "mean_distance",
    "median_distance",
    "feature_coverage",
    "availability_status",
]
