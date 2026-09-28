"""Identity is a hard type boundary."""

from __future__ import annotations

from roller.validation.v4c_measurement_identity import (
    audit_frozen_negatives,
    audit_identity_uniqueness,
)
from roller.v4c.types import GreekIdentity


def test_same_name_different_regime_or_resolution():
    assert audit_identity_uniqueness() == []
    a = GreekIdentity("market_delta_1m", "4.0.0-B", "CANDLE_1M", "60_SECOND_CANDLE")
    b = GreekIdentity("market_delta_1s", None, "SECOND_SNAPSHOT", "1_SECOND")
    assert a != b


def test_frozen_negative_identities():
    assert audit_frozen_negatives() == []
    discrete = GreekIdentity("discrete_gamma", "4.0.0-B", "CANDLE_1M", "60_SECOND_CANDLE")
    surface = GreekIdentity("score_surface_gamma", None, "CANDLE_1M", "60_SECOND_CANDLE")
    assert discrete != surface
    vol = GreekIdentity("realized_market_volatility", "4.0.0-B", "CANDLE_1M", "60_SECOND_CANDLE")
    sigma = GreekIdentity("sigma_K", None, "TRADE_TICK", "TRADE_TIMESTAMP")
    assert vol != sigma
    pure = GreekIdentity("pure_theta", "4.0.0-B", "CANDLE_1M", "60_SECOND_CANDLE")
    no_event = GreekIdentity("no_event_theta", None, "EVENT_SEQUENCE", "EVENT_TIMESTAMP")
    assert pure != no_event
    score = GreekIdentity("score_delta", "4.0.0-B", "CANDLE_1M", "60_SECOND_CANDLE")
    cond = GreekIdentity("conditional_score_surface_delta", None, "CANDLE_1M", "60_SECOND_CANDLE")
    assert score != cond
