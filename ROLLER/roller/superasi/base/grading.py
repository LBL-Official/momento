"""Evidence grade of the Roller CSV. Mode A does not set BASE_GRADE."""

from __future__ import annotations

from typing import Any

from roller.superasi.base.grade_config import (
    BORDERLINE_FRAC,
    COMPOSITE_WEIGHTS,
    COVERAGE_BANDS,
    EVIDENCE_LO_OFFSETS,
    ROBUSTNESS_N,
    WIDTH_CAP_C,
    WIDTH_CAP_D,
    min_letter,
    score_letter,
    weaker,
)
from roller.superasi.base.versions import GRADE_CONFIG_VERSION, P_BE, P_DESK


def _near(value: float, threshold: float) -> bool:
    if threshold == 0:
        return abs(value) < BORDERLINE_FRAC
    return abs(value - threshold) < BORDERLINE_FRAC * abs(threshold)


def research_evidence_grade(
    *,
    decided: int,
    p_hat: float | None,
    lo: float | None,
    gross_ev: float | None,
    p_be: float = P_BE,
) -> tuple[str, list[str]]:
    flags: list[str] = []
    if decided <= 0 or p_hat is None:
        return "F", flags
    if p_hat < p_be - 0.05:
        letter = "F"
    elif lo is None:
        letter = "D"
    else:
        delta = float(lo) - p_be
        letter = "C-" if p_hat >= p_be else "D"
        for offset, named in EVIDENCE_LO_OFFSETS:
            if delta + 1e-15 >= offset:
                letter = named
                if _near(delta, offset):
                    flags.append("research_evidence")
                break
        if p_hat < p_be:
            letter = weaker(letter, "D")
    if gross_ev is None or gross_ev == 0:
        letter = weaker(letter, "C")
    elif gross_ev < 0:
        letter = weaker(letter, "D")
    return letter, flags


def coverage_grade(
    *,
    decided_rate: float,
    bad_settle_rate: float,
    population_mismatch: bool,
) -> tuple[str, list[str]]:
    if population_mismatch:
        return "F", []
    flags: list[str] = []
    letter = "F"
    for dmin, bmax, named in COVERAGE_BANDS:
        if decided_rate + 1e-15 >= dmin and bad_settle_rate < bmax:
            letter = named
            if _near(decided_rate, dmin) or _near(bad_settle_rate, bmax):
                flags.append("coverage")
            break
    return letter, flags


def robustness_grade(*, decided: int, width: float | None) -> tuple[str, list[str]]:
    flags: list[str] = []
    letter = "F"
    for threshold, named in ROBUSTNESS_N:
        if decided >= threshold:
            letter = named
            if _near(float(decided), float(threshold)):
                flags.append("robustness")
            break
    if width is not None and width > WIDTH_CAP_D:
        letter = weaker(letter, "D")
    elif width is not None and width > WIDTH_CAP_C:
        letter = weaker(letter, "C")
    return letter, flags


def alignment_grade(
    *,
    decided: int,
    p_hat: float | None,
    lo: float | None,
    hi: float | None,
    p_be: float = P_BE,
    p_desk: float = P_DESK,
) -> tuple[str, list[str]]:
    flags: list[str] = []
    if decided <= 0 or p_hat is None:
        return "F", flags
    if p_hat < p_be - 0.05:
        return "F", flags
    if p_hat < p_be:
        return "D", flags
    if lo is None:
        return "C", flags
    if lo > p_desk:
        if _near(lo, p_desk):
            flags.append("theoretical_alignment")
        return "A+", flags
    if p_hat >= p_desk and lo > p_be:
        return "A", flags
    if lo > p_be:
        return "B", flags
    if hi is not None and lo <= p_desk <= hi:
        return "B-", flags
    if p_hat > p_be and lo < p_be:
        return "C", flags
    return "D", flags


def validation_grade(checks: list[dict[str, Any]]) -> tuple[str, list[str]]:
    hard = [c for c in checks if c.get("severity") == "hard" and not c.get("ok")]
    warn = [c for c in checks if c.get("severity") == "warning" and not c.get("ok")]
    if hard:
        return "F", []
    if warn:
        return "B", []
    return "A+", []


def grade_strategy(observed: dict[str, Any], checks: list[dict[str, Any]]) -> dict[str, Any]:
    decided = int(observed.get("decided") or 0)
    p_hat = observed.get("win_rate")
    lo = observed.get("wilson_lower")
    hi = observed.get("wilson_upper")
    width = observed.get("wilson_width")
    header_n = observed.get("header_population")
    pop = observed.get("population")
    pop_mismatch = header_n is not None and pop is not None and int(header_n) != int(pop)
    decided_rate = observed.get("decided_rate")
    bad_settle_rate = observed.get("bad_settle_rate")
    ev_letter, ev_flags = research_evidence_grade(
        decided=decided,
        p_hat=float(p_hat) if p_hat is not None else None,
        lo=float(lo) if lo is not None else None,
        gross_ev=observed.get("gross_ev"),
    )
    cov_letter, cov_flags = coverage_grade(
        decided_rate=float(decided_rate) if decided_rate is not None else 0.0,
        bad_settle_rate=float(bad_settle_rate) if bad_settle_rate is not None else 1.0,
        population_mismatch=bool(pop_mismatch),
    )
    rob_letter, rob_flags = robustness_grade(
        decided=decided,
        width=float(width) if width is not None else None,
    )
    ali_letter, ali_flags = alignment_grade(
        decided=decided,
        p_hat=float(p_hat) if p_hat is not None else None,
        lo=float(lo) if lo is not None else None,
        hi=float(hi) if hi is not None else None,
    )
    val_letter, val_flags = validation_grade(checks)
    components = {
        "research_evidence": ev_letter,
        "coverage": cov_letter,
        "robustness": rob_letter,
        "theoretical_alignment": ali_letter,
        "validation": val_letter,
    }
    scores = {name: score_letter(letter) for name, letter in components.items()}
    composite = sum(scores[name] * COMPOSITE_WEIGHTS[name] for name in COMPOSITE_WEIGHTS)
    base = min_letter(list(components.values()))
    flags = sorted(set(ev_flags + cov_flags + rob_flags + ali_flags + val_flags))
    return {
        "grade_config_version": GRADE_CONFIG_VERSION,
        "p_be": P_BE,
        "p_desk": P_DESK,
        "components": components,
        "scores": scores,
        "composite_score": composite,
        "BASE_GRADE": base,
        "borderline": bool(flags),
        "borderline_components": flags,
        "note": "BASE_GRADE is min(component letters). Monte Carlo is not the letter grade.",
    }
