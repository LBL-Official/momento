"""Path helpers driven by roller.json and season metadata."""

from __future__ import annotations

import os
from pathlib import Path


def find_root(start: Path | None = None) -> Path:
    env = os.environ.get("ROLLER_ROOT")
    if env:
        return Path(env).resolve()
    here = (start or Path(__file__).resolve()).parent
    for p in [here, *here.parents]:
        if (p / "roller.json").is_file():
            return p
    raise FileNotFoundError("roller.json not found; set ROLLER_ROOT")


def momento_root(roller_root: Path) -> Path:
    return roller_root.parent


def sport_dir(sport: str) -> str:
    return sport.lower()


def season_path_key(label: str) -> str:
    return label.replace("-", "_")


def season_data_dir(root: Path, sport: str, path_key: str) -> Path:
    return root / "data" / sport_dir(sport) / path_key


def canonical_dir(root: Path, sport: str, path_key: str) -> Path:
    return season_data_dir(root, sport, path_key) / "canonical"


def derived_dir(root: Path, sport: str, path_key: str) -> Path:
    return season_data_dir(root, sport, path_key) / "derived"


def raw_dir(root: Path, sport: str, path_key: str) -> Path:
    return season_data_dir(root, sport, path_key) / "raw"


def warehouse_dir(warehouse_root: Path, warehouse_sport: str, warehouse_season: str) -> Path:
    return warehouse_root / warehouse_sport / warehouse_season / "warehouse"


def ensure_season_dirs(root: Path, sport: str, path_key: str) -> None:
    base = season_data_dir(root, sport, path_key)
    for sub in (
        "raw/games",
        "raw/pbp",
        "raw/kalshi",
        "canonical/pbp",
        "canonical/kalshi_candles",
        "canonical/polymarket_candles",
        "raw/polymarket",
        "canonical/kalshi_trades",
        "canonical/kalshi_orderbook_snapshots",
        "raw/kalshi/orderbook",
        "derived",
    ):
        (base / sub).mkdir(parents=True, exist_ok=True)
