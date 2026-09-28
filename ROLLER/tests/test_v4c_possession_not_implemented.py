"""NBA possessions=REAL does not implement possession_delta."""

from __future__ import annotations

from pathlib import Path

from roller.config import RollerConfig
from roller.state.capabilities import REAL, capability
from roller.v4c.capability import possession_conditioned_f_validated, possession_delta_authorized
from roller.v4c.mapping import overlay_architecture
from roller.v4c.registry import get_v4c_object
from roller.v4c.state_greeks import describe


def test_possession_data_is_not_measurement_validity():
    cfg = RollerConfig(Path(__file__).resolve().parents[1])
    assert capability("NBA", "possessions") == REAL
    assert possession_conditioned_f_validated() is False
    assert possession_delta_authorized("NBA") is False
    row = get_v4c_object(cfg, "possession_delta")
    assert row["status"] == "NOT_YET_IMPLEMENTED"
    payload = overlay_architecture(cfg, {"identity": {"observation_id": "OBS_X"}, "observed": {}})
    cat = payload["catalog"]["possession_delta"]
    assert cat["value"] is None
    assert cat["status"] == "NOT_YET_IMPLEMENTED"
    described = describe(cfg, "possession_delta")
    assert described["value"] is None
