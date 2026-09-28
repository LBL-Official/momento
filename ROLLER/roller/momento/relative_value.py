"""Pluggable relative-value research. Not a live hedge."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from typing import Protocol

from roller.momento.contracts import RVHedgeAssessment

METHOD = "tk_relative_value_v1"


class RVModel(Protocol):
    method: str

    def assess(
        self,
        *,
        generated_at: str,
        as_of: str,
        game_id: str | None,
        base_price_cents: int,
        wing_price_cents: int,
        base_anchor_cents: int,
        wing_anchor_cents: int,
        beta: Fraction,
        ticks_per_handle: int,
    ) -> RVHedgeAssessment: ...


def parse_price(raw: str, *, field: str) -> Fraction:
    text = str(raw).strip()
    if not text:
        raise ValueError(f"{field} is missing")
    try:
        value = Fraction(text)
    except (ValueError, ZeroDivisionError, TypeError) as exc:
        raise ValueError(f"{field} is not a number") from exc
    return value


def frac_decimal(value: Fraction, places: int) -> str:
    quant = Decimal("1").scaleb(-places)
    number = Decimal(value.numerator) / Decimal(value.denominator)
    return str(number.quantize(quant, rounding=ROUND_HALF_UP))


def reading_of(residual: Fraction) -> str:
    if residual < 0:
        return "WING_CHEAP"
    if residual > 0:
        return "WING_RICH"
    return "FAIR_LINE"


@dataclass(frozen=True)
class TkRelativeValueResult:
    method: str
    wing_price: Fraction
    base_price: Fraction
    beta: Fraction
    wing_anchor: Fraction
    base_anchor: Fraction
    ticks_per_handle: int
    relationship_multiplier: Fraction
    expected_wing_move: Fraction
    expected_wing: Fraction
    residual: Fraction
    rv_ticks: Fraction

    @property
    def reading(self) -> str:
        return reading_of(self.residual)

    def payload(self) -> dict[str, object]:
        return {
            "method": self.method,
            "model_mode": "GENERIC_RV",
            "schema": "tk_ultra.generic_assess.v1",
            "live_execution": False,
            "binary_formula_is_truth": False,
            "status": "RESEARCH_ONLY",
            "reading": self.reading,
            "ticks_per_handle": self.ticks_per_handle,
            "inputs": {
                "wing_price": frac_decimal(self.wing_price, 6),
                "base_price": frac_decimal(self.base_price, 6),
                "beta": frac_decimal(self.beta, 6),
                "wing_anchor": frac_decimal(self.wing_anchor, 6),
                "base_anchor": frac_decimal(self.base_anchor, 6),
            },
            "steps": [
                {
                    "id": "multiplier",
                    "label": "(wing_price / base_price) * beta",
                    "value": frac_decimal(self.relationship_multiplier, 4),
                    "numer": self.relationship_multiplier.numerator,
                    "denom": self.relationship_multiplier.denominator,
                },
                {
                    "id": "expected_move",
                    "label": "(base_price - base_anchor) * multiplier",
                    "value": frac_decimal(self.expected_wing_move, 4),
                    "numer": self.expected_wing_move.numerator,
                    "denom": self.expected_wing_move.denominator,
                },
                {
                    "id": "residual",
                    "label": "wing_price - (expected_move + wing_anchor)",
                    "value": frac_decimal(self.residual, 4),
                    "numer": self.residual.numerator,
                    "denom": self.residual.denominator,
                },
                {
                    "id": "rv_ticks",
                    "label": "residual * ticks_per_handle",
                    "value": frac_decimal(self.rv_ticks, 2),
                    "numer": self.rv_ticks.numerator,
                    "denom": self.rv_ticks.denominator,
                },
            ],
            "relationship_multiplier": frac_decimal(self.relationship_multiplier, 4),
            "expected_wing_move": frac_decimal(self.expected_wing_move, 4),
            "expected_wing": frac_decimal(self.expected_wing, 4),
            "residual": frac_decimal(self.residual, 4),
            "rv_ticks": frac_decimal(self.rv_ticks, 2),
        }


def evaluate(
    *,
    wing_price: Fraction,
    base_price: Fraction,
    beta: Fraction,
    wing_anchor: Fraction,
    base_anchor: Fraction,
    ticks_per_handle: int,
) -> TkRelativeValueResult:
    if base_price == 0:
        raise ValueError("base_price must be non-zero")
    if int(ticks_per_handle) < 1:
        raise ValueError("ticks_per_handle must be >= 1")
    multiplier = (wing_price / base_price) * beta
    expected_move = (base_price - base_anchor) * multiplier
    expected_wing = wing_anchor + expected_move
    residual = wing_price - expected_wing
    ticks = residual * int(ticks_per_handle)
    return TkRelativeValueResult(
        method=METHOD,
        wing_price=wing_price,
        base_price=base_price,
        beta=beta,
        wing_anchor=wing_anchor,
        base_anchor=base_anchor,
        ticks_per_handle=int(ticks_per_handle),
        relationship_multiplier=multiplier,
        expected_wing_move=expected_move,
        expected_wing=expected_wing,
        residual=residual,
        rv_ticks=ticks,
    )


class TkRelativeValueV1:
    method = METHOD

    def assess(
        self,
        *,
        generated_at: str,
        as_of: str,
        game_id: str | None,
        base_price_cents: int,
        wing_price_cents: int,
        base_anchor_cents: int,
        wing_anchor_cents: int,
        beta: Fraction,
        ticks_per_handle: int,
    ) -> RVHedgeAssessment:
        result = evaluate(
            wing_price=Fraction(wing_price_cents),
            base_price=Fraction(base_price_cents),
            beta=beta,
            wing_anchor=Fraction(wing_anchor_cents),
            base_anchor=Fraction(base_anchor_cents),
            ticks_per_handle=ticks_per_handle,
        )
        return RVHedgeAssessment(
            generated_at=generated_at,
            as_of=as_of,
            source_system="relative_value_hedging",
            game_id=game_id,
            provenance={"formula": METHOD, "binary_truth": False},
            method=self.method,
            base_price_cents=base_price_cents,
            wing_price_cents=wing_price_cents,
            base_anchor_cents=base_anchor_cents,
            wing_anchor_cents=wing_anchor_cents,
            beta_numer=beta.numerator,
            beta_denom=beta.denominator,
            relationship_multiplier_numer=result.relationship_multiplier.numerator,
            relationship_multiplier_denom=result.relationship_multiplier.denominator,
            expected_wing_cents_numer=result.expected_wing.numerator,
            expected_wing_cents_denom=result.expected_wing.denominator,
            residual_cents_numer=result.residual.numerator,
            residual_cents_denom=result.residual.denominator,
            rv_ticks_numer=result.rv_ticks.numerator,
            rv_ticks_denom=result.rv_ticks.denominator,
            ticks_per_handle=int(ticks_per_handle),
            binary_formula_is_truth=False,
            status="RESEARCH_ONLY",
        )


def binary_yes_no(
    model: RVModel,
    *,
    generated_at: str,
    as_of: str,
    game_id: str | None,
    yes_cents: int,
    no_cents: int,
    yes_anchor_cents: int,
    no_anchor_cents: int,
    beta: Fraction,
    ticks_per_handle: int = 1,
) -> RVHedgeAssessment:
    """YES is base, NO is wing. Formula is not claimed true for binaries."""
    out = model.assess(
        generated_at=generated_at,
        as_of=as_of,
        game_id=game_id,
        base_price_cents=yes_cents,
        wing_price_cents=no_cents,
        base_anchor_cents=yes_anchor_cents,
        wing_anchor_cents=no_anchor_cents,
        beta=beta,
        ticks_per_handle=ticks_per_handle,
    )
    out.provenance = {
        **out.provenance,
        "pair": "YES_vs_NO",
        "note": "binary adapter; futures formula is not truth",
    }
    return out


REGISTRY: dict[str, type[TkRelativeValueV1]] = {METHOD: TkRelativeValueV1}
