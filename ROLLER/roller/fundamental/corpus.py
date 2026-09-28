"""Prior-only fundamental state corpus. Not a public PIT dataset. Always re-filter."""

from __future__ import annotations

from typing import Any

import pandas as pd

from roller.admin import load_dataset
from roller.config import RollerConfig
from roller.fundamental.conditioning import condition_state
from roller.fundamental.eligibility import fundamental_eligible
from roller.fundamental.orientation import y_home_win
from roller.io_csv import read_csv_optional, write_csv
from roller.paths import derived_dir
from roller.state.clock import elapsed_game_seconds
from roller.timeutil import parse_utc

CORPUS_CONSTRUCTION_VERSION = "pbp_last_per_clock_bucket_v1"

CORPUS_COLUMNS = [
    "internal_game_id",
    "sport",
    "season",
    "home_team_id",
    "away_team_id",
    "observation_time",
    "state_available_at",
    "result_available_at",
    "period",
    "clock",
    "elapsed_game_seconds",
    "home_score",
    "away_score",
    "score_differential_home",
    "clock_bucket",
    "score_margin_bucket",
    "condition_id",
    "conditioning_schema_version",
    "home_win",
    "y_home_win",
    "construction_version",
]


def corpus_path(cfg: RollerConfig, sport: str, season: str):
    path_key = cfg.season_meta(sport, season)["path_key"]
    return derived_dir(cfg.root, sport, path_key) / "v4a_fundamental_state_corpus.csv"


def load_fundamental_corpus(cfg: RollerConfig, sport: str, season: str) -> list[dict[str, Any]]:
    path = corpus_path(cfg, sport, season)
    df = read_csv_optional(path, columns=CORPUS_COLUMNS)
    if df.empty:
        return []
    return df.to_dict("records")


def filter_eligible(
    rows: list[dict[str, Any]],
    *,
    current_game_id: str,
    cutoff,
    condition_id: str | None = None,
) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        if condition_id is not None and row.get("condition_id") != condition_id:
            continue
        if y_home_win(row.get("home_win")) is None:
            continue
        if not fundamental_eligible(row, current_game_id=current_game_id, cutoff=cutoff):
            continue
        out.append(row)
    return out


def _clock_bucket(elapsed: Any, width: int) -> str | None:
    from roller.measurement.conditioning import _width_bucket

    return _width_bucket(elapsed, width)


def build_state_rows(
    cfg: RollerConfig,
    *,
    games: pd.DataFrame,
    pbp: pd.DataFrame,
    sport: str,
    season: str,
    schema_version: str | None = None,
) -> list[dict[str, Any]]:
    if games is None or games.empty or pbp is None or pbp.empty:
        return []
    spec = (cfg.fundamental_conditioning or {}).get("schemas") or {}
    core = spec.get(schema_version or (cfg.fundamental_conditioning or {}).get("default_schema") or "core_v1") or {}
    width = 60
    for dim in core.get("dimensions") or []:
        if dim.get("name") == "clock_bucket":
            width = int(dim.get("width") or 60)
    games_by_id = {str(g["internal_game_id"]): g for g in games.to_dict("records")}
    rows: list[dict[str, Any]] = []
    grouped = pbp.groupby("internal_game_id", sort=False)
    for gid, gp in grouped:
        game = games_by_id.get(str(gid))
        if game is None:
            continue
        if sport == "NCAAB" and str(game.get("p5_vs_p5") or "") != "1":
            continue
        y = y_home_win(game.get("home_win"))
        result_at = str(game.get("result_available_at") or "").strip()
        if y is None or not result_at or parse_utc(result_at) is None:
            continue
        last_in_bucket: dict[tuple[str, str], dict[str, Any]] = {}
        recs = gp.to_dict("records")
        recs.sort(key=lambda r: (str(r.get("available_at") or ""), int(r.get("event_number") or 0)))
        for ev in recs:
            elapsed = elapsed_game_seconds(ev.get("period"), ev.get("clock"), sport=sport)
            bucket = _clock_bucket(elapsed, width)
            period = None if ev.get("period") in (None, "") else str(ev.get("period"))
            if period is None or bucket is None or elapsed is None:
                continue
            last_in_bucket[(period, bucket)] = ev
        for ev in last_in_bucket.values():
            elapsed = elapsed_game_seconds(ev.get("period"), ev.get("clock"), sport=sport)
            state = {
                "period": ev.get("period"),
                "elapsed_game_seconds": elapsed,
                "score_differential_home": ev.get("score_differential_home"),
            }
            cond = condition_state(cfg, state, schema_version=schema_version)
            if cond["status"] != "valid":
                continue
            state_at = str(ev.get("available_at") or "").strip()
            if not state_at:
                continue
            dims = cond["dimensions"]
            rows.append(
                {
                    "internal_game_id": str(gid),
                    "sport": sport,
                    "season": season,
                    "home_team_id": game.get("home_team_id") or "",
                    "away_team_id": game.get("away_team_id") or "",
                    "observation_time": state_at,
                    "state_available_at": state_at,
                    "result_available_at": result_at,
                    "period": ev.get("period"),
                    "clock": ev.get("clock"),
                    "elapsed_game_seconds": elapsed,
                    "home_score": ev.get("home_score"),
                    "away_score": ev.get("away_score"),
                    "score_differential_home": ev.get("score_differential_home"),
                    "clock_bucket": dims.get("clock_bucket"),
                    "score_margin_bucket": dims.get("score_margin_bucket"),
                    "condition_id": cond["condition_id"],
                    "conditioning_schema_version": cond["conditioning_schema_version"],
                    "home_win": game.get("home_win"),
                    "y_home_win": y,
                    "construction_version": CORPUS_CONSTRUCTION_VERSION,
                }
            )
    rows.sort(key=lambda r: (str(r.get("result_available_at") or ""), str(r.get("internal_game_id") or ""), str(r.get("state_available_at") or "")))
    return rows


def write_fundamental_corpus(cfg: RollerConfig, sport: str, season: str) -> pd.DataFrame:
    if sport not in {"NBA", "WNBA", "NCAAB"}:
        return pd.DataFrame(columns=CORPUS_COLUMNS)
    try:
        games = load_dataset(cfg, sport, season, "games")
        pbp = load_dataset(cfg, sport, season, "pbp")
    except FileNotFoundError:
        return pd.DataFrame(columns=CORPUS_COLUMNS)
    rows = build_state_rows(cfg, games=games, pbp=pbp, sport=sport, season=season)
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=CORPUS_COLUMNS)
    write_csv(corpus_path(cfg, sport, season), df, CORPUS_COLUMNS)
    return df
