"""D2D information states: I(d) using result_available_at < UTCStart(d)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

import pandas as pd

from roller.config import RollerConfig
from roller.features.engine import rest_days, result_sort_key, summarize_priors, team_appearances
from roller.io_csv import write_csv
from roller.paths import derived_dir
from roller.timeutil import UTC, now_utc_iso, parse_utc

D2D_COLUMNS = [
    "as_of_date",
    "sport",
    "season",
    "team_id",
    "games_played_pre",
    "wins_pre",
    "losses_pre",
    "win_pct_pre",
    "home_games_pre",
    "home_wins_pre",
    "away_games_pre",
    "away_wins_pre",
    "wins_last_5_pre",
    "losses_last_5_pre",
    "wins_last_10_pre",
    "losses_last_10_pre",
    "rest_days",
    "event_timestamp",
    "available_at",
    "ingested_at",
    "source_dataset",
    "source_file_hash",
    "pipeline_version",
    "derived_at",
]


def utc_start(date_s: str) -> datetime:
    return datetime(int(date_s[:4]), int(date_s[5:7]), int(date_s[8:10]), tzinfo=UTC)


def build_d2d_daily(
    cfg: RollerConfig,
    sport: str,
    season: str,
    games: pd.DataFrame,
    source_hash: str = "",
) -> pd.DataFrame:
    windows = list(cfg.features.get("team_features", {}).get("rolling_windows") or [5, 10])
    now = now_utc_iso()
    records = games.to_dict("records") if not games.empty else []
    if sport == "NCAAB":
        records = [g for g in records if str(g.get("p5_vs_p5") or "") == "1"]

    completed_by_team: dict[str, list[dict]] = defaultdict(list)
    teams = set()
    dates = set()
    for g in records:
        if g.get("game_date"):
            dates.add(str(g["game_date"])[:10])
        for app in team_appearances(g):
            teams.add(app["team_id"])
            if app["has_result"]:
                completed_by_team[app["team_id"]].append(app)
    for team, apps in completed_by_team.items():
        completed_by_team[team] = sorted(apps, key=result_sort_key)

    rows = []
    for date_s in sorted(dates):
        cutoff = utc_start(date_s)
        for team in sorted(teams):
            priors = []
            for p in completed_by_team.get(team, []):
                ts = parse_utc(p["result_available_at"])
                if ts is not None and ts < cutoff:
                    priors.append(p)
            stats, prev_date = summarize_priors(priors, team, windows)
            avail = priors[-1]["result_available_at"] if priors else ""
            rows.append(
                {
                    "as_of_date": date_s,
                    "sport": sport,
                    "season": season,
                    "team_id": team,
                    "event_timestamp": date_s,
                    "available_at": avail,
                    "ingested_at": now,
                    "rest_days": rest_days(prev_date, date_s),
                    **stats,
                    "source_dataset": "games",
                    "source_file_hash": source_hash,
                    "pipeline_version": cfg.pipeline_version,
                    "derived_at": now,
                }
            )

    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=D2D_COLUMNS)
    else:
        df = df.sort_values(["as_of_date", "team_id"]).reset_index(drop=True)
        df = df[D2D_COLUMNS]
    path_key = cfg.season_meta(sport, season)["path_key"]
    write_csv(derived_dir(cfg.root, sport, path_key) / "d2d_daily.csv", df, D2D_COLUMNS)
    return df


def write_terminal_game_state(
    cfg: RollerConfig,
    sport: str,
    season: str,
    games: pd.DataFrame,
    source_hash: str = "",
) -> pd.DataFrame:
    """Terminal labels only — explicit *_terminal names."""
    now = now_utc_iso()
    rows = []
    for g in games.to_dict("records") if not games.empty else []:
        rows.append(
            {
                "internal_game_id": g["internal_game_id"],
                "home_score_terminal": g.get("final_home_score") or "",
                "away_score_terminal": g.get("final_away_score") or "",
                "home_win_terminal": g.get("home_win") or "",
                "away_win_terminal": g.get("away_win") or "",
                "result_available_at": g.get("result_available_at") or "",
                "event_timestamp": g.get("event_timestamp") or "",
                "available_at": g.get("result_available_at") or "",
                "ingested_at": now,
                "source_dataset": "games",
                "source_file_hash": source_hash,
                "pipeline_version": cfg.pipeline_version,
                "derived_at": now,
            }
        )
    cols = [
        "internal_game_id",
        "home_score_terminal",
        "away_score_terminal",
        "home_win_terminal",
        "away_win_terminal",
        "result_available_at",
        "event_timestamp",
        "available_at",
        "ingested_at",
        "source_dataset",
        "source_file_hash",
        "pipeline_version",
        "derived_at",
    ]
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=cols)
    else:
        df = df[cols]
    path_key = cfg.season_meta(sport, season)["path_key"]
    write_csv(derived_dir(cfg.root, sport, path_key) / "game_state_features.csv", df, cols)
    return df
