"""Clock snap at a timestamp.

Last visible PBP row whose event_timestamp <= snap time.
Public API still requires available_at < as_of (I(t)).
This does not invent a wall clock from tip + remaining.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from roller.admin import load_dataset, load_identity
from roller.canonical.events import event_records, events_visible, project_events
from roller.config import RollerConfig
from roller.point_in_time.filters import AsOfRequiredError
from roller.state.clock import clock_remaining_seconds, elapsed_game_seconds, entry_slice
from roller.timeutil import parse_utc, resolve_cutoff, to_iso


def pbp_event_ts(ev: dict[str, Any]) -> datetime | None:
    """Canonical PBP event clock. event_timestamp wins if event_time disagrees."""
    return parse_utc(
        ev.get("event_timestamp")
        or ev.get("event_time")
        or ev.get("time_actual")
        or ev.get("point_timestamp")
    )


def snap_events(
    events: list[dict[str, Any]],
    snap_ts: datetime,
    *,
    sport: str = "NBA",
) -> dict[str, Any]:
    """Last event with event_timestamp <= snap_ts. Events must already be I(t)-filtered."""
    chosen: dict[str, Any] | None = None
    for ev in events:
        clock = pbp_event_ts(ev)
        if clock is None or clock > snap_ts:
            continue
        if chosen is None:
            chosen = ev
            continue
        prev = pbp_event_ts(chosen)
        if prev is None or clock > prev:
            chosen = ev
            continue
        if clock == prev and int(ev.get("event_number") or 0) > int(chosen.get("event_number") or 0):
            chosen = ev
    if chosen is None:
        return {
            "status": "UNALIGNED",
            "slice": "UNALIGNED",
            "period": None,
            "clock": None,
            "period_remaining_s": None,
            "elapsed_game_seconds": None,
            "event_number": None,
            "event_timestamp": None,
            "available_at": None,
            "time_actual": None,
        }
    rem = clock_remaining_seconds(chosen.get("clock"))
    period = chosen.get("period")
    return {
        "status": "REAL",
        "slice": entry_slice(sport, period, rem),
        "period": period,
        "clock": chosen.get("clock"),
        "period_remaining_s": rem,
        "elapsed_game_seconds": elapsed_game_seconds(period, chosen.get("clock"), sport=sport),
        "event_number": chosen.get("event_number"),
        "event_timestamp": chosen.get("event_time") or chosen.get("event_timestamp"),
        "available_at": chosen.get("available_at"),
        "time_actual": chosen.get("time_actual") or chosen.get("event_timestamp"),
    }


def clock_snap(
    cfg: RollerConfig,
    internal_game_id: str,
    timestamp,
    *,
    as_of=None,
    end_of_day: bool = False,
    full_history: bool = False,
) -> dict[str, Any]:
    if as_of is None and not full_history:
        raise AsOfRequiredError("clock_snap requires as_of or full_history=True")
    snap_ts = parse_utc(timestamp) if not isinstance(timestamp, datetime) else timestamp
    if snap_ts is None:
        raise ValueError("clock_snap timestamp is unparseable")
    ident = load_identity(cfg)
    hit = ident[ident["internal_game_id"] == internal_game_id]
    if hit.empty:
        raise KeyError(internal_game_id)
    rec = hit.iloc[0].to_dict()
    sport, season = rec["sport"], rec["season"]
    try:
        pbp = load_dataset(cfg, sport, season, "pbp")
    except FileNotFoundError:
        events = []
    else:
        pbp = pbp[pbp["internal_game_id"] == internal_game_id] if not pbp.empty else pbp
        if full_history:
            events = event_records(project_events(pbp)) if not pbp.empty else []
        else:
            vis = events_visible(project_events(pbp), as_of, end_of_day=end_of_day) if not pbp.empty else []
            events = event_records(vis) if vis is not None and not getattr(vis, "empty", True) else []
    body = snap_events(events, snap_ts, sport=sport)
    cutoff = resolve_cutoff(as_of or timestamp, end_of_day=end_of_day)
    body.update(
        {
            "internal_game_id": internal_game_id,
            "sport": sport,
            "season": season,
            "snap_timestamp": to_iso(snap_ts),
            "as_of": None if full_history else to_iso(cutoff),
            "note": "last visible PBP with event_timestamp <= snap; not a fill",
        }
    )
    return body
