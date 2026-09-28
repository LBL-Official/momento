"""Gate 2: V4B registry, versions, and dataset firewall. No engines."""

from __future__ import annotations

from pathlib import Path

import pytest

from roller import Roller
from roller.config import RollerConfig
from roller.point_in_time.filters import FutureInformationError
from roller.v4b.definitions import (
    OBSERVED_FAMILIES,
    REQUIRED_FAMILY_FIELDS,
    expected_interval_seconds,
    get_v4b_family,
    load_v4b_definitions,
    load_v4b_registry,
    realized_vol_window_closes,
)

SRC = Path(__file__).resolve().parents[1]


def test_v4b_versions_and_locked_definitions():
    cfg = RollerConfig(SRC)
    defs = load_v4b_definitions(cfg)
    body = load_v4b_registry(cfg)
    assert cfg.greek_schema_version == "4.0.0-B"
    assert cfg.fundamental_schema_version == "4.0.0-A"
    assert cfg.state_schema_version == "2.0.0"
    assert cfg.measurement_schema_version == "3.0.0"
    assert cfg.db_map["database"]["version"] == "4.0.0-C"
    assert defs["greek_schema_version"] == "4.0.0-B"
    assert defs["k_field"] == "yes_bid_close"
    assert expected_interval_seconds(cfg) == 60
    assert realized_vol_window_closes(cfg) >= 2
    assert defs["absolute_return"]["definition"] == "abs(market_delta_1m)"
    assert defs["score_state"]["convention"].startswith("S_t = home_score_t")
    assert defs["discrete_gamma"]["kind"] == "temporal_second_difference"
    assert "d2F_dS2" in defs["discrete_gamma"]["not"]
    assert defs["pure_theta"]["interpretation"] == "PARTIAL"
    assert "standard_deviation" in defs["realized_market_volatility"]["not"]
    names = [row["name"] for row in body["families"]]
    for fam in OBSERVED_FAMILIES:
        assert fam in names
        row = get_v4b_family(cfg, fam)
        for field in REQUIRED_FAMILY_FIELDS:
            assert field in row
    assert get_v4b_family(cfg, "v4b_baseline")["contains_future_information"] is True
    assert get_v4b_family(cfg, "v4b_residual")["contains_future_information"] is True
    assert get_v4b_family(cfg, "market_delta_1m")["information_boundary"] == "backward"
    assert get_v4b_family(cfg, "market_delta_1m")["contains_future_information"] is False
    cond = cfg.fundamental_conditioning
    assert cond["default_schema"] == "core_v1"
    assert [d["name"] for d in cond["schemas"]["core_v1"]["dimensions"]] == [
        "period",
        "clock_bucket",
        "score_margin_bucket",
    ]


def test_v4b_dataset_names_rejected(roller_env: Path):
    db = Roller(roller_env)
    for name in ("v4b_greek_observations", "v4b_anything", "greek_observations", "greek_baselines"):
        with pytest.raises(FutureInformationError, match="use db.greeks()"):
            db.dataset("NBA", "2025-2026", name, as_of="2025-12-21")


def test_v3_and_v4a_firewall_strings_unchanged(roller_env: Path):
    db = Roller(roller_env)
    with pytest.raises(FutureInformationError, match="use db.fundamental()"):
        db.dataset("NBA", "2025-2026", "fundamental", as_of="2025-12-21")
    with pytest.raises(FutureInformationError, match="use db.labels()"):
        db.dataset("NBA", "2025-2026", "game_state_features", as_of="2025-12-21")
