"""Errors and fraction display. Research only."""

from __future__ import annotations

from fractions import Fraction
from typing import Any


class ChoosinTexasError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, str]:
        return {"status": self.code, "code": self.code, "message": self.message}


def frac(numer: int, denom: int, *, status: str = "OBSERVED") -> dict[str, Any]:
    if denom == 0:
        raise ChoosinTexasError("LOCK_MISMATCH", "fraction denominator is 0")
    value = Fraction(int(numer), int(denom))
    return {
        "numer": value.numerator,
        "denom": value.denominator,
        "status": status,
    }


def pct_display(numer: int, denom: int, *, digits: int = 4) -> str:
    if denom == 0:
        raise ChoosinTexasError("LOCK_MISMATCH", "percent denominator is 0")
    q = Fraction(int(numer), int(denom)) * 100
    return f"{float(q):.{digits}f}%"


def ratio_display(numer: int, denom: int) -> str:
    return f"{int(numer)}/{int(denom)}"
