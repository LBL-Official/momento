"""Exact rationals and shared X_t. No float money."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from fractions import Fraction
from typing import Any


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, dict) and "value" in value:
        return _as_int(value.get("value"))
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class ExactRational:
    numerator: int
    denominator: int
    units: str = "e4"

    def __post_init__(self) -> None:
        if self.denominator == 0:
            raise ZeroDivisionError("ExactRational denominator must be nonzero")
        reduced = Fraction(self.numerator, self.denominator)
        object.__setattr__(self, "numerator", reduced.numerator)
        object.__setattr__(self, "denominator", reduced.denominator)

    @classmethod
    def from_int(cls, value: int, units: str = "e4") -> ExactRational:
        return cls(int(value), 1, units)

    @classmethod
    def from_fraction(cls, value: Fraction, units: str = "e4") -> ExactRational:
        return cls(value.numerator, value.denominator, units)

    def fraction(self) -> Fraction:
        return Fraction(self.numerator, self.denominator)

    def public(self) -> dict[str, Any]:
        return {
            "numerator": self.numerator,
            "denominator": self.denominator,
            "units": self.units,
        }

    def __add__(self, other: ExactRational) -> ExactRational:
        return ExactRational.from_fraction(self.fraction() + other.fraction(), self.units)

    def __sub__(self, other: ExactRational) -> ExactRational:
        return ExactRational.from_fraction(self.fraction() - other.fraction(), self.units)

    def __abs__(self) -> ExactRational:
        return ExactRational.from_fraction(abs(self.fraction()), self.units)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ExactRational):
            return NotImplemented
        return self.fraction() == other.fraction() and self.units == other.units


@dataclass
class CandleView:
    available_at: str
    available_at_dt: datetime
    yes_bid_close: int | None
    yes_bid_open: int | None = None
    yes_bid_high: int | None = None
    yes_bid_low: int | None = None


@dataclass
class FundamentalView:
    observation_id: str | None
    cutoff: str | None
    available_at: str | None
    status: str
    wins: int | None
    n: int | None
    condition_id: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "IMPLEMENTED" and self.wins is not None and self.n not in (None, 0)

    def f_e4(self) -> Fraction | None:
        if not self.ok:
            return None
        return Fraction(int(self.wins) * 10000, int(self.n))

    def basis(self, k_e4: int) -> Fraction | None:
        if not self.ok:
            return None
        return Fraction(int(k_e4) * int(self.n) - int(self.wins) * 10000, int(self.n))


@dataclass
class SharedXt:
    observation_id: str
    internal_game_id: str
    sport: str
    season: str
    cutoff: datetime
    cutoff_iso: str
    expected_interval_seconds: int
    vol_window_closes: int
    current: CandleView | None
    previous: CandleView | None
    previous2: CandleView | None
    interval_seconds: int | None
    interval_seconds_prev: int | None
    interval_ok: bool
    interval_prev_ok: bool
    f_t: FundamentalView | None
    f_prev: FundamentalView | None
    f_prev2: FundamentalView | None
    s_t: int | None
    s_prev: int | None
    period_t: Any
    period_prev: Any
    elapsed_t: int | None
    elapsed_prev: int | None
    visible_closes: list[tuple[str, int]]
    condition_id: str | None = None
    state_available_at: str | None = None


@dataclass
class MeasurementPoint:
    name: str
    value: ExactRational | None
    status: str
    measurement_available_at: str | None
    provenance: dict[str, Any] = field(default_factory=dict)
    path_information_status: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "measurement_name": self.name,
            "value": None if self.value is None else self.value.public(),
            "status": self.status,
            "measurement_available_at": self.measurement_available_at,
            "k_field": "yes_bid_close",
            "provenance": dict(self.provenance),
        }
        if self.path_information_status:
            body["path_information_status"] = self.path_information_status
        body.update(self.extra)
        return body


as_int = _as_int
