"""Lebronner Layer 0 only: stress p, hold s_W and s_L. Not a forecast."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from roller.superasi.exit_mixes import ev_from_s
from roller.superasi.four_cell import as_fractions
from roller.superasi.models import SuperasiError

LABELS = {
    "70": Fraction(70, 100),
    "73": Fraction(73, 100),
    "75": Fraction(75, 100),
    "K": Fraction(80, 100),
    "historical": None,
}


def stress(
    four_cell: dict[str, Any],
    p_key: str,
    *,
    gain: int = 20,
    loss: Fraction | None = None,
) -> dict[str, Any]:
    if p_key not in LABELS:
        raise SuperasiError("PACKAGE_SCHEMA_INVALID", f"unknown adverse p {p_key}")
    if (four_cell.get("s_W") or {}).get("status") == "UNAVAILABLE" or (
        four_cell.get("s_L") or {}
    ).get("status") == "UNAVAILABLE":
        return {
            "label": "ADVERSE TERMINAL",
            "kind": "STRESS TEST",
            "status": "DATA_REQUIRED",
            "code": "DATA_REQUIRED",
            "not_a_forecast": True,
            "held_s_W": False,
            "held_s_L": False,
            "note": "Adverse p holds observed s_W and s_L. Terminal four-cell is UNAVAILABLE.",
        }
    fr = as_fractions(four_cell)
    if "s_W" not in fr or "s_L" not in fr:
        raise SuperasiError("DATA_REQUIRED", "adverse p requires s_W and s_L")
    s_w, s_l = fr["s_W"], fr["s_L"]
    if p_key == "historical":
        p = fr["p"]
        label = "historical"
    else:
        p = LABELS[p_key]
        label = p_key
    assert p is not None
    s = p * s_w + (1 - p) * s_l
    out: dict[str, Any] = {
        "label": "ADVERSE TERMINAL",
        "kind": "STRESS TEST",
        "not_a_forecast": True,
        "not_a_model": True,
        "not_a_signal": True,
        "p_key": label,
        "p": {"numer": p.numerator, "denom": p.denominator, "status": "MODEL-ASSUMED" if p_key != "historical" else "OBSERVED"},
        "s_W": {"numer": s_w.numerator, "denom": s_w.denominator, "status": "OBSERVED", "held": True},
        "s_L": {"numer": s_l.numerator, "denom": s_l.denominator, "status": "OBSERVED", "held": True},
        "S_stressed": {"numer": s.numerator, "denom": s.denominator, "status": "DERIVED"},
        "held_s_W": True,
        "held_s_L": True,
        "note": "Changing adverse p must not modify s_W or s_L.",
    }
    if loss is not None:
        ev = ev_from_s(s, gain, loss)
        out["EV_adverse"] = {"numer": ev.numerator, "denom": ev.denominator, "status": "HYPOTHETICAL"}
        out["G"] = gain
        out["L"] = {"numer": loss.numerator, "denom": loss.denominator}
    return out
