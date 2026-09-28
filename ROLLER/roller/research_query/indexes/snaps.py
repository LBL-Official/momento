"""PBP as-of facts. Last event with event_time <= observation_time. Never future-looking.

Store the source event fields (score, inning, period, clock). The index is not a
precomputed snap answer — detectors still choose the as-of row at query time.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from roller.timeutil import parse_utc

SNAPS_NAME = "pbp_events.parquet"


def _event_ts(rec: dict[str, Any]):
    return parse_utc(
        rec.get("event_time")
        or rec.get("event_timestamp")
        or rec.get("ts")
        or rec.get("available_at")
        or rec.get("time_actual")
    )


def _cell(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    return json.dumps(value, default=str)


def write_snaps(path: Path, pbp_by_game: dict[str, list[dict[str, Any]]]) -> int:
    rows: list[dict[str, Any]] = []
    for gid, events in pbp_by_game.items():
        for ev in events:
            ts = _event_ts(ev)
            if ts is None:
                continue
            ts_iso = ts.isoformat().replace("+00:00", "Z")
            row = {str(k): _cell(v) for k, v in ev.items()}
            row["game_id"] = gid
            row["event_ts"] = ts_iso
            row.setdefault("internal_game_id", gid)
            row.setdefault("event_time", ts_iso)
            row.setdefault("event_timestamp", ts_iso)
            rows.append(row)
    pd.DataFrame(rows).to_parquet(path, index=False)
    return len(rows)


def _clean(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def read_snaps(path: Path) -> dict[str, list[dict[str, Any]]]:
    df = pd.read_parquet(path)
    out: dict[str, list[dict[str, Any]]] = {}
    if df.empty:
        return out
    for rec in df.to_dict("records"):
        row = {str(k): _clean(v) for k, v in rec.items()}
        gid = str(row.get("game_id") or row.get("internal_game_id") or "")
        ts = row.get("event_ts") or row.get("event_time") or row.get("event_timestamp")
        row["internal_game_id"] = row.get("internal_game_id") or gid
        row["event_time"] = row.get("event_time") or ts
        row["event_timestamp"] = row.get("event_timestamp") or ts
        out.setdefault(gid, []).append(row)
    from roller.research_query.entry_engine import order_pbp_events

    return {gid: order_pbp_events(events) for gid, events in out.items()}
