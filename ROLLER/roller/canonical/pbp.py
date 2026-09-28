"""Canonical monthly PBP CSVs. Raw source files stay untouched."""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from roller.config import RollerConfig
from roller.ingest.games import load_sport_games
from roller.ingest.pbp import (
    espn_plays_path,
    load_json,
    nba_pbp_live_path,
    nba_pbp_v3_path,
    parse_espn_plays,
    parse_nba_actions,
)
from roller.ingest.pointers import pointer_record, write_manifest
from roller.io_csv import write_csv
from roller.paths import canonical_dir, raw_dir
from roller.timeutil import now_utc_iso

PBP_COLUMNS = [
    "internal_game_id",
    "source_game_id",
    "event_number",
    "event_timestamp",
    "time_actual",
    "available_at",
    "ingested_at",
    "availability_quality",
    "timestamp_status",
    "period",
    "clock",
    "home_score",
    "away_score",
    "score_differential_home",
    "event_type",
    "event_description",
    "team_tricode",
    "possession",
    "person_id",
    "sub_type",
    "shot_result",
    "team_id",
    "player_name",
    "home_away",
    "source_dataset",
    "source_file_hash",
    "pipeline_version",
    "derived_at",
]


def canonicalize_pbp(
    cfg: RollerConfig,
    sport: str,
    season: str,
    identity: pd.DataFrame,
    games: pd.DataFrame,
) -> int:
    _, _, wh = load_sport_games(cfg, sport, season)
    path_key = cfg.season_meta(sport, season)["path_key"]
    now = now_utc_iso()
    by_id = {r["internal_game_id"]: r for r in identity.to_dict("records") if r["sport"] == sport and r["season"] == season}
    months: dict[str, list[dict]] = defaultdict(list)
    pointers = []

    for g in games.to_dict("records"):
        ident = by_id.get(g["internal_game_id"])
        if ident is None:
            continue
        src = g.get("source_game_id") or ""
        events: list[dict] = []
        src_path = None
        if sport == "NBA" and src:
            live_p = nba_pbp_live_path(wh, src)
            v3_p = nba_pbp_v3_path(wh, src)
            live = load_json(live_p)
            events = parse_nba_actions(live)
            if live_p.is_file():
                src_path = live_p
                pointers.append(pointer_record(live_p, "pbp_live"))
            elif v3_p.is_file():
                src_path = v3_p
                events = parse_nba_actions(load_json(v3_p))
                pointers.append(pointer_record(v3_p, "pbp_v3"))
        elif src:
            ep = espn_plays_path(wh, sport, src)
            events = parse_espn_plays(load_json(ep))
            if ep.is_file():
                src_path = ep
                pointers.append(pointer_record(ep, "espn_plays"))

        month = str(g.get("game_date") or "unknown")[:7]
        src_hash = ""
        if src_path is not None and src_path.is_file():
            from roller.io_csv import sha256_file

            src_hash = sha256_file(src_path)
        for e in events:
            rec = {
                "internal_game_id": g["internal_game_id"],
                "source_game_id": src,
                "event_number": e.get("event_number"),
                "event_timestamp": e.get("event_timestamp") or "",
                "time_actual": e.get("time_actual") or e.get("event_timestamp") or "",
                "available_at": e.get("available_at") or "",
                "ingested_at": now,
                "availability_quality": e.get("availability_quality") or "",
                "timestamp_status": e.get("timestamp_status") or "",
                "period": e.get("period"),
                "clock": e.get("clock") or "",
                "home_score": e.get("home_score"),
                "away_score": e.get("away_score"),
                "score_differential_home": e.get("score_differential_home"),
                "event_type": e.get("event_type") or "",
                "event_description": e.get("event_description") or "",
                "team_tricode": e.get("team_tricode") or "",
                "possession": e.get("possession") or "",
                "person_id": e.get("person_id") or "",
                "sub_type": e.get("sub_type") or "",
                "shot_result": e.get("shot_result") or "",
                "team_id": e.get("team_id") or "",
                "player_name": e.get("player_name") or "",
                "home_away": e.get("home_away") or "",
                "source_dataset": "pbp",
                "source_file_hash": src_hash,
                "pipeline_version": cfg.pipeline_version,
                "derived_at": now,
            }
            months[month].append(rec)

    out_dir = canonical_dir(cfg.root, sport, path_key) / "pbp"
    if out_dir.exists():
        for old in out_dir.glob("*.csv"):
            old.unlink()
    total = 0
    for month, recs in sorted(months.items()):
        df = pd.DataFrame(recs)
        if df.empty:
            continue
        df["_t"] = pd.to_datetime(df["available_at"], utc=True, errors="coerce")
        df = df.sort_values(
            ["internal_game_id", "_t", "event_number"],
            kind="mergesort",
            na_position="last",
        ).drop(columns=["_t"]).reset_index(drop=True)
        write_csv(out_dir / f"month={month}.csv", df, PBP_COLUMNS)
        total += len(df)
    write_manifest(raw_dir(cfg.root, sport, path_key) / "pbp" / "manifest.json", pointers)
    return total
