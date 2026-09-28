from __future__ import annotations

from pathlib import Path

from roller import Roller
from roller.config import RollerConfig
from roller.maintenance.update import update_sport
from roller.point_in_time.query import ResearchNotImplementedError
from roller.validation.greek_leakage import audit_observation_clean
from roller.validation.v4b_leakage import audit_observation_excludes_greeks
from roller.validation.v4c_constructibility import audit_no_proxy, audit_possession_not_implemented
from roller.validation.v4c_information_regime import audit_information_regimes
from roller.validation.v4c_measurement_identity import audit_frozen_negatives


def test_v4c_audit_hooks():
    assert audit_no_proxy() == []
    assert audit_possession_not_implemented() == []
    assert audit_information_regimes() == []
    assert audit_frozen_negatives() == []


def test_observation_excludes_v4c(roller_env: Path):
    cfg = RollerConfig(roller_env)
    update_sport(cfg, "NBA", "2025-2026", include_pbp=True, include_candles=True)
    db = Roller(roller_env)
    obs = db.observation("NBA_20251220_LAL_BOS", as_of="2025-12-20T20:13:30Z")
    assert audit_observation_excludes_greeks(obs) == []
    assert audit_observation_clean(obs) == []
    assert "v4c" not in obs
    assert "catalog" not in obs
    assert "measurements" not in obs
    db.greeks(obs["observation_id"], corpus=[], schema_version="4.0.0-C")
    obs2 = db.observation("NBA_20251220_LAL_BOS", as_of="2025-12-20T20:13:30Z")
    assert "v4c" not in obs2
    assert "measurements" not in obs2


def test_research_remains_stub(roller_env: Path):
    db = Roller(roller_env)
    try:
        db.research()
        raise AssertionError("research should remain a stub")
    except ResearchNotImplementedError as exc:
        assert "db.greeks()" in str(exc)
        assert "db.fundamental()" in str(exc)
