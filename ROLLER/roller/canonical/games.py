"""Canonical games.csv from warehouse catalog + box/PBP scores."""

from __future__ import annotations

import pandas as pd

from roller.config import RollerConfig
from roller.ingest.games import index_crosswalk, load_sport_games, source_id_field
from roller.ingest.pbp import (
    box_scores,
    espn_plays_path,
    last_scored_result,
    load_json,
    nba_box_path,
    nba_pbp_live_path,
    parse_espn_plays,
    parse_nba_actions,
)
from roller.ingest.pointers import pointer_record, write_manifest
from roller.io_csv import sha256_file, write_csv
from roller.paths import canonical_dir, ensure_season_dirs, raw_dir
from roller.research.game_window import game_window
from roller.timeutil import now_utc_iso

GAMES_COLUMNS = [
    "internal_game_id",
    "sport",
    "season",
    "league",
    "game_date",
    "scheduled_start",
    "actual_start",
    "home_team_id",
    "away_team_id",
    "home_team_name",
    "away_team_name",
    "source_game_id",
    "warehouse_game_id",
    "event_ticker",
    "final_home_score",
    "final_away_score",
    "home_win",
    "away_win",
    "p5_vs_p5",
    "game_window_start",
    "game_window_end",
    "identity_available_at",
    "availability_quality",
    "result_available_at",
    "event_timestamp",
    "available_at",
    "ingested_at",
    "source_dataset",
    "source_file_hash",
    "pipeline_version",
    "derived_at",
]


def canonicalize_games(
    cfg: RollerConfig,
    sport: str,
    season: str,
    identity: pd.DataFrame,
) -> pd.DataFrame:
    ensure_season_dirs(cfg.root, sport, cfg.season_meta(sport, season)["path_key"])
    games, xwalk, wh = load_sport_games(cfg, sport, season)
    by_event = index_crosswalk(xwalk)
    src_field = source_id_field(sport)
    id_map = identity[identity["sport"] == sport]
    id_map = id_map[id_map["season"] == season]
    by_ticker = {r["event_ticker"]: r for r in id_map.to_dict("records")}
    now = now_utc_iso()
    pointers = []
    games_path = None
    from roller.ingest.games import games_json_path

    gj = games_json_path(wh, cfg.season_meta(sport, season)["warehouse_sport"])
    if gj.is_file():
        pointers.append(pointer_record(gj, "games"))
        games_path = gj
    source_hash = sha256_file(games_path) if games_path and games_path.is_file() else ""

    rows = []
    for g in games:
        ev = str(g.get("event_ticker") or g.get("event_id") or "")
        ident = by_ticker.get(ev)
        if ident is None:
            continue
        cw = by_event.get(ev) or {}
        src = ident.get("source_game_id") or cw.get(src_field) or ""
        home = ident["home_team_id"]
        away = ident["away_team_id"]
        start = g.get("scheduled_start") or ""
        ident_at = start
        if not ident_at and ident.get("game_date"):
            ident_at = f"{str(ident['game_date'])[:10]}T00:00:00Z"
        tip = start or ident_at
        hs = as_ = None
        result_at = ""
        if sport == "NBA" and src:
            box = load_json(nba_box_path(wh, src))
            bhs, bas, btip = box_scores(box)
            if btip:
                tip = btip
            if bhs is not None:
                hs = bhs
            if bas is not None:
                as_ = bas
            live = load_json(nba_pbp_live_path(wh, src))
            events = parse_nba_actions(live)
            _hs, _as, wall = last_scored_result(events)
            if wall:
                result_at = wall
            if hs is None:
                hs = _hs
            if as_ is None:
                as_ = _as
        else:
            plays = load_json(espn_plays_path(wh, sport, src)) if src else None
            events = parse_espn_plays(plays)
            hs, as_, wall = last_scored_result(events)
            if wall:
                result_at = wall

        home_win = away_win = ""
        if hs is not None and as_ is not None:
            home_win = "1" if hs > as_ else "0"
            away_win = "1" if as_ > hs else "0"

        p5 = ""
        if sport == "NCAAB":
            p5 = "1" if cfg.is_p5_vs_p5(sport, season, home, away) else "0"
        gw_start, gw_end = game_window(ident["game_date"])

        rows.append(
            {
                "internal_game_id": ident["internal_game_id"],
                "sport": sport,
                "season": season,
                "league": sport,
                "game_date": ident["game_date"],
                "scheduled_start": start,
                "actual_start": tip,
                "home_team_id": home,
                "away_team_id": away,
                "home_team_name": ident.get("home_team_name") or "",
                "away_team_name": ident.get("away_team_name") or "",
                "source_game_id": src,
                "warehouse_game_id": ident.get("warehouse_game_id") or "",
                "event_ticker": ev,
                "final_home_score": "" if hs is None else str(hs),
                "final_away_score": "" if as_ is None else str(as_),
                "home_win": home_win,
                "away_win": away_win,
                "p5_vs_p5": p5,
                "game_window_start": gw_start,
                "game_window_end": gw_end,
                "identity_available_at": ident_at,
                "availability_quality": "CONSERVATIVE_PROXY",
                "result_available_at": result_at,
                "event_timestamp": tip or start,
                "available_at": ident_at,
                "ingested_at": now,
                "source_dataset": "warehouse_games",
                "source_file_hash": source_hash,
                "pipeline_version": cfg.pipeline_version,
                "derived_at": now,
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=GAMES_COLUMNS)
    else:
        df = df.sort_values(["game_date", "scheduled_start", "internal_game_id"]).reset_index(drop=True)
        df = df[GAMES_COLUMNS]
    path_key = cfg.season_meta(sport, season)["path_key"]
    out = canonical_dir(cfg.root, sport, path_key) / "games.csv"
    write_csv(out, df, GAMES_COLUMNS)
    write_manifest(raw_dir(cfg.root, sport, path_key) / "games" / "manifest.json", pointers)
    return df
