"""Conservative re-grade using unchanged grade_config_v1. Does not overwrite BASE_GRADE."""

from __future__ import annotations

from typing import Any

from roller.superasi.base.grade_config import letter_rank, min_letter, weaker
from roller.superasi.base.grading import grade_strategy
from roller.superasi.debase.versions import A_PLUS_FLOOR, A_PLUS_RETURN, GRADE_CONFIG_VERSION


def conservative_observed(
    observed: dict[str, Any],
    *,
    ev_debase: float,
    p_working: float,
    wilson_lower: float | None = None,
    wilson_upper: float | None = None,
    wilson_width: float | None = None,
) -> dict[str, Any]:
    header_ev = observed.get("gross_ev")
    if header_ev is None:
        conservative_ev = ev_debase
    else:
        conservative_ev = min(float(header_ev), float(ev_debase))
    lo = float(wilson_lower) if wilson_lower is not None else float(p_working)
    hi = float(wilson_upper) if wilson_upper is not None else observed.get("wilson_upper")
    width = float(wilson_width) if wilson_width is not None else (
        (float(hi) - lo) if hi is not None else None
    )
    body = dict(observed)
    body["win_rate"] = float(p_working)
    body["wilson_lower"] = lo
    body["wilson_upper"] = hi
    body["wilson_width"] = width
    body["gross_ev"] = conservative_ev
    body["ev_debase"] = ev_debase
    body["p_working"] = p_working
    body["p_working_basis"] = "iqr1"
    return body


def cap_to_base(debase_letter: str, base_letter: str) -> str:
    if not base_letter:
        return debase_letter
    return debase_letter if letter_rank(debase_letter) <= letter_rank(base_letter) else base_letter


def instrument_gate(*, expected_20_week_return: float | None, p_floor: float | None) -> dict[str, Any]:
    reasons: list[str] = []
    ret_ok = expected_20_week_return is not None and float(expected_20_week_return) >= A_PLUS_RETURN
    floor_ok = p_floor is not None and float(p_floor) < A_PLUS_FLOOR
    if expected_20_week_return is None:
        reasons.append("expected_20_week_return_unavailable")
    elif not ret_ok:
        reasons.append("expected_20_week_return_below_67pct")
    if p_floor is None:
        reasons.append("p_floor_unavailable")
    elif not floor_ok:
        reasons.append("p_floor_at_or_above_5_50pct")
    passed = bool(ret_ok and floor_ok)
    return {
        "metric": "A_PLUS_INSTRUMENT_GATE",
        "passed": passed,
        "value": "PASS" if passed else "FAIL",
        "expected_20_week_return": expected_20_week_return,
        "threshold_return": A_PLUS_RETURN,
        "P_min_bankroll_le_floor": p_floor,
        "threshold_floor": A_PLUS_FLOOR,
        "reasons": reasons,
        "note": "Valuation gate only. Not a letter. Not BASE_GRADE. Not DEBASE_GRADE.",
    }


def run_degrading(
    *,
    observed: dict[str, Any],
    checks: list[dict[str, Any]],
    ev_debase: float,
    p_working: float,
    base_grade: str,
    phase_a_components: dict[str, str],
    expected_20_week_return: float | None,
    p_floor: float | None,
) -> dict[str, Any]:
    conservative = conservative_observed(
        observed,
        ev_debase=ev_debase,
        p_working=p_working,
        wilson_lower=observed.get("wilson_lower_at_iqr1"),
        wilson_upper=observed.get("wilson_upper_at_iqr1"),
        wilson_width=observed.get("wilson_width_at_iqr1"),
    )
    graded = grade_strategy(conservative, checks)
    raw = str(graded.get("BASE_GRADE") or "F")
    capped = cap_to_base(raw, base_grade)
    components = graded.get("components") if isinstance(graded.get("components"), dict) else {}
    bottleneck = min_letter(list(components.values())) if components else "F"
    bottleneck_names = [name for name, letter in components.items() if letter == bottleneck]
    return {
        "grade_config_version": GRADE_CONFIG_VERSION,
        "BASE_GRADE": base_grade,
        "phase_a_components": dict(phase_a_components),
        "DEBASE_GRADE": capped,
        "DEBASE_GRADE_uncapped": raw,
        "capped_to_base": capped != raw,
        "components": components,
        "composite_score": graded.get("composite_score"),
        "borderline": graded.get("borderline"),
        "borderline_components": graded.get("borderline_components"),
        "bottleneck": bottleneck,
        "bottleneck_components": bottleneck_names,
        "p_working": p_working,
        "ev_used": conservative.get("gross_ev"),
        "raise_requires": (
            f"raise {bottleneck_names[0]} above {bottleneck}" if bottleneck_names else "all components"
        ),
        "instrument_gate": instrument_gate(
            expected_20_week_return=expected_20_week_return,
            p_floor=p_floor,
        ),
        "note": "DEBASE_GRADE uses grade_config_v1 on IQR 1 as the mean and min(header EV, ev_debase). It cannot exceed BASE_GRADE.",
    }


def weaker_or_equal(a: str, b: str) -> str:
    return weaker(a, b)
