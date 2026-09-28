"""Catalog None ≠ mapped measurement None."""

from __future__ import annotations

from pathlib import Path

from roller.config import RollerConfig
from roller.v4c.capability import INSTANCE_STATUSES
from roller.v4c.mapping import overlay_architecture


def test_catalog_none_is_intentional_absence():
    cfg = RollerConfig(Path(__file__).resolve().parents[1])
    v4c = overlay_architecture(
        cfg,
        {
            "identity": {"observation_id": "OBS_X"},
            "observed": {
                "market_delta_1m": {"value": None, "status": "MISSING_K"},
                "score_delta": {"value": None, "status": "ZERO_SCORE_DELTA"},
                "pure_theta": {"value": None, "status": "MIXED_INTERVAL"},
            },
        },
    )
    catalog = v4c["catalog"]["microprice"]
    assert catalog["value"] is None
    assert catalog["status"] == "NOT_CONSTRUCTIBLE"
    assert catalog["reason"]
    missing = v4c["measurements"]["market_delta_1m"]
    assert missing["value"] is None
    assert missing["status"] == "DATA_UNAVAILABLE"
    invalid = v4c["measurements"]["score_delta"]
    assert invalid["value"] is None
    assert invalid["status"] == "INVALID_INPUT"
    mixed = v4c["measurements"]["pure_theta"]
    assert mixed["value"] is None
    assert mixed["status"] == "INSUFFICIENT_SUPPORT"
    assert missing["status"] in INSTANCE_STATUSES
    assert catalog["status"] not in INSTANCE_STATUSES
