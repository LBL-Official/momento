"""Frozen 25-slot ITI price catalog. Same ROLLER ops. No new indicators."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from roller.superasi.iti.versions import MAX_CENTS, MIN_CENTS, SLOT_COUNT, STEP_RATE

# (slot_id, label, entry_steps, win_steps, loss_steps)
SLOT_SPEC: tuple[tuple[str, str, int, int, int], ...] = (
    ("ITI-00", "control", 0, 0, 0),
    ("ITI-01", "E-3", -3, 0, 0),
    ("ITI-02", "E-2", -2, 0, 0),
    ("ITI-03", "E-1", -1, 0, 0),
    ("ITI-04", "E+1", 1, 0, 0),
    ("ITI-05", "E+2", 2, 0, 0),
    ("ITI-06", "E+3", 3, 0, 0),
    ("ITI-07", "W-3", 0, -3, 0),
    ("ITI-08", "W-2", 0, -2, 0),
    ("ITI-09", "W-1", 0, -1, 0),
    ("ITI-10", "W+1", 0, 1, 0),
    ("ITI-11", "W+2", 0, 2, 0),
    ("ITI-12", "W+3", 0, 3, 0),
    ("ITI-13", "L-3", 0, 0, -3),
    ("ITI-14", "L-2", 0, 0, -2),
    ("ITI-15", "L-1", 0, 0, -1),
    ("ITI-16", "L+1", 0, 0, 1),
    ("ITI-17", "L+2", 0, 0, 2),
    ("ITI-18", "L+3", 0, 0, 3),
    ("ITI-19", "E+1 W+1", 1, 1, 0),
    ("ITI-20", "E-1 W-1", -1, -1, 0),
    ("ITI-21", "E+1 L+1", 1, 0, 1),
    ("ITI-22", "E-1 L-1", -1, 0, -1),
    ("ITI-23", "W+1 L-1", 0, 1, -1),
    ("ITI-24", "W-1 L+1", 0, -1, 1),
)


def question_sha256(question: dict[str, Any]) -> str:
    blob = json.dumps(question, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def cents_from_e4(price_e4: int) -> int:
    return int(price_e4) // 100


def step_cents(price_e4: int) -> int:
    return max(1, int(round(cents_from_e4(price_e4) * STEP_RATE)))


def shift_price_e4(price_e4: int, steps: int) -> int:
    cents = cents_from_e4(price_e4)
    moved = min(MAX_CENTS, max(MIN_CENTS, cents + steps * step_cents(price_e4)))
    return int(moved) * 100


def _outcome(raw: dict[str, Any]) -> str:
    return str(raw.get("outcome") or "").strip().lower()


def _priced(raw: dict[str, Any]) -> bool:
    return raw.get("price_e4") is not None


def plan_prices(question: dict[str, Any]) -> dict[str, int | None]:
    entries = [int(e["price_e4"]) for e in (question.get("entry_conditions") or []) if _priced(e)]
    wins = [
        int(p["price_e4"])
        for p in (question.get("path_conditions") or [])
        if _priced(p) and _outcome(p) == "win"
    ]
    losses = [
        int(p["price_e4"])
        for p in (question.get("path_conditions") or [])
        if _priced(p) and _outcome(p) == "loss"
    ]
    return {
        "entry_e4": entries[0] if entries else None,
        "win_e4": wins[0] if wins else None,
        "loss_e4": losses[0] if losses else None,
        "entry_cents": cents_from_e4(entries[0]) if entries else None,
        "win_cents": cents_from_e4(wins[0]) if wins else None,
        "loss_cents": cents_from_e4(losses[0]) if losses else None,
    }


def apply_shifts(
    question: dict[str, Any],
    *,
    entry_steps: int,
    win_steps: int,
    loss_steps: int,
) -> dict[str, Any]:
    next_q = copy.deepcopy(question)
    for entry in next_q.get("entry_conditions") or []:
        if entry_steps and _priced(entry):
            entry["price_e4"] = shift_price_e4(int(entry["price_e4"]), entry_steps)
    for path in next_q.get("path_conditions") or []:
        if not _priced(path):
            continue
        if win_steps and _outcome(path) == "win":
            path["price_e4"] = shift_price_e4(int(path["price_e4"]), win_steps)
        if loss_steps and _outcome(path) == "loss":
            path["price_e4"] = shift_price_e4(int(path["price_e4"]), loss_steps)
    return next_q


def inversion_reason(question: dict[str, Any]) -> str | None:
    prices = plan_prices(question)
    entry = prices["entry_cents"]
    win = prices["win_cents"]
    loss = prices["loss_cents"]
    if entry is None:
        return "no_priced_entry"
    if win is not None and int(win) <= int(entry):
        return "win_le_entry"
    if loss is not None and int(loss) >= int(entry):
        return "loss_ge_entry"
    entries = [int(e["price_e4"]) for e in (question.get("entry_conditions") or []) if _priced(e)]
    wins = [
        int(p["price_e4"])
        for p in (question.get("path_conditions") or [])
        if _priced(p) and _outcome(p) == "win"
    ]
    losses = [
        int(p["price_e4"])
        for p in (question.get("path_conditions") or [])
        if _priced(p) and _outcome(p) == "loss"
    ]
    for e in entries:
        e_c = cents_from_e4(e)
        if any(cents_from_e4(w) <= e_c for w in wins):
            return "win_le_entry"
        if any(cents_from_e4(loss_e4) >= e_c for loss_e4 in losses):
            return "loss_ge_entry"
    return None


def axis_missing_reason(question: dict[str, Any], *, entry_steps: int, win_steps: int, loss_steps: int) -> str | None:
    prices = plan_prices(question)
    if entry_steps and prices["entry_e4"] is None:
        return "no_priced_entry"
    if win_steps and prices["win_e4"] is None:
        return "no_priced_win"
    if loss_steps and prices["loss_e4"] is None:
        return "no_priced_loss"
    return None


def build_catalog(question: dict[str, Any]) -> list[dict[str, Any]]:
    if len(SLOT_SPEC) != SLOT_COUNT:
        raise RuntimeError("ITI slot spec is not 25")
    source_hash = question_sha256(question)
    slots: list[dict[str, Any]] = []
    for slot_id, label, e_s, w_s, l_s in SLOT_SPEC:
        missing = axis_missing_reason(question, entry_steps=e_s, win_steps=w_s, loss_steps=l_s)
        variant = apply_shifts(question, entry_steps=e_s, win_steps=w_s, loss_steps=l_s)
        invert = None if missing else inversion_reason(variant)
        skip = missing or invert
        prices = plan_prices(variant)
        slots.append(
            {
                "slot_id": slot_id,
                "label": label,
                "entry_steps": e_s,
                "win_steps": w_s,
                "loss_steps": l_s,
                "status": "SKIPPED" if skip else "PENDING",
                "skip_reason": skip,
                "question": variant,
                "question_sha256": question_sha256(variant),
                "source_question_sha256": source_hash,
                **prices,
                "population": None,
                "BASE_GRADE": None,
                "DEBASE_GRADE": None,
                "lab_id": None,
                "phase_a_result_id": None,
                "phase_b_result_id": None,
                "executed": False,
            }
        )
    return slots
