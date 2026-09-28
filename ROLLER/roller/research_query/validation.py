"""AST validation before compile/execute. Does not scan."""

from __future__ import annotations

from roller.research_query.models import (
    EntryOp,
    ExitOutcome,
    PathOp,
    PriceField,
    ResearchQuestion,
)


def _entry_ref_e4(question: ResearchQuestion) -> int | None:
    if not question.entry_conditions:
        return None
    return int(question.entry_conditions[0].price_e4)


def validate_question(question: ResearchQuestion) -> list[str]:
    errors: list[str] = []
    for i, e in enumerate(question.entry_conditions):
        if e.price_e4 % 100 != 0 or e.price_e4 < 500 or e.price_e4 > 9500:
            errors.append(f"price_e4 {e.price_e4} is outside the 5¢–95¢ grid.")
        if e.price_field not in {f.value for f in PriceField}:
            errors.append(f"{e.price_field} is not an approved price field.")
        if e.ordinal.value == "NTH_TOUCH" and (e.nth is None or int(e.nth) < 1):
            errors.append("NTH_TOUCH requires nth >= 1.")
        if e.price_to_e4 is not None and (e.price_to_e4 % 100 != 0 or e.price_to_e4 < 500 or e.price_to_e4 > 9500):
            errors.append(f"price_to_e4 {e.price_to_e4} is outside the 5¢–95¢ grid.")
        if e.max_entry_e4 is not None:
            if e.max_entry_e4 % 100 != 0 or e.max_entry_e4 < 500 or e.max_entry_e4 > 9500:
                errors.append(f"max_entry_e4 {e.max_entry_e4} is outside integer cents 5¢–95¢.")
            elif e.max_entry_e4 < e.price_e4:
                errors.append(
                    f"max_entry_e4 {e.max_entry_e4} is below the First Touch trigger {e.price_e4}."
                )
        if e.direction not in (None, "up", "down"):
            errors.append(f"direction {e.direction} is not approved.")
        if e.resolved_operation() is EntryOp.RECOVERY and i == 0 and e.direction not in ("up", "down"):
            errors.append(
                "Standalone Recovery requires an explicit direction. "
                "Equality at P does not invent a side. This is invalid, not n=0."
            )
    ref = _entry_ref_e4(question)
    for p in question.path_conditions:
        if p.price_e4 % 100 != 0:
            errors.append(f"path price_e4 {p.price_e4} is not an integer-cent E4 value.")
        if p.horizon_minutes is not None and int(p.horizon_minutes) < 1:
            errors.append("horizon_minutes must be >= 1.")
        if ref is None or p.op in (PathOp.HORIZON_WIN, PathOp.HORIZON_LOSS):
            continue
        if p.outcome is ExitOutcome.WIN and p.price_e4 < ref:
            errors.append(
                f"WIN exit {p.op.value} {p.price_e4} is under the entry reference {ref}."
            )
        if p.outcome is ExitOutcome.LOSS and p.price_e4 > ref:
            errors.append(
                f"LOSS exit {p.op.value} {p.price_e4} is over the entry reference {ref}."
            )
    return errors
