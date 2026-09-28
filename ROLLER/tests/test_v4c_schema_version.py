from __future__ import annotations

from pathlib import Path

import pytest

from roller import Roller
from roller.config import RollerConfig
from roller.maintenance.update import update_sport


def test_unknown_schema_version_errors(roller_env: Path):
    cfg = RollerConfig(roller_env)
    update_sport(cfg, "NBA", "2025-2026", include_pbp=True, include_candles=True)
    db = Roller(roller_env)
    obs = db.observation("NBA_20251220_LAL_BOS", as_of="2025-12-20T20:13:30Z")
    with pytest.raises(ValueError, match="unknown greek schema_version"):
        db.greeks(obs["observation_id"], corpus=[], schema_version="9.9.9")
    v4c = db.greeks(obs["observation_id"], corpus=[], schema_version="4.0.0-C")
    assert v4c["schema_version"] == "4.0.0-C"
    assert v4c["greek_architecture_version"] == "4.0.0-C"
    assert v4c["source_measurement_schema"]["greek_schema_version"] == "4.0.0-B"
    assert "measurements" in v4c
    assert "catalog" in v4c
    assert "observed" not in v4c
