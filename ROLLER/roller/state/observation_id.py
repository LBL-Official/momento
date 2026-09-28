"""Deterministic observation identity. No random UUIDs."""

from __future__ import annotations

from datetime import datetime

from roller.timeutil import parse_utc_required


def compact_observation_time(observation_time) -> str:
    dt = observation_time if isinstance(observation_time, datetime) else parse_utc_required(observation_time)
    return dt.strftime("%Y%m%dT%H%M%S") + f"{dt.microsecond // 1000:03d}Z"


def make_observation_id(internal_game_id: str, observation_time, state_schema_version: str) -> str:
    compact = compact_observation_time(observation_time)
    return f"OBS_{internal_game_id}_{compact}_V{state_schema_version}"


def parse_observation_id(observation_id: str) -> tuple[str, datetime, str]:
    text = str(observation_id or "").strip()
    if not text.startswith("OBS_"):
        raise ValueError(f"invalid observation_id: {observation_id!r}")
    try:
        gid, compact, ver = text[4:].rsplit("_", 2)
    except ValueError as exc:
        raise ValueError(f"invalid observation_id: {observation_id!r}") from exc
    if not ver.startswith("V") or len(compact) != 19 or compact[8] != "T" or not compact.endswith("Z"):
        raise ValueError(f"invalid observation_id: {observation_id!r}")
    iso = f"{compact[0:4]}-{compact[4:6]}-{compact[6:8]}T{compact[9:11]}:{compact[11:13]}:{compact[13:15]}.{compact[15:18]}Z"
    return gid, parse_utc_required(iso), ver[1:]
