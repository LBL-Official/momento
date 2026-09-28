"""Canonical event projection. V1 PBP columns plus NBA pass-through fields.

Never invent timeActual. Visibility uses available_at < cutoff only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from roller.timeutil import apply_as_of, resolve_cutoff

EVENT_PASS_THROUGH = (
    "person_id",
    "sub_type",
    "shot_result",
    "team_id",
    "player_name",
    "time_actual",
    "home_away",
)


def project_events(pbp: pd.DataFrame) -> pd.DataFrame:
    """Project V1 PBP rows. Alias event_time; fill missing NBA pass-through columns."""
    if pbp is None or pbp.empty:
        cols = [
            "internal_game_id",
            "event_number",
            "event_timestamp",
            "event_time",
            "available_at",
            *EVENT_PASS_THROUGH,
        ]
        return pd.DataFrame(columns=cols)
    out = pbp.copy()
    if "event_time" not in out.columns:
        out["event_time"] = out["event_timestamp"] if "event_timestamp" in out.columns else ""
    for col in EVENT_PASS_THROUGH:
        if col not in out.columns:
            out[col] = ""
    return out


def events_visible(events: pd.DataFrame, as_of, end_of_day: bool = False) -> pd.DataFrame:
    """Constitutional choke point: available_at < cutoff. event_time is ignored."""
    cutoff = as_of if isinstance(as_of, datetime) else resolve_cutoff(as_of, end_of_day=end_of_day)
    return apply_as_of(events, cutoff)


def event_records(events: pd.DataFrame) -> list[dict[str, Any]]:
    if events is None or events.empty:
        return []
    return events.to_dict("records")
