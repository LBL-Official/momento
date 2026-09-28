"""Pre-game team features. X_pre(i,g) = f(G_1..G_{g-1}) ordered by result_available_at."""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from roller.config import RollerConfig
from roller.features.engine import priors_before, rest_days, result_sort_key, summarize_priors, team_appearances
from roller.io_csv import write_csv
from roller.paths import derived_dir
from roller.timeutil import now_utc_iso

FEATURE_COLUMNS = [
    "internal_game_id",
    "sport",
    "season",
    "team_id",
    "is_home",
    "game_date",
    "scheduled_start",
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


def build_team_features(
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
    all_apps: list[dict] = []
    for g in records:
        for app in team_appearances(g):
            all_apps.append(app)
            if app["has_result"]:
                completed_by_team[app["team_id"]].append(app)
    for team, apps in completed_by_team.items():
        completed_by_team[team] = sorted(apps, key=result_sort_key)

    rows = []
    for app in all_apps:
        team = app["team_id"]
        completed = completed_by_team.get(team, [])
        priors = priors_before(completed, app)

        stats, prev_date = summarize_priors(priors, team, windows)
        avail = priors[-1]["result_available_at"] if priors else (app["scheduled_start"] or app["game_date"])
        rows.append(
            {
                "internal_game_id": app["internal_game_id"],
                "sport": sport,
                "season": season,
                "team_id": team,
                "is_home": "1" if app["is_home"] else "0",
                "game_date": app["game_date"],
                "scheduled_start": app["scheduled_start"],
                **stats,
                "rest_days": rest_days(prev_date, app["game_date"]),
                "event_timestamp": app["scheduled_start"] or app["game_date"],
                "available_at": avail,
                "ingested_at": now,
                "source_dataset": "games",
                "source_file_hash": source_hash,
                "pipeline_version": cfg.pipeline_version,
                "derived_at": now,
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=FEATURE_COLUMNS)
    else:
        df = df.sort_values(["game_date", "internal_game_id", "team_id"]).reset_index(drop=True)
        df = df[FEATURE_COLUMNS]
    path_key = cfg.season_meta(sport, season)["path_key"]
    write_csv(derived_dir(cfg.root, sport, path_key) / "team_game_features.csv", df, FEATURE_COLUMNS)
    return df
