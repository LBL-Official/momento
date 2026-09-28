"""V4A leakage: observation stays clean; eligibility uses both clocks + identity."""

from __future__ import annotations

from pathlib import Path

from roller import Roller
from roller.config import RollerConfig
from roller.maintenance.update import update_sport
from roller.validation.fundamental_leakage import (
    audit_fundamental_eligibility_example,
    audit_observation_excludes_fundamental,
)
from roller.validation.greek_leakage import audit_observation_clean


def test_fundamental_eligibility_contract():
    assert audit_fundamental_eligibility_example() == []


def test_observation_has_no_fundamental(roller_env: Path):
    cfg = RollerConfig(roller_env)
    update_sport(cfg, "NBA", "2025-2026", include_pbp=True, include_candles=True)
    db = Roller(roller_env)
    obs = db.observation("NBA_20251220_LAL_BOS", as_of="2025-12-20T20:13:30Z")
    assert audit_observation_excludes_fundamental(obs) == []
    assert audit_observation_clean(obs) == []
    assert obs.get("fundamental") is None
    assert "F_t" not in obs
