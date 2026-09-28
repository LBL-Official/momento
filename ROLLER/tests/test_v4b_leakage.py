from __future__ import annotations

from pathlib import Path

import pandas as pd

from roller import Roller
from roller.config import RollerConfig
from roller.maintenance.update import update_sport
from roller.point_in_time.query import ResearchNotImplementedError
from roller.validation.greek_leakage import audit_observation_clean
from roller.validation.v4b_leakage import (
    audit_measurement_not_before_inputs,
    audit_observation_excludes_greeks,
    audit_v4b_eligibility_example,
    audit_visible_candles_half_open,
)
from roller.v4b.measurements import compute_observed
from tests.helpers_v4b import make_xt


def test_v4b_eligibility_contract():
    assert audit_v4b_eligibility_example() == []


def test_measurement_available_at_not_before_inputs():
    assert audit_measurement_not_before_inputs("2025-12-20T20:14:00Z", "2025-12-20T20:14:00Z") == []
    assert audit_measurement_not_before_inputs("2025-12-20T20:13:00Z", "2025-12-20T20:14:00Z")


def test_rolling_vol_uses_only_visible_closes():
    candles = pd.DataFrame(
        [
            {"available_at": "2025-12-20T20:13:00Z", "yes_bid_close": 1, "team_side": "home"},
            {"available_at": "2025-12-20T20:15:00Z", "yes_bid_close": 9, "team_side": "home"},
        ]
    )
    assert audit_visible_candles_half_open(candles, "2025-12-20T20:15:00Z") == []
    vis_error = audit_visible_candles_half_open(candles, "2025-12-20T20:13:00Z")
    assert vis_error == []


def test_observation_has_no_greeks(roller_env: Path):
    cfg = RollerConfig(roller_env)
    update_sport(cfg, "NBA", "2025-2026", include_pbp=True, include_candles=True)
    db = Roller(roller_env)
    obs = db.observation("NBA_20251220_LAL_BOS", as_of="2025-12-20T20:13:30Z")
    assert audit_observation_excludes_greeks(obs) == []
    assert audit_observation_clean(obs) == []
    assert "greeks" not in obs
    payload = db.greeks(obs["observation_id"], corpus=[])
    assert payload["identity"]["observation_id"] == obs["observation_id"]
    assert payload["versions"]["greek_schema_version"] == "4.0.0-B"
    assert payload["versions"]["fundamental_schema_version"] == "4.0.0-A"
    obs2 = db.observation("NBA_20251220_LAL_BOS", as_of="2025-12-20T20:13:30Z")
    assert "greeks" not in obs2
    assert "observed" not in obs2


def test_research_remains_stub(roller_env: Path):
    db = Roller(roller_env)
    try:
        db.research()
        raise AssertionError("research should remain a stub")
    except ResearchNotImplementedError as exc:
        assert "db.greeks()" in str(exc)


def test_compute_observed_does_not_write_onto_xt():
    xt = make_xt()
    compute_observed(xt)
    assert not hasattr(xt, "observed")
