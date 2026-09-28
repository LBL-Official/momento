"""L_t — substitution-only reconstruction. Opening five is unavailable. Never fabricate."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import pandas as pd

from roller.canonical.events import events_visible, project_events
from roller.state.capabilities import INCOMPLETE, SCHEMA_ONLY, capability
from roller.state.missingness import section


def lineup_state(events, *, sport: str, as_of, end_of_day: bool = False) -> dict[str, Any]:
    cap = capability(sport, "lineups")
    if cap == SCHEMA_ONLY:
        return section(SCHEMA_ONLY, None)
    if isinstance(events, pd.DataFrame):
        vis = events_visible(project_events(events), as_of, end_of_day=end_of_day) if not events.empty else events
        recs = vis.to_dict("records") if vis is not None and not vis.empty else []
    else:
        df = pd.DataFrame(list(events or []))
        vis = events_visible(project_events(df), as_of, end_of_day=end_of_day) if not df.empty else df
        recs = vis.to_dict("records") if vis is not None and not vis.empty else []

    on_court: dict[str, list[str]] = defaultdict(list)
    known: dict[str, set[str]] = defaultdict(set)
    for rec in recs:
        if str(rec.get("event_type") or "").lower() != "substitution":
            continue
        pid = str(rec.get("person_id") or "").strip()
        team = str(rec.get("team_tricode") or rec.get("team_id") or "").strip()
        if not pid or not team:
            continue
        direction = str(rec.get("sub_type") or "").strip().lower()
        roster = on_court[team]
        if direction == "out":
            if pid in roster:
                roster.remove(pid)
            known[team].add(pid)
        elif direction == "in":
            if pid not in roster:
                roster.append(pid)
            known[team].add(pid)
        else:
            known[team].add(pid)

    data = {
        "on_court": {team: list(players) for team, players in on_court.items()},
        "known_player_ids": {team: sorted(ids) for team, ids in known.items()},
        "known_count": sum(len(v) for v in known.values()),
        "note": "opening five unavailable; lineup is INCOMPLETE and is not padded to five",
    }
    return section(INCOMPLETE, data)
