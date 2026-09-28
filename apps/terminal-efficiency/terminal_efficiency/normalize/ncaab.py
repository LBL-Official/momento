"""Normalize NCAAB ESPN scoreboard games and observed-wallclock PBP."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from terminal_efficiency.clocks import parse_iso_duration_seconds, parse_utc, seconds_remaining_game, to_iso
from terminal_efficiency.config import LeagueConfig
from terminal_efficiency.constants import QUALITY_OBSERVED, QUALITY_UNAVAILABLE
from terminal_efficiency.paths import derived_root, warehouse
from terminal_efficiency.provenance import write_json


def load_ncaab_games(season: str) -> pd.DataFrame:
    path = warehouse("NCAAB", season) / "normalized" / "ncaab" / "games" / "ncaab_games.json"
    if not path.exists():
        return pd.DataFrame()
    rows = json.loads(path.read_text())
    for r in rows:
        r["league"] = "NCAAB"
        r["season"] = season
        r["game_id"] = str(r.get("espn_game_id") or r.get("game_id") or "")
        start = parse_utc(r.get("scheduled_start"))
        r["scheduled_start"] = to_iso(start) if start else (r.get("scheduled_start") or "")
        # result available at end unknown; conservative same calendar day 23:59Z if final
        if r.get("final_home_score") is not None and start:
            r["result_available_at"] = to_iso(start)  # replaced below if we have last play
        else:
            r["result_available_at"] = r.get("scheduled_start") or ""
        r["final_home_win"] = bool(r.get("home_win")) if r.get("home_win") is not None else None
    df = pd.DataFrame(rows)
    if not df.empty:
        dest = derived_root("NCAAB", season) / "games.parquet"
        df.to_parquet(dest, index=False)
        write_json(derived_root("NCAAB", season) / "games_manifest.json", {"n": int(len(df))})
    return df


def normalize_espn_plays(game: dict, cfg: LeagueConfig, plays_path: Path) -> list[dict]:
    if not plays_path.exists():
        return []
    payload = json.loads(plays_path.read_text())
    plays = payload.get("plays") or []
    if payload.get("status") == "EMPTY":
        return []
    rows = []
    last_hs = 0
    last_as = 0
    last_wall = parse_utc(game.get("scheduled_start"))
    for i, p in enumerate(plays):
        if not isinstance(p, dict):
            continue
        period = int((p.get("period") or {}).get("number") or p.get("period") or 1)
        clock = str(p.get("clock") or (p.get("clock") or {}).get("displayValue") or "")
        if isinstance(p.get("clock"), dict):
            clock = str(p["clock"].get("displayValue") or "")
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
        hs = p.get("homeScore", last_hs)
        aws = p.get("awayScore", last_as)
        try:
            hs, aws = int(hs), int(aws)
        except (TypeError, ValueError):
            hs, aws = last_hs, last_as
        last_hs, last_as = hs, aws
        wall = parse_utc(p.get("wallclock") or p.get("wallClock"))
        quality = QUALITY_OBSERVED if wall else QUALITY_UNAVAILABLE
        if wall is None:
            wall = last_wall
        else:
            last_wall = wall
        team = ((p.get("team") or {}).get("abbreviation")) or ""
        rows.append(
            {
                "game_id": game["game_id"],
                "league": "NCAAB",
                "season": game.get("season"),
                "event_number": int(p.get("sequenceNumber") or i + 1),
                "period": period,
                "clock": clock,
                "seconds_remaining_period": float(srp),
                "seconds_remaining_game": float(srg),
                "home_score": hs,
                "away_score": aws,
                "score_difference": hs - aws,
                "team_tricode": str(team),
                "person_id": None,
                "player_name": "",
                "action_type": str(p.get("type_text") or (p.get("type") or {}).get("text") or ""),
                "sub_type": "",
                "shot_result": "",
                "description": str(p.get("text") or ""),
                "event_timestamp": to_iso(wall),
                "available_at": to_iso(wall),
                "timestamp_quality": quality,
                "raw_event_id": str(p.get("id") or i),
            }
        )
    return rows


def load_all_ncaab_events(games: pd.DataFrame, cfg: LeagueConfig, season: str) -> list[dict]:
    plays_dir = warehouse("NCAAB", season) / "normalized" / "ncaab" / "pbp" / "plays"
    events = []
    for g in games.to_dict("records"):
        if not g.get("p5_vs_p5"):
            continue
        events.extend(normalize_espn_plays(g, cfg, plays_dir / f"{g['game_id']}.json"))
    return events
