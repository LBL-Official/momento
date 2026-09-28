"""Epistemic classes. A Greek name is not a statistic type.

DIRECT_DIFFERENCE
        ≠
EMPIRICAL_DISCRETE_SENSITIVITY
        ≠
PATH_DESCRIPTOR
        ≠
CONDITIONAL_SURFACE
        ≠
MICROSTRUCTURE
"""

from __future__ import annotations

from typing import Any

MEASUREMENT_CLASSES = (
    "DIRECT_DIFFERENCE",
    "EMPIRICAL_DISCRETE_SENSITIVITY",
    "PATH_DESCRIPTOR",
    "CONDITIONAL_SURFACE",
    "MICROSTRUCTURE",
)

# V4B public key is frozen. The scientific identity is the canonical name.
CANONICAL_IDENTITY = {
    "realized_market_volatility": "market_absolute_variation",
}

INFORMAL_FAMILY = {
    "realized_market_volatility": "VEGA_ANALOGUE",
    "discrete_gamma": "GAMMA_ANALOGUE",
    "score_delta": "DELTA_ANALOGUE",
    "theta_observed": "THETA_ANALOGUE",
    "pure_theta": "THETA_ANALOGUE",
}


def is_measurement_class(name: str) -> bool:
    return str(name) in MEASUREMENT_CLASSES


def classes_not_interchangeable(left: str, right: str) -> bool:
    return left != right
