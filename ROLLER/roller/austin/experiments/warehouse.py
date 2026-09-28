"""NCAAB warehouse identity join. Not Confirm & Run."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import pandas as pd

from roller.config import RollerConfig
from roller.warehouse.layout import games_path, markets_path


@lru_cache(maxsize=1)
def join_ncaab_identity() -> dict[str, dict[str, Any]]:
    cfg = RollerConfig()
    mpath = markets_path(cfg, sport="NCAAB")
    gpath = games_path(cfg, sport="NCAAB")
    if not mpath.is_file():
        return {}
    markets = pd.read_parquet(mpath)
    games = pd.read_parquet(gpath) if gpath.is_file() else pd.DataFrame()
    game_event = {}
    if not games.empty:
        for rec in games.itertuples(index=False):
            gid = str(getattr(rec, "internal_game_id", "") or "")
            game_event[gid] = str(getattr(rec, "event_id", "") or getattr(rec, "event_ticker", "") or "")
    out: dict[str, dict[str, Any]] = {}
    for rec in markets.itertuples(index=False):
        ticker = str(getattr(rec, "ticker", "") or "")
        gid = str(getattr(rec, "internal_game_id", "") or "")
        if not ticker or not gid:
            continue
        out[ticker] = {
            "internal_game_id": gid,
            "event_id": game_event.get(gid) or str(getattr(rec, "event_ticker", "") or ""),
            "team_side": str(getattr(rec, "team_side", "") or ""),
        }
    return out


def ncaab_warehouse_present() -> bool:
    cfg = RollerConfig()
    return markets_path(cfg, sport="NCAAB").is_file()
