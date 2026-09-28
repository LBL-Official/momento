"""G_t — current game state from visible events."""

from __future__ import annotations

from typing import Any

import pandas as pd

from roller.canonical.align import latest_pbp
from roller.canonical.events import events_visible, project_events
from roller.state.capabilities import capability
from roller.state.clock import elapsed_game_seconds
from roller.state.missingness import field, section


def game_state_section(
    pbp: pd.DataFrame,
    game: dict[str, Any] | None,
    *,
    sport: str,
    as_of,
    end_of_day: bool = False,
) -> dict[str, Any]:
    events = events_visible(project_events(pbp), as_of, end_of_day=end_of_day) if pbp is not None and not pbp.empty else pbp
    latest = latest_pbp(pbp, as_of, end_of_day=end_of_day) if pbp is not None and not pbp.empty else None
    status = capability(sport, "events")
    if latest is None:
        return section(
            "PARTIAL" if status == "REAL" else status,
            {
                "game": game,
                "n_events": 0,
                "score": {
                    "home": field(None, "known_missing", "pbp.home_score"),
                    "away": field(None, "known_missing", "pbp.away_score"),
                },
            },
        )
    rec = latest.to_dict()
    data = {
        "game": game,
        "n_events": int(len(events)) if events is not None else 0,
        "period": rec.get("period"),
        "clock": rec.get("clock"),
        "elapsed_game_seconds": elapsed_game_seconds(rec.get("period"), rec.get("clock"), sport=sport),
        "score": {
            "home": field(rec.get("home_score"), "observed", "pbp.home_score"),
            "away": field(rec.get("away_score"), "observed", "pbp.away_score"),
            "score_differential_home": field(
                rec.get("score_differential_home"), "observed", "pbp.score_differential_home"
            ),
        },
        "latest_event_number": rec.get("event_number"),
        "latest_event_type": rec.get("event_type"),
        "latest_available_at": rec.get("available_at"),
    }
    return section("REAL", data)
