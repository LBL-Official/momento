"""Gate 2: V4C registry, regimes, capability, dataset firewall. No new numbers."""

from __future__ import annotations

from pathlib import Path

import pytest

from roller import GREEK_ARCHITECTURE_VERSION, GREEK_SCHEMA_VERSION, Roller
from roller.config import RollerConfig
from roller.point_in_time.filters import FutureInformationError
from roller.v4c.capability import (
    ARCHITECTURE_STATUSES,
    INSTANCE_STATUSES,
    ProxyProhibitedError,
    constructible,
    possession_delta_authorized,
    refuse_proxy,
)
from roller.v4c.information_regimes import ACTIVE_REGIMES, REGIMES, quality_rank
from roller.v4c.registry import (
    REQUIRED_OBJECT_FIELDS,
    catalog_names,
    get_v4c_object,
    load_v4c_registry,
    mapped_names,
    validate_registry_row,
    v4c_objects,
)
from roller.v4c.validation import audit_registry

SRC = Path(__file__).resolve().parents[1]


def test_v4c_versions_and_registry_fields():
    cfg = RollerConfig(SRC)
    body = load_v4c_registry(cfg)
    assert cfg.greek_architecture_version == "4.0.0-C"
    assert GREEK_ARCHITECTURE_VERSION == "4.0.0-C"
    assert GREEK_SCHEMA_VERSION == "4.0.0-B"
    assert cfg.greek_schema_version == "4.0.0-B"
    assert cfg.db_map["database"]["version"] == "4.0.0-C"
    assert body["greek_architecture_version"] == "4.0.0-C"
    assert body["source_measurement_schema"]["greek_schema_version"] == "4.0.0-B"
    assert audit_registry(cfg) == []
    names = [row["measurement_name"] for row in v4c_objects(cfg)]
    for fam in (
        "market_delta_1m",
        "fundamental_delta",
        "response_delta",
        "market_fundamental_basis",
        "basis_delta",
        "score_delta",
        "discrete_gamma",
        "theta_observed",
        "pure_theta",
        "candle_range",
        "absolute_return",
        "realized_market_volatility",
        "directional_efficiency",
    ):
        assert fam in names
        row = get_v4c_object(cfg, fam)
        for field in REQUIRED_OBJECT_FIELDS:
            assert field in row
        assert validate_registry_row(row) == []
        assert row["status"] in {"IMPLEMENTED", "PARTIAL"}
        assert row["definition_version"] == "4.0.0-B"
        assert row["edge_claim"] is False
    assert get_v4c_object(cfg, "pure_theta")["status"] == "PARTIAL"
    assert "market_delta_1m" in mapped_names(cfg)
    assert "microprice" in catalog_names(cfg)
    assert get_v4c_object(cfg, "response_beta")["status"] == "NOT_YET_IMPLEMENTED"
    assert get_v4c_object(cfg, "microprice")["status"] == "NOT_CONSTRUCTIBLE"
    assert get_v4c_object(cfg, "response_beta")["status"] != get_v4c_object(cfg, "microprice")["status"]


def test_v4c_regimes_are_modalities():
    assert set(REGIMES) == {
        "CANDLE_1M",
        "EVENT_SEQUENCE",
        "POSSESSION_STATE",
        "TRADE_TICK",
        "SECOND_SNAPSHOT",
        "FULL_ORDER_BOOK",
    }
    assert ACTIVE_REGIMES == {"CANDLE_1M"}
    assert quality_rank("FULL_ORDER_BOOK") is None
    assert quality_rank("CANDLE_1M") is None


def test_v4c_capability_taxonomy_not_collapsed():
    assert ARCHITECTURE_STATUSES == {
        "IMPLEMENTED",
        "PARTIAL",
        "NOT_YET_IMPLEMENTED",
        "NOT_CONSTRUCTIBLE",
    }
    assert INSTANCE_STATUSES == {
        "DATA_UNAVAILABLE",
        "INSUFFICIENT_SUPPORT",
        "INVALID_INPUT",
    }
    assert constructible(
        data_available=True,
        information_regime_valid=True,
        point_in_time_valid=True,
        definition_exists=True,
        definition_implemented=True,
        identity_unambiguous=True,
        proxy_prohibition_satisfied=True,
    )
    assert not constructible(
        data_available=True,
        information_regime_valid=True,
        point_in_time_valid=True,
        definition_exists=True,
        definition_implemented=False,
        identity_unambiguous=True,
        proxy_prohibition_satisfied=True,
    )


def test_v4c_no_proxy_and_possession_data_insufficient():
    with pytest.raises(ProxyProhibitedError, match="MICROPRICE"):
        refuse_proxy("OHLC", "microprice")
    with pytest.raises(ProxyProhibitedError):
        refuse_proxy("candle_volume", "signed_flow_lambda")
    with pytest.raises(ProxyProhibitedError):
        refuse_proxy("possession_data", "possession_delta")
    assert possession_delta_authorized("NBA") is False


def test_v4c_dataset_names_rejected(roller_env: Path):
    db = Roller(roller_env)
    for name in ("v4c_greek_observations", "v4c_catalog", "v4c_anything"):
        with pytest.raises(FutureInformationError, match="use db.greeks()"):
            db.dataset("NBA", "2025-2026", name, as_of="2025-12-21")


def test_v3_and_v4a_firewall_strings_unchanged(roller_env: Path):
    db = Roller(roller_env)
    with pytest.raises(FutureInformationError, match="use db.fundamental()"):
        db.dataset("NBA", "2025-2026", "fundamental", as_of="2025-12-21")
    with pytest.raises(FutureInformationError, match="use db.labels()"):
        db.dataset("NBA", "2025-2026", "game_state_features", as_of="2025-12-21")
    with pytest.raises(FutureInformationError, match="use db.greeks()"):
        db.dataset("NBA", "2025-2026", "v4b_greek_observations", as_of="2025-12-21")
