"""Rank ITI slots by DEBASE_GRADE then BASE_GRADE. Not a fill."""

from __future__ import annotations

from typing import Any

from roller.superasi.base.grade_config import LETTER_SCORE


def _score(letter: Any) -> float:
    if not letter:
        return -1.0
    return float(LETTER_SCORE.get(str(letter), -1.0))


def rank_key(slot: dict[str, Any]) -> tuple[float, float, int]:
    if slot.get("status") != "COMPLETE":
        return (-1.0, -1.0, -1)
    control_last = 0 if slot.get("slot_id") == "ITI-00" else 1
    return (_score(slot.get("DEBASE_GRADE")), _score(slot.get("BASE_GRADE")), control_last)


def recommend_slot_id(slots: list[dict[str, Any]]) -> str | None:
    completed = [s for s in slots if s.get("status") == "COMPLETE"]
    if not completed:
        return None
    best = max(completed, key=rank_key)
    return str(best.get("slot_id") or "") or None
