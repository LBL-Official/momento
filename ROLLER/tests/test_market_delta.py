"""Backward return lives on O_t. Forward market_response only via db.response."""

from __future__ import annotations

from pathlib import Path

from roller import Roller
from roller.config import RollerConfig
from roller.maintenance.update import update_sport


def test_backward_return_on_observation_not_response(roller_env: Path):
    cfg = RollerConfig(roller_env)
    update_sport(cfg, "NBA", "2025-2026", include_pbp=True, include_candles=True)
    db = Roller(roller_env)
    late = db.observation("NBA_20251220_LAL_BOS", as_of="2025-12-20T20:16:00Z")
    back = late["BACKWARD_MEASUREMENTS"]["data"]["measurements"]
    assert back["market_return_1m_backward"]["status"] == "valid"
    assert back["market_return_1m_backward"]["value"] == 130
    assert "market_response_1m" not in back
    assert "response" not in late
    y = db.response(late["observation_id"], measurement="market_response_1m", horizon="1m")
    assert y["contains_future_information"] is True
    assert y["measurement_name"] == "market_response_1m"
    assert y["response_available_at"]
    assert y["response_start_time"]
    assert y["response_end_time"]


def test_forward_delta_uses_future_close(roller_env: Path):
    cfg = RollerConfig(roller_env)
    update_sport(cfg, "NBA", "2025-2026", include_pbp=True, include_candles=True)
    db = Roller(roller_env)
    obs = db.observation("NBA_20251220_LAL_BOS", as_of="2025-12-20T20:14:00Z")
    y = db.response(obs["observation_id"], measurement="market_response_1m", horizon="1m")
    assert y["status"] == "valid"
    assert y["value"] == 130
    assert y["k_start"] == 5050
    assert y["k_end"] == 5180
