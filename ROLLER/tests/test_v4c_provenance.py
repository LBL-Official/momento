"""Mapped objects are an overlay, not a V4C computation."""

from __future__ import annotations

from pathlib import Path

from roller.config import RollerConfig
from roller.v4c import V4C_EMPIRICAL_COMPUTATION_COUNT
from roller.v4c.mapping import overlay_architecture
from roller.v4c.provenance import SOURCE, SOURCE_SCHEMA_VERSION, TRANSFORMATION, assert_overlay_provenance


def test_mapped_provenance_is_lossless_v4b():
    cfg = RollerConfig(Path(__file__).resolve().parents[1])
    v4c = overlay_architecture(
        cfg,
        {
            "identity": {"observation_id": "OBS_X"},
            "observed": {
                "market_delta_1m": {
                    "value": {"numerator": 3, "denominator": 1, "units": "e4"},
                    "status": "valid",
                }
            },
        },
    )
    assert V4C_EMPIRICAL_COMPUTATION_COUNT == 0
    assert v4c["empirical_computation_count"] == 0
    prov = v4c["measurements"]["market_delta_1m"]["provenance"]
    assert_overlay_provenance(prov)
    assert prov["source"] == SOURCE
    assert prov["source"] != "V4C_COMPUTATION"
    assert prov["transformation"] == TRANSFORMATION
    assert prov["source_schema_version"] == SOURCE_SCHEMA_VERSION
    assert prov["source_measurement_name"] == "market_delta_1m"
