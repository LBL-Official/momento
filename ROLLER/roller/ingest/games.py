"""Load warehouse game catalogs and PBP crosswalks (read-only)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from roller.config import RollerConfig
from roller.paths import warehouse_dir


def warehouse_layer(sport: str) -> str:
    return sport.lower()


def load_games_json(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    raise ValueError(f"unexpected games payload at {path}")


def load_crosswalk(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def games_json_path(wh: Path, sport: str) -> Path:
    layer = warehouse_layer(sport)
    return wh / "normalized" / layer / "games" / f"{layer}_games.json"


def crosswalk_path(wh: Path, sport: str) -> Path:
    layer = warehouse_layer(sport)
    return wh / "normalized" / layer / "pbp" / "game_crosswalk.json"


def source_id_field(sport: str) -> str:
    return {
        "NBA": "nba_game_id",
        "WNBA": "espn_game_id",
        "NCAAB": "espn_game_id",
        "MLB": "game_pk",
    }[sport]


def warehouse_available(cfg: RollerConfig, sport: str, season: str) -> bool:
    meta = cfg.season_meta(sport, season)
    wh = warehouse_dir(
        cfg.warehouse_root,
        meta["warehouse_sport"],
        meta["warehouse_season"],
    )
    return games_json_path(wh, meta["warehouse_sport"]).is_file()


def load_sport_games(cfg: RollerConfig, sport: str, season: str) -> tuple[list[dict], list[dict], Path]:
    meta = cfg.season_meta(sport, season)
    wh = warehouse_dir(
        cfg.warehouse_root,
        meta["warehouse_sport"],
        meta["warehouse_season"],
    )
    path = games_json_path(wh, meta["warehouse_sport"])
    if not path.is_file():
        return [], [], wh
    games = load_games_json(path)
    xwalk = load_crosswalk(crosswalk_path(wh, meta["warehouse_sport"]))
    campaign = meta.get("campaign_year")
    if campaign is not None:
        games = [g for g in games if _campaign_year(g.get("game_date")) == int(campaign)]
        keep = {g.get("event_id") or g.get("event_ticker") for g in games}
        xwalk = [r for r in xwalk if (r.get("event_id") or r.get("event_ticker")) in keep]
    return games, xwalk, wh


def _campaign_year(game_date: str | None) -> int | None:
    if not game_date or len(str(game_date)) < 7:
        return None
    y = int(str(game_date)[:4])
    m = int(str(game_date)[5:7])
    return y if m >= 5 else y - 1


def infer_market_tickers(
    game: dict[str, Any],
    home_code: str,
    away_code: str,
    canon=None,
) -> tuple[str, str]:
    """Prefer explicit home/away tickers; else split market_tickers by suffix code."""
    home_t = str(game.get("home_market_ticker") or "").strip()
    away_t = str(game.get("away_market_ticker") or "").strip()
    if home_t and away_t:
        return home_t, away_t
    for raw in game.get("market_tickers") or []:
        ticker = str(raw)
        suffix = ticker.rsplit("-", 1)[-1]
        mapped = canon(suffix) if canon else suffix
        if mapped == home_code or suffix == home_code:
            home_t = ticker
        elif mapped == away_code or suffix == away_code:
            away_t = ticker
    return home_t, away_t


def index_crosswalk(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        for key in (r.get("event_id"), r.get("event_ticker")):
            if key:
                out[str(key)] = r
    return out
