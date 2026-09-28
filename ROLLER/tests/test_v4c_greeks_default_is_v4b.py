"""Default db.greeks() remains the public V4B contract."""

from __future__ import annotations

from pathlib import Path

from roller import Roller
from roller.config import RollerConfig
from roller.maintenance.update import update_sport


def test_default_greeks_equals_explicit_v4b(roller_env: Path):
    cfg = RollerConfig(roller_env)
    update_sport(cfg, "NBA", "2025-2026", include_pbp=True, include_candles=True)
    db = Roller(roller_env)
    obs = db.observation("NBA_20251220_LAL_BOS", as_of="2025-12-20T20:13:30Z")
    oid = obs["observation_id"]
    default = db.greeks(oid, corpus=[])
    explicit = db.greeks(oid, corpus=[], schema_version="4.0.0-B")
    assert default == explicit
    assert default["versions"]["greek_schema_version"] == "4.0.0-B"
    assert "measurements" not in default
    assert "catalog" not in default
    assert "observed" in default
