"""Forward Y never enters observation()."""

from __future__ import annotations

from pathlib import Path

from roller import Roller
from roller.config import RollerConfig
from roller.maintenance.update import update_sport
from roller.validation.greek_leakage import audit_observation_clean, audit_response_future


def test_observation_excludes_forward_response(roller_env: Path):
    cfg = RollerConfig(roller_env)
    update_sport(cfg, "NBA", "2025-2026", include_pbp=True, include_candles=True)
    db = Roller(roller_env)
    obs = db.observation("NBA_20251220_LAL_BOS", as_of="2025-12-20T20:14:00Z")
    assert audit_observation_clean(obs) == []
    assert "BACKWARD_MEASUREMENTS" in obs
    y = db.response(obs["observation_id"], measurement="market_response_1m", horizon="1m")
    assert audit_response_future(y) == []
    assert y["contains_future_information"] is True
    blob = str(obs)
    assert "market_response_1m" not in blob
    assert y["value"] not in ((obs.get("BACKWARD_MEASUREMENTS") or {}).get("data") or {}).get("measurements", {})
