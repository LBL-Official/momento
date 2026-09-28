"""Four epistemic classes are not interchangeable. V4B keys stay frozen."""

from __future__ import annotations

from pathlib import Path

from roller.config import RollerConfig
from roller.v4c.mapping import overlay_architecture
from roller.v4c.measurement_classes import MEASUREMENT_CLASSES
from roller.v4c.registry import get_v4c_object
from roller.v4c.types import GreekIdentity, identity_from_row


def test_classes_are_the_five_constitutional_types():
    assert MEASUREMENT_CLASSES == (
        "DIRECT_DIFFERENCE",
        "EMPIRICAL_DISCRETE_SENSITIVITY",
        "PATH_DESCRIPTOR",
        "CONDITIONAL_SURFACE",
        "MICROSTRUCTURE",
    )


def test_v4b_key_realized_vol_is_absolute_variation_identity():
    cfg = RollerConfig(Path(__file__).resolve().parents[1])
    row = get_v4c_object(cfg, "realized_market_volatility")
    assert row["measurement_name"] == "realized_market_volatility"
    assert row["canonical_identity"] == "market_absolute_variation"
    assert row["measurement_class"] == "PATH_DESCRIPTOR"
    assert row["informal_family"] == "VEGA_ANALOGUE"
    ident = identity_from_row(row)
    assert ident.canonical_identity == "market_absolute_variation"
    sigma = identity_from_row(get_v4c_object(cfg, "sigma_K"))
    assert ident != sigma
    assert ident.measurement_class != sigma.measurement_class


def test_discrete_gamma_is_not_a_conditional_surface():
    cfg = RollerConfig(Path(__file__).resolve().parents[1])
    gamma = identity_from_row(get_v4c_object(cfg, "discrete_gamma"))
    surface = identity_from_row(get_v4c_object(cfg, "score_surface_gamma"))
    assert gamma.measurement_class == "EMPIRICAL_DISCRETE_SENSITIVITY"
    assert gamma.identity_kind == "temporal_second_difference"
    assert surface.measurement_class == "CONDITIONAL_SURFACE"
    assert gamma != surface


def test_same_informal_delta_four_identities():
    candle = GreekIdentity(
        "market_delta_1m",
        "4.0.0-B",
        "CANDLE_1M",
        "60_SECOND_CANDLE",
        measurement_class="DIRECT_DIFFERENCE",
    )
    second = GreekIdentity(
        "market_delta_1s",
        None,
        "SECOND_SNAPSHOT",
        "1_SECOND",
        measurement_class="DIRECT_DIFFERENCE",
    )
    beta = GreekIdentity(
        "response_beta",
        None,
        "CANDLE_1M",
        "60_SECOND_CANDLE",
        measurement_class="CONDITIONAL_SURFACE",
    )
    book = GreekIdentity(
        "book_microprice_delta",
        None,
        "FULL_ORDER_BOOK",
        "BOOK_SNAPSHOT",
        measurement_class="MICROSTRUCTURE",
    )
    keys = {candle.key(), second.key(), beta.key(), book.key()}
    assert len(keys) == 4


def test_overlay_exposes_class_on_mapped_and_catalog():
    cfg = RollerConfig(Path(__file__).resolve().parents[1])
    v4c = overlay_architecture(
        cfg,
        {
            "identity": {"observation_id": "OBS_X"},
            "observed": {
                "realized_market_volatility": {
                    "value": {"numerator": 40, "denominator": 1, "units": "e4"},
                    "status": "valid",
                }
            },
        },
    )
    vol = v4c["measurements"]["realized_market_volatility"]
    assert vol["value"]["numerator"] == 40
    assert vol["identity"]["canonical_identity"] == "market_absolute_variation"
    assert vol["identity"]["measurement_class"] == "PATH_DESCRIPTOR"
    assert v4c["catalog"]["microprice"]["measurement_class"] == "MICROSTRUCTURE"
    assert v4c["catalog"]["score_surface_gamma"]["measurement_class"] == "CONDITIONAL_SURFACE"
