"""V4C identity firewall. Same informal name ≠ same measurement."""

from __future__ import annotations

from typing import Any

from roller.v4c.types import GreekIdentity


def _id(name: str, version: str | None, regime: str, resolution: str | None) -> GreekIdentity:
    return GreekIdentity(name, version, regime, resolution)


def audit_identity_uniqueness() -> list[str]:
    errors: list[str] = []
    one_m = _id("market_delta_1m", "4.0.0-B", "CANDLE_1M", "60_SECOND_CANDLE")
    one_s = _id("market_delta_1s", None, "SECOND_SNAPSHOT", "1_SECOND")
    if one_m == one_s or one_m.key() == one_s.key():
        errors.append("market_delta_1m must not equal market_delta_1s")
    same_name_diff_regime = _id("market_delta", "4.0.0-B", "CANDLE_1M", "60_SECOND_CANDLE")
    same_name_other = _id("market_delta", "4.0.0-B", "SECOND_SNAPSHOT", "1_SECOND")
    if same_name_diff_regime == same_name_other:
        errors.append("same name + different regime must be a different identity")
    same_name_diff_res = _id("market_delta", "4.0.0-B", "CANDLE_1M", "60_SECOND_CANDLE")
    same_name_1s = _id("market_delta", "4.0.0-B", "CANDLE_1M", "1_SECOND")
    if same_name_diff_res == same_name_1s:
        errors.append("same name + different resolution must be a different identity")
    return errors


def audit_frozen_negatives() -> list[str]:
    errors: list[str] = []
    pairs = (
        (
            _id("discrete_gamma", "4.0.0-B", "CANDLE_1M", "60_SECOND_CANDLE"),
            _id("score_surface_gamma", None, "CANDLE_1M", "60_SECOND_CANDLE"),
        ),
        (
            _id("realized_market_volatility", "4.0.0-B", "CANDLE_1M", "60_SECOND_CANDLE"),
            _id("sigma_K", None, "TRADE_TICK", "TRADE_TIMESTAMP"),
        ),
        (
            _id("pure_theta", "4.0.0-B", "CANDLE_1M", "60_SECOND_CANDLE"),
            _id("no_event_theta", None, "EVENT_SEQUENCE", "EVENT_TIMESTAMP"),
        ),
        (
            _id("score_delta", "4.0.0-B", "CANDLE_1M", "60_SECOND_CANDLE"),
            _id("conditional_score_surface_delta", None, "CANDLE_1M", "60_SECOND_CANDLE"),
        ),
    )
    labels = (
        "discrete_gamma ≠ score_surface_gamma",
        "realized_market_volatility ≠ sigma_K",
        "pure_theta ≠ no_event_theta",
        "score_delta ≠ conditional_score_surface_delta",
    )
    for (left, right), label in zip(pairs, labels, strict=True):
        if left == right or left.key() == right.key():
            errors.append(label)
    return errors


def run_v4c_identity_validate() -> dict[str, Any]:
    errors = audit_identity_uniqueness() + audit_frozen_negatives()
    return {"status": "FAIL" if errors else "PASS", "errors": errors}
