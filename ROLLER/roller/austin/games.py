"""Query-universe game catalog. Not the 604 training lock."""

from __future__ import annotations

import csv
from functools import lru_cache
from typing import Any

import pandas as pd

from roller.austin.errors import AustinError
from roller.austin.instances import load_trades
from roller.austin.locks import N_TRADES
from roller.choosin_texas.sources import default_asked_six_csv
from roller.config import RollerConfig
from roller.warehouse.layout import games_path, links_path, markets_path


def _cfg() -> RollerConfig:
    return RollerConfig()


@lru_cache(maxsize=1)
def locked_tickers() -> set[str]:
    return {str(row["ticker"]) for row in load_trades()}


@lru_cache(maxsize=1)
def asked_six_entries() -> dict[str, dict[str, Any]]:
    """All NBA FIRST80 rows in asked-six. Not an Austin N."""
    path = default_asked_six_csv()
    out: dict[str, dict[str, Any]] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            if str(rec.get("sport") or "").strip() != "NBA":
                continue
            ticker = str(rec.get("ticker") or "").strip()
            if not ticker:
                continue
            out[ticker] = {
                "ticker": ticker,
                "event_id": str(rec.get("event_id") or rec.get("game_id") or ticker),
                "side": str(rec.get("side") or "").strip().lower(),
                "entry_timestamp": str(rec.get("timestamp_utc") or "").strip(),
                "entry_price_cents": rec.get("market_yes_bid"),
                "home_score_entry": rec.get("score_home"),
                "away_score_entry": rec.get("score_away"),
                "entry_seconds_remaining": rec.get("period_remaining_s"),
                "slice": str(rec.get("slice") or "").strip(),
                "quarter": rec.get("period") or rec.get("quarter") or rec.get("slice"),
            }
    return out


@lru_cache(maxsize=1)
def load_game_catalog() -> list[dict[str, Any]]:
    cfg = _cfg()
    gpath = games_path(cfg)
    mpath = markets_path(cfg)
    lpath = links_path(cfg)
    if not gpath.is_file() or not mpath.is_file():
        raise AustinError("DATA_REQUIRED", f"missing warehouse games/markets under {gpath.parent}")
    games = pd.read_parquet(gpath)
    markets = pd.read_parquet(mpath)
    locked = locked_tickers()
    by_game: dict[str, dict[str, str]] = {}
    locked_games: set[str] = set()
    for rec in markets.itertuples(index=False):
        gid = str(getattr(rec, "internal_game_id", "") or "")
        ticker = str(getattr(rec, "ticker", "") or "")
        side = str(getattr(rec, "team_side", "") or "")
        if not gid or not ticker:
            continue
        by_game.setdefault(gid, {})[side or ticker] = ticker
        if ticker in locked:
            locked_games.add(gid)
    rows = []
    for rec in games.itertuples(index=False):
        gid = str(getattr(rec, "internal_game_id", "") or "")
        if not gid:
            continue
        sides = by_game.get(gid) or {}
        rows.append(
            {
                "internal_game_id": gid,
                "game_date": str(getattr(rec, "game_date", "") or ""),
                "home_team_id": str(getattr(rec, "home_team_id", "") or ""),
                "away_team_id": str(getattr(rec, "away_team_id", "") or ""),
                "home_team_name": str(getattr(rec, "home_team_name", "") or ""),
                "away_team_name": str(getattr(rec, "away_team_name", "") or ""),
                "event_ticker": str(getattr(rec, "event_ticker", "") or ""),
                "home_ticker": sides.get("home"),
                "away_ticker": sides.get("away"),
                "in_austin_604": gid in locked_games,
                "model_universe": gid in locked_games,
            }
        )
    rows.sort(key=lambda r: (r["game_date"], r["internal_game_id"]))
    _ = lpath
    return rows


def get_game(game_id: str) -> dict[str, Any]:
    wanted = str(game_id or "").strip()
    for row in load_game_catalog():
        if row["internal_game_id"] == wanted:
            return row
        if row.get("home_ticker") == wanted or row.get("away_ticker") == wanted:
            return row
        if row.get("event_ticker") == wanted:
            return row
    raise AustinError("DATA_REQUIRED", f"unknown game {game_id}")


def catalog_payload() -> dict[str, Any]:
    rows = load_game_catalog()
    return {
        "status": "OBSERVED",
        "model_universe": "choosin_nba_2q3q_604",
        "model_n": N_TRADES,
        "query_universe": "nba_warehouse_games",
        "n_query_games": len(rows),
        "n_in_austin_604": sum(1 for r in rows if r["in_austin_604"]),
        "note": "Historical N=604 is the training lock. Allowed query games are warehouse NBA games.",
        "live_feed": "UNAVAILABLE",
        "submits": False,
        "games": rows,
    }
