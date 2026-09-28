"""Read warehouse 1-minute candle parquet. Candles are observations, not fills."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pandas as pd


CANDLE_COLS = [
    "ticker",
    "event_id",
    "game_id",
    "end_period_ts",
    "start_time",
    "end_time",
    "yes_bid_open_e4",
    "yes_bid_high_e4",
    "yes_bid_low_e4",
    "yes_bid_close_e4",
    "yes_ask_open_e4",
    "yes_ask_high_e4",
    "yes_ask_low_e4",
    "yes_ask_close_e4",
    "volume_hundredths",
    "is_valid",
]


def candles_root(warehouse: Path, sport: str) -> Path:
    return warehouse / "normalized" / sport.lower() / "candles_1m"


def iter_candle_frames(warehouse: Path, sport: str) -> Iterator[tuple[str, pd.DataFrame]]:
    root = candles_root(warehouse, sport)
    if not root.is_dir():
        return
    months = sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("month="))
    for month_dir in months:
        month = month_dir.name.split("=", 1)[-1]
        files = sorted(month_dir.glob("*.parquet"))
        if not files:
            continue
        frames = []
        for f in files:
            frames.append(pd.read_parquet(f))
        if frames:
            yield month, pd.concat(frames, ignore_index=True)


def team_side(ticker: str, home_code: str, away_code: str) -> str:
    suffix = str(ticker).rsplit("-", 1)[-1]
    if suffix == home_code:
        return "home"
    if suffix == away_code:
        return "away"
    return ""
