"""FIRST80 research objects. Off O_t. Candle path ≠ fill."""

from __future__ import annotations

from pathlib import Path

import pytest

from roller import Roller
from roller.config import RollerConfig
from roller.maintenance.update import update_sport
from roller.point_in_time.filters import FutureInformationError
from roller.research.first80 import build_first80_rows, scan_ticker
from roller.research.game_window import game_window
from roller.research.quality import HIT80, quality


def test_quality_spread_and_volume():
    assert quality(8000, 8500, 1, False) is True
    assert quality(8000, 9100, 1, False) is False
    assert quality(8100, 8000, 1, False) is False
    assert quality(8000, 8500, 0, False) is False
    assert quality(8000, 8500, 0, True) is True


def test_game_window_is_16h_to_52h():
    start, end = game_window("2025-12-20")
    assert start == "2025-12-20T16:00:00Z"
    assert end == "2025-12-22T04:00:00Z"


def test_scan_first80_then_t40():
    rows = [
        {"available_at": "2025-12-20T20:00:00Z", "yes_bid_close": 7000, "yes_ask_close": 7500, "volume": 10, "ticker": "T-BOS"},
        {"available_at": "2025-12-20T20:01:00Z", "yes_bid_close": 8000, "yes_ask_close": 8500, "volume": 10, "ticker": "T-BOS"},
        {"available_at": "2025-12-20T20:02:00Z", "yes_bid_close": 4000, "yes_ask_close": 4500, "volume": 10, "ticker": "T-BOS"},
    ]
    out = scan_ticker(rows, window_start=None, window_end=None)
    assert out["status"] == "FIRST_80"
    assert int(out["first_80_bid_close"]) == HIT80
    assert out["t40_timestamp"] == "2025-12-20T20:02:00Z"


def test_scan_requires_seen_below_80():
    rows = [
        {"available_at": "2025-12-20T20:00:00Z", "yes_bid_close": 8200, "yes_ask_close": 8500, "volume": 10, "ticker": "T-BOS"},
    ]
    assert scan_ticker(rows, window_start=None, window_end=None)["status"] == "NO_FIRST_80"


def test_tie_same_timestamp_excluded():
    games = __import__("pandas").DataFrame(
        [
            {
                "internal_game_id": "NBA_20251220_LAL_BOS",
                "sport": "NBA",
                "season": "2025-2026",
                "event_ticker": "EV",
                "game_date": "2025-12-20",
                "p5_vs_p5": "",
            }
        ]
    )
    candles = __import__("pandas").DataFrame(
        [
            {
                "internal_game_id": "NBA_20251220_LAL_BOS",
                "ticker": "EV-BOS",
                "team_side": "home",
                "available_at": "2025-12-20T20:01:00Z",
                "yes_bid_close": 7000,
                "yes_ask_close": 7500,
                "volume": 10,
            },
            {
                "internal_game_id": "NBA_20251220_LAL_BOS",
                "ticker": "EV-BOS",
                "team_side": "home",
                "available_at": "2025-12-20T20:02:00Z",
                "yes_bid_close": 8000,
                "yes_ask_close": 8500,
                "volume": 10,
            },
            {
                "internal_game_id": "NBA_20251220_LAL_BOS",
                "ticker": "EV-LAL",
                "team_side": "away",
                "available_at": "2025-12-20T20:01:00Z",
                "yes_bid_close": 6900,
                "yes_ask_close": 7400,
                "volume": 10,
            },
            {
                "internal_game_id": "NBA_20251220_LAL_BOS",
                "ticker": "EV-LAL",
                "team_side": "away",
                "available_at": "2025-12-20T20:02:00Z",
                "yes_bid_close": 8100,
                "yes_ask_close": 8600,
                "volume": 10,
            },
        ]
    )
    rows = build_first80_rows(
        sport="NBA",
        season="2025-2026",
        games=games,
        candles=candles,
        markets=__import__("pandas").DataFrame(),
        pbp=__import__("pandas").DataFrame(),
    )
    assert rows[0]["status"] == "TIE_SAME_MINUTE"


def test_first80_refused_by_dataset_and_off_observation(roller_env: Path):
    cfg = RollerConfig(roller_env)
    update_sport(cfg, "NBA", "2025-2026", include_pbp=True, include_candles=True)
    db = Roller(roller_env)
    with pytest.raises(FutureInformationError):
        db.dataset("NBA", "2025-2026", "first80_triggers", as_of="2025-12-21")
    obs = db.observation("NBA_20251220_LAL_BOS", as_of="2025-12-20T20:13:30Z")
    blob = str(obs)
    assert "FIRST80" not in blob
    assert "first80" not in blob
    labels = db.labels(observation_id=obs["observation_id"])
    names = {row["label_name"] for row in labels["labels"]}
    assert "first80_trigger" in names
    assert "first80_t40" in names
    assert "first80_entry_slice" in names
    assert "kalshi_yes_settled" in names
    book = db.first80(internal_game_id="NBA_20251220_LAL_BOS", as_of="2025-12-22T12:00:00Z")
    assert book["contains_future_information"] is True
    assert book["rows"]
