"""Insufficient support does not emit residual 0."""

from __future__ import annotations

from pathlib import Path

from roller.config import RollerConfig
from roller.greeks.residual import compute_residual
from roller.measurement.baseline import compute_baseline


SRC = Path(__file__).resolve().parents[1]


def test_insufficient_support_is_undefined_not_zero():
    cfg = RollerConfig(SRC)
    obs = {
        "observation_id": "OBS_TEST",
        "observation_time": "2025-12-20T10:06:00Z",
        "sport": "NBA",
        "GAME_STATE": {"data": {"period": 3, "elapsed_game_seconds": 100, "score": {"score_differential_home": {"value": 1}}}},
        "MARKET_STATE": {"data": {"yes_bid_close": "5000"}},
        "BACKWARD_MEASUREMENTS": {"data": {"measurements": {"high_low_range_1m": {"value": 10}}}},
        "POSSESSIONS": {"status": "REAL", "data": {"possessions": []}},
    }
    corpus = [
        {
            "observation_time": "2025-12-20T10:00:00Z",
            "response_available_at": "2025-12-20T10:05:00Z",
            "measurement_name": "market_response_5m",
            "horizon": "5m",
            "value": 7,
            "status": "valid",
            "internal_game_id": "only_one_game",
        }
    ]
    base = compute_baseline(
        cfg, observation=obs, measurement="market_response_5m", horizon="5m", corpus=corpus
    )
    assert base["status"] == "INSUFFICIENT_SUPPORT"
    assert base["expected"] is None
    y = {"observation_id": "OBS_TEST", "measurement_name": "market_response_5m", "horizon": "5m", "value": 7}
    resid = compute_residual(y, base)
    assert resid["residual_status"] == "INSUFFICIENT_SUPPORT"
    assert resid["value"] is None
    assert resid["value"] != 0
