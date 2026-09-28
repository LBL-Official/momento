"""Market state uses integer E4 candles. Candle path is not a fill."""

from __future__ import annotations

from pathlib import Path

from roller import Roller
from roller.config import RollerConfig
from roller.maintenance.update import update_sport


def test_market_state_is_integer_e4_and_backward(roller_env: Path):
    cfg = RollerConfig(roller_env)
    update_sport(cfg, "NBA", "2025-2026", include_pbp=True, include_candles=True)
    db = Roller(roller_env)
    before = db.observation("NBA_20251220_LAL_BOS", as_of="2025-12-20T20:13:00Z")
    assert before["MARKET_STATE"]["status"] in {"REAL", "PARTIAL"}
    mid = db.observation("NBA_20251220_LAL_BOS", as_of="2025-12-20T20:14:00Z")
    after = db.observation("NBA_20251220_LAL_BOS", as_of="2025-12-20T20:16:00Z")
    later = after["MARKET_STATE"]["data"]
    assert later is not None
    close = later.get("yes_bid_close")
    assert close not in (None, "")
    assert str(close).isdigit()
    assert later.get("market_data_type") == "CANDLESTICK_TOP_OF_BOOK"
    mid_data = mid["MARKET_STATE"]["data"]
    if mid_data:
        assert mid_data.get("yes_bid_close") != close or before["MARKET_STATE"]["data"] is None
