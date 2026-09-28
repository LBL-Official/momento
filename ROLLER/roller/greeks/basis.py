"""Basis K_t - F_t. No F_t provider. Do not use historical win rate."""

from __future__ import annotations

from typing import Any

from roller.state.missingness import section


def basis_measurement(_observation: dict[str, Any] | None = None) -> dict[str, Any]:
    return section(
        "NOT_YET_IMPLEMENTED",
        None,
        measurement_name="basis",
        measurement_version="v1",
        market_probability_source="yes_bid_close",
        fundamental_probability_source=None,
        basis_definition="K_t - F_t",
        note="no validated F_t provider; historical win rate is not F_t",
    )
