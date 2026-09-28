"""Two-clock visibility: event_time does not grant visibility. Equality is hidden."""

from __future__ import annotations

import pandas as pd

from roller.canonical.events import events_visible, project_events
from roller.timeutil import resolve_cutoff


def _row(*, event_time: str, available_at: str, event_number: int = 1) -> dict:
    return {
        "internal_game_id": "NBA_20251220_LAL_BOS",
        "event_number": event_number,
        "event_timestamp": event_time,
        "available_at": available_at,
        "home_score": 0,
        "away_score": 0,
        "event_type": "shot",
    }


def test_event_time_before_cutoff_still_hidden_until_available_at():
    events = project_events(pd.DataFrame([_row(event_time="2025-12-20T10:00:00Z", available_at="2025-12-20T10:00:02Z")]))
    assert events_visible(events, "2025-12-20T10:00:01Z").empty
    assert events_visible(events, "2025-12-20T10:00:02Z").empty
    assert len(events_visible(events, "2025-12-20T10:00:03Z")) == 1


def test_equality_and_subsecond_boundaries_are_hidden():
    events = project_events(pd.DataFrame([_row(event_time="2025-12-20T10:00:00Z", available_at="2025-12-20T10:00:02.000Z")]))
    assert events_visible(events, "2025-12-20T10:00:01.999Z").empty
    assert events_visible(events, "2025-12-20T10:00:02.000Z").empty
    assert len(events_visible(events, "2025-12-20T10:00:02.001Z")) == 1


def test_visibility_ignores_event_time_column():
    cutoff = resolve_cutoff("2025-12-20T10:00:03Z")
    events = project_events(
        pd.DataFrame(
            [
                _row(event_time="2025-12-20T09:00:00Z", available_at="2025-12-20T10:00:05Z"),
                _row(event_time="2025-12-20T11:00:00Z", available_at="2025-12-20T10:00:01Z", event_number=2),
            ]
        )
    )
    vis = events_visible(events, cutoff)
    assert list(vis["event_number"]) == [2]
