"""Normalize NBA PlayByPlayV3. Never invent timeActual."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from terminal_efficiency.clocks import parse_iso_duration_seconds, parse_utc, seconds_remaining_game, to_iso
from terminal_efficiency.config import LeagueConfig
from terminal_efficiency.constants import QUALITY_MODELED, QUALITY_OBSERVED, QUALITY_UNAVAILABLE
from terminal_efficiency.paths import warehouse

_PERIOD_WALL = re.compile(
    r"(Start|End) of .*Period \((\d{1,2}:\d{2})\s*(AM|PM)\s*([A-Z]{2,4})\)",
    re.I,
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _actions(payload: dict) -> list[dict]:
    game = payload.get("game") or payload
    return list(game.get("actions") or [])


def _parse_period_knots(actions: list[dict], scheduled_start: datetime | None) -> dict[int, dict[str, datetime]]:
    """Parse Start/End of period local times. Offset from scheduled_start date. MODELED."""
    knots: dict[int, dict[str, datetime]] = {}
    if scheduled_start is None:
        return knots
    for a in actions:
        desc = str(a.get("description") or "")
        m = _PERIOD_WALL.search(desc)
        if not m:
            continue
        kind = m.group(1).lower()
        hhmm, ampm = m.group(2), m.group(3).upper()
        hour, minute = map(int, hhmm.split(":"))
        hour = hour % 12
        if ampm == "PM":
            hour += 12
        period = int(a.get("period") or 0)
        # Use calendar date of scheduled_start; if clock is before 6am and start is evening, +1 day
        base = scheduled_start.astimezone(timezone.utc)
        local_naive = datetime(base.year, base.month, base.day, hour, minute)
        # Interpret as same UTC offset as scheduled_start (boxscore gameTimeUTC vs gameEt)
        est = local_naive.replace(tzinfo=timezone.utc) - timedelta(hours=5)
        # Better: keep as UTC-naive attached to game date + US/Eastern offset from start
        offset = scheduled_start.utcoffset() or timedelta(0)
        # Reconstruct: take game local date from gameEt if we only have UTC start
        wall = datetime(base.year, base.month, base.day, hour, minute, tzinfo=timezone.utc)
        # If description EST and start is ~00:00 UTC (7pm ET prev day), evening times belong to start-1 or start
        if hour >= 12:
            # evening: typically same local calendar as gameEt
            wall = datetime(scheduled_start.year, scheduled_start.month, scheduled_start.day, hour, minute)
            # scheduled_start is UTC; convert to ET-ish by subtracting 5h for date
            local_date = (scheduled_start - timedelta(hours=5)).date()
            wall = datetime(local_date.year, local_date.month, local_date.day, hour, minute, tzinfo=timezone.utc)
            wall = wall + timedelta(hours=5)  # treat printed clock as ET → UTC
        else:
            local_date = (scheduled_start - timedelta(hours=5)).date()
            if hour < 6:
                local_date = local_date + timedelta(days=1) if hour < 8 else local_date
            wall = datetime(local_date.year, local_date.month, local_date.day, hour, minute, tzinfo=timezone.utc)
            wall = wall + timedelta(hours=5)
        knots.setdefault(period, {})
        knots[period]["start" if kind == "start" else "end"] = wall
    return knots


def modeled_wall_time(
    period: int,
    seconds_remaining_period: float,
    knots: dict[int, dict[str, datetime]],
    period_seconds: int,
    ot_seconds: int,
) -> datetime | None:
    k = knots.get(period) or {}
    start, end = k.get("start"), k.get("end")
    if start is None or end is None:
        return None
    length = period_seconds if period <= 4 else ot_seconds
    elapsed = max(0.0, min(length, length - seconds_remaining_period))
    span = (end - start).total_seconds()
    if span <= 0:
        return start
    frac = elapsed / length if length else 0.0
    return start + timedelta(seconds=span * frac)


def normalize_nba_pbp_game(
    game: dict,
    cfg: LeagueConfig,
    pbp_path: Path,
) -> list[dict[str, Any]]:
    if not pbp_path.exists():
        return []
    payload = _load(pbp_path)
    actions = _actions(payload)
    start = parse_utc(game.get("scheduled_start"))
    knots = _parse_period_knots(actions, start)
    rows = []
    last_hs = 0
    last_as = 0
    for i, a in enumerate(actions):
        period = int(a.get("period") or 1)
        clock = str(a.get("clock") or "")
        srp = parse_iso_duration_seconds(clock)
        if srp is None:
            srp = 0.0
        srg = seconds_remaining_game(
            period,
            srp,
            regulation_periods=cfg.regulation_periods,
            period_seconds=cfg.period_seconds,
            ot_seconds=cfg.ot_seconds,
        )
        try:
            hs = int(a.get("scoreHome") or last_hs)
            aws = int(a.get("scoreAway") or last_as)
        except (TypeError, ValueError):
            hs, aws = last_hs, last_as
        last_hs, last_as = hs, aws
        wall = modeled_wall_time(period, srp, knots, cfg.period_seconds, cfg.ot_seconds)
        quality = QUALITY_MODELED if wall is not None else QUALITY_UNAVAILABLE
        if wall is None and start is not None:
            # monotonic proxy: start + elapsed game clock (ignores stoppages) — MODELED
            elapsed_game = (cfg.regulation_periods * cfg.period_seconds) - srg
            if period > cfg.regulation_periods:
                elapsed_game = cfg.regulation_periods * cfg.period_seconds + (period - cfg.regulation_periods) * cfg.ot_seconds - srp
            wall = start + timedelta(seconds=max(0.0, elapsed_game))
            quality = QUALITY_MODELED
        rows.append(
            {
                "game_id": game["game_id"],
                "league": "NBA",
                "season": game.get("season"),
                "event_number": int(a.get("actionNumber") or i + 1),
                "period": period,
                "clock": clock,
                "seconds_remaining_period": float(srp),
                "seconds_remaining_game": float(srg),
                "home_score": hs,
                "away_score": aws,
                "score_difference": hs - aws,
                "team_tricode": str(a.get("teamTricode") or ""),
                "person_id": a.get("personId"),
                "player_name": a.get("playerName") or "",
                "action_type": str(a.get("actionType") or ""),
                "sub_type": str(a.get("subType") or ""),
                "shot_result": str(a.get("shotResult") or ""),
                "description": str(a.get("description") or ""),
                "event_timestamp": to_iso(wall),
                "available_at": to_iso(wall),
                "timestamp_quality": quality,
                "raw_event_id": str(a.get("actionId") or a.get("actionNumber") or i),
            }
        )
    return rows


def load_all_nba_events(games: pd.DataFrame, cfg: LeagueConfig, season: str) -> list[dict]:
    pbp_dir = warehouse("NBA", season) / "raw" / "nba_stats" / "pbp_v3"
    events: list[dict] = []
    for g in games.to_dict("records"):
        events.extend(normalize_nba_pbp_game(g, cfg, pbp_dir / f"{g['game_id']}.json"))
    return events
