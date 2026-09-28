"""BINARY_COMPLEMENT_V0 relationship RV. Structural β=-1. Not route RV."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from roller.tk_ultra.models import (
    BETA_SOURCE,
    BETA_VERSION,
    MODEL_BINARY,
    UNAVAILABLE,
    frac_decimal,
)

STRUCTURAL_BETA = Fraction(-1)
COMPLEMENT = Fraction(100)


def complementary(a_anchor: Fraction, b_anchor: Fraction) -> bool:
    return a_anchor + b_anchor == COMPLEMENT


def expected_b(
    *,
    a_anchor: Fraction,
    b_anchor: Fraction,
    a_ref: Fraction,
    beta: Fraction,
) -> Fraction:
    return b_anchor + beta * (a_ref - a_anchor)


def rv_state(residual: Fraction) -> str:
    if residual < 0:
        return "CHEAP"
    if residual > 0:
        return "RICH"
    return "PARITY"


def in_binary_domain(value: Fraction) -> bool:
    return Fraction(0) <= value <= COMPLEMENT


def assess_relationship(
    *,
    a_anchor: Fraction | None,
    b_anchor: Fraction | None,
    a_ref: Fraction | None,
    b_observed: Fraction | None,
    a_ref_basis: str,
    b_observed_basis: str,
    a_bid: Fraction | None = None,
    b_ask: Fraction | None = None,
    a_bid_basis: str = "YES_BID",
    b_ask_basis: str = "YES_ASK",
    beta: Fraction = STRUCTURAL_BETA,
    beta_source: str = BETA_SOURCE,
    price_basis_transform: str | None = None,
) -> dict[str, Any]:
    reasons: list[str] = []
    if a_anchor is None or b_anchor is None:
        return {
            "status": UNAVAILABLE,
            "model_mode": MODEL_BINARY,
            "expected_wing": UNAVAILABLE,
            "observed_wing": json_obs(b_observed),
            "tk_residual": UNAVAILABLE,
            "rv_state": UNAVAILABLE,
            "relationship_route_collinear": False,
            "reason_codes": ["ANCHOR_UNAVAILABLE"],
            "anchor_validity": UNAVAILABLE,
        }
    if not complementary(a_anchor, b_anchor):
        if price_basis_transform:
            reasons.append("PRICE_BASIS_TRANSFORM_DOCUMENTED")
            anchor_validity = "MISMATCH_DOCUMENTED"
        else:
            return {
                "status": "ANCHOR_INVALID",
                "model_mode": MODEL_BINARY,
                "expected_wing": UNAVAILABLE,
                "observed_wing": json_obs(b_observed),
                "tk_residual": UNAVAILABLE,
                "rv_state": UNAVAILABLE,
                "relationship_route_collinear": False,
                "anchor_validity": "A_PLUS_B_NOT_100",
                "a_anchor": frac_decimal(a_anchor, 4),
                "b_anchor": frac_decimal(b_anchor, 4),
                "beta": frac_decimal(beta, 4),
                "beta_source": beta_source,
                "beta_version": BETA_VERSION,
                "reason_codes": ["ANCHOR_INVALID"],
                "detail": "A_anchor + B_anchor != 100. Not silently normalized.",
            }
    else:
        anchor_validity = "COMPLEMENT_100"
    if a_ref is None:
        return {
            "status": UNAVAILABLE,
            "model_mode": MODEL_BINARY,
            "expected_wing": UNAVAILABLE,
            "observed_wing": json_obs(b_observed),
            "tk_residual": UNAVAILABLE,
            "rv_state": UNAVAILABLE,
            "relationship_route_collinear": False,
            "anchor_validity": anchor_validity,
            "a_anchor": frac_decimal(a_anchor, 4),
            "b_anchor": frac_decimal(b_anchor, 4),
            "beta": frac_decimal(beta, 4),
            "beta_source": beta_source,
            "beta_version": BETA_VERSION,
            "a_ref_basis": a_ref_basis,
            "reason_codes": ["A_REF_UNAVAILABLE"],
        }
    expected = expected_b(a_anchor=a_anchor, b_anchor=b_anchor, a_ref=a_ref, beta=beta)
    if complementary(a_anchor, b_anchor) and beta == STRUCTURAL_BETA:
        invariant = COMPLEMENT - a_ref
        if expected != invariant:
            return {
                "status": "MODEL_INVALID",
                "model_mode": MODEL_BINARY,
                "expected_wing": UNAVAILABLE,
                "tk_residual": UNAVAILABLE,
                "rv_state": UNAVAILABLE,
                "reason_codes": ["COMPLEMENT_INVARIANCE_BROKEN"],
                "detail": "EXPECTED_B must equal 100 - A_ref under β=-1 complementary anchors.",
            }
    if not in_binary_domain(expected):
        return {
            "status": "MODEL_OUT_OF_BINARY_BOUNDS",
            "model_mode": MODEL_BINARY,
            "expected_wing": frac_decimal(expected, 4),
            "observed_wing": json_obs(b_observed),
            "tk_residual": UNAVAILABLE,
            "rv_state": UNAVAILABLE,
            "relationship_route_collinear": False,
            "anchor_validity": anchor_validity,
            "reason_codes": ["MODEL_OUT_OF_BINARY_BOUNDS"],
            "detail": "Expected B outside [0, 100]. Not silently clipped.",
        }
    collinear = (
        a_bid is not None
        and b_ask is not None
        and a_ref == a_bid
        and b_observed is not None
        and b_observed == b_ask
    )
    if collinear:
        reasons.append("RELATIONSHIP_ROUTE_COLLINEAR")
    residual = None if b_observed is None else (b_observed - expected)
    state = UNAVAILABLE if residual is None else rv_state(residual)
    b_obs_label = b_observed_basis if b_observed is not None else UNAVAILABLE
    if state == "CHEAP":
        reasons.append("WING_CHEAP_TO_RELATIONSHIP")
    elif state == "RICH":
        reasons.append("WING_RICH_TO_RELATIONSHIP")
    elif state == "PARITY":
        reasons.append("RELATIONSHIP_PARITY")
    else:
        reasons.append("OBSERVED_WING_UNAVAILABLE")
    return {
        "status": "RESEARCH_ONLY",
        "model_mode": MODEL_BINARY,
        "a_anchor": frac_decimal(a_anchor, 4),
        "b_anchor": frac_decimal(b_anchor, 4),
        "anchor_validity": anchor_validity,
        "beta": frac_decimal(beta, 4),
        "beta_source": beta_source,
        "beta_version": BETA_VERSION,
        "a_ref": frac_decimal(a_ref, 4),
        "a_ref_basis": a_ref_basis,
        "expected_wing": frac_decimal(expected, 4),
        "observed_wing": json_obs(b_observed),
        "observed_wing_basis": b_observed_basis if b_observed is not None else UNAVAILABLE,
        "tk_residual": frac_decimal(residual, 4) if residual is not None else UNAVAILABLE,
        "rv_state": state,
        "relationship_route_collinear": collinear,
        "relationship_basis_label": f"{a_ref_basis} / {b_obs_label}",
        "binary_formula_is_truth": False,
        "anchors_are_predictive": False,
        "note": (
            "V0 structural complement. EXPECTED_B = 100 - A_ref when anchors sum to 100 and β=-1. "
            "Anchors do not add predictive information beyond complementarity."
            + (
                " Relationship and route are collinear: TK_RESIDUAL = −GROSS_ROUTE_EDGE. "
                "Not a second independent confirmation."
                if collinear
                else ""
            )
        ),
        "reason_codes": reasons,
    }


def json_obs(value: Fraction | None) -> str:
    if value is None:
        return UNAVAILABLE
    out = frac_decimal(value, 4)
    return out if out is not None else UNAVAILABLE
