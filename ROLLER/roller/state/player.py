"""P_t — in-game player totals from personId. WNBA/NCAAB are NOT_SUPPORTED."""

from __future__ import annotations

from typing import Any

from roller.canonical.events import events_visible, project_events
from roller.state.capabilities import NOT_SUPPORTED, capability
from roller.state.missingness import section
import pandas as pd


def _points_for(event: dict[str, Any]) -> int:
    sr = str(event.get("shot_result") or "").strip().lower()
    if sr not in {"made", "make"}:
        return 0
    et = str(event.get("event_type") or "").lower().replace(" ", "").replace("-", "")
    st = str(event.get("sub_type") or "").lower()
    if et in {"freethrow", "freethrows"} or "free" in st:
        return 1
    if "3" in st or et in {"3pt", "threepoint"}:
        return 3
    return 2


def player_state(events, *, sport: str, as_of, end_of_day: bool = False) -> dict[str, Any]:
    cap = capability(sport, "player_state")
    if cap == NOT_SUPPORTED:
        return section(NOT_SUPPORTED, None)
    if cap != "REAL":
        return section(cap, None)

    if isinstance(events, pd.DataFrame):
        vis = events_visible(project_events(events), as_of, end_of_day=end_of_day)
        recs = vis.to_dict("records") if vis is not None and not vis.empty else []
    else:
        df = pd.DataFrame(list(events or []))
        vis = events_visible(project_events(df), as_of, end_of_day=end_of_day) if not df.empty else df
        recs = vis.to_dict("records") if vis is not None and not vis.empty else []

    if not recs:
        return section("PARTIAL", {"players": {}})

    players: dict[str, dict[str, Any]] = {}
    missing_person = 0
    for rec in recs:
        pid = str(rec.get("person_id") or "").strip()
        if not pid:
            missing_person += 1
            continue
        slot = players.setdefault(
            pid,
            {
                "player_id": pid,
                "display_name": rec.get("player_name") or "",
                "team_tricode": rec.get("team_tricode") or "",
                "points": 0,
                "made_fg": 0,
                "events": 0,
            },
        )
        slot["events"] += 1
        pts = _points_for(rec)
        slot["points"] += pts
        if pts >= 2:
            slot["made_fg"] += 1
        if rec.get("player_name") and not slot["display_name"]:
            slot["display_name"] = rec["player_name"]

    status = "REAL" if players else "PARTIAL"
    return section(
        status,
        {
            "players": players,
            "events_without_person_id": missing_person,
        },
    )
