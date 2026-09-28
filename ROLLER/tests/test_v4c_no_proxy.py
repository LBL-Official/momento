"""Catalog microstructure objects stay null. No candle→book path."""

from __future__ import annotations

from pathlib import Path

import pytest

from roller.config import RollerConfig
from roller.v4c.capability import ProxyProhibitedError, refuse_proxy
from roller.v4c.mapping import overlay_architecture


def test_no_proxy_structural_refusals():
    with pytest.raises(ProxyProhibitedError):
        refuse_proxy("OHLC", "order_book")
    with pytest.raises(ProxyProhibitedError):
        refuse_proxy("high_low", "microprice")
    with pytest.raises(ProxyProhibitedError):
        refuse_proxy("candle_volume", "signed_flow")
    with pytest.raises(ProxyProhibitedError):
        refuse_proxy("volume", "queue")
    with pytest.raises(ProxyProhibitedError):
        refuse_proxy("candle_sequence", "second_level")


def test_catalog_microstructure_values_are_none():
    cfg = RollerConfig(Path(__file__).resolve().parents[1])
    v4c = overlay_architecture(
        cfg,
        {"identity": {"observation_id": "OBS_X"}, "observed": {}},
    )
    for name in (
        "microprice",
        "order_book_imbalance",
        "signed_flow_lambda",
        "price_impact_lambda",
        "psi_resilience",
    ):
        row = v4c["catalog"][name]
        assert row["value"] is None
        assert row["status"] == "NOT_CONSTRUCTIBLE"
        assert name not in v4c["measurements"]
