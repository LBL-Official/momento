"""Frozen grade_config_v1. Thresholds are configuration, not UI."""

from __future__ import annotations

from typing import Any

from roller.superasi.base.versions import GRADE_CONFIG_VERSION, P_BE, P_DESK

LETTERS: tuple[str, ...] = (
    "F",
    "D-",
    "D",
    "D+",
    "C-",
    "C",
    "C+",
    "B-",
    "B",
    "B+",
    "A-",
    "A",
    "A+",
)

LETTER_SCORE = {
    "A+": 100.0,
    "A": 94.0,
    "A-": 90.0,
    "B+": 85.0,
    "B": 80.0,
    "B-": 75.0,
    "C+": 70.0,
    "C": 65.0,
    "C-": 60.0,
    "D+": 55.0,
    "D": 45.0,
    "D-": 30.0,
    "F": 0.0,
}

COMPOSITE_WEIGHTS = {
    "research_evidence": 0.40,
    "coverage": 0.20,
    "robustness": 0.20,
    "theoretical_alignment": 0.10,
    "validation": 0.10,
}

ROBUSTNESS_N = (
    (500, "A+"),
    (300, "A"),
    (200, "A-"),
    (150, "B+"),
    (100, "B"),
    (75, "B-"),
    (50, "C+"),
    (35, "C"),
    (25, "C-"),
    (15, "D+"),
    (10, "D"),
    (5, "D-"),
)

COVERAGE_BANDS = (
    (0.98, 0.01, "A+"),
    (0.95, 0.02, "A"),
    (0.90, 0.05, "B"),
    (0.80, 0.10, "C"),
    (0.60, 0.20, "D"),
)

EVIDENCE_LO_OFFSETS = (
    (0.08, "A+"),
    (0.05, "A"),
    (0.03, "A-"),
    (0.01, "B+"),
    (0.00, "B"),
    (-0.01, "B-"),
    (-0.03, "C+"),
    (-0.05, "C"),
)

WIDTH_CAP_C = 0.20
WIDTH_CAP_D = 0.30
BORDERLINE_FRAC = 0.05


def letter_rank(letter: str) -> int:
    try:
        return LETTERS.index(letter)
    except ValueError:
        return 0


def weaker(a: str, b: str) -> str:
    return a if letter_rank(a) <= letter_rank(b) else b


def min_letter(letters: list[str]) -> str:
    if not letters:
        return "F"
    return min(letters, key=letter_rank)


def score_letter(letter: str) -> float:
    return float(LETTER_SCORE.get(letter, 0.0))


def config_payload() -> dict[str, Any]:
    return {
        "version": GRADE_CONFIG_VERSION,
        "p_be": P_BE,
        "p_desk": P_DESK,
        "composite_weights": dict(COMPOSITE_WEIGHTS),
        "robustness_n": list(ROBUSTNESS_N),
        "coverage_bands": list(COVERAGE_BANDS),
        "note": "BASE_GRADE is min of component letters. Composite never raises the letter.",
    }
