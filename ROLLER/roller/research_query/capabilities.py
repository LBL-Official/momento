"""Operation capability — independent of data availability."""

from __future__ import annotations

from roller.research_query.models import (
    APPROVED_EVENT_DEFINITIONS,
    BASIS_LAST_TRADE,
    BASIS_TRADABLE,
    IMPLEMENTED_ENTRY_OPS,
    LAST_TRADE_EVENT_DEFINITIONS,
    PathOp,
    PriceField,
    ResearchQuestion,
    TOUCH_FAMILIES,
    TRADABLE_EVENT_DEFINITIONS,
    UNSUPPORTED_ENTRY,
    UNSUPPORTED_PATH,
    EntryOp,
    TouchOrdinal,
)
from roller.research_query.scopes import RESERVED_FAMILIES, RESERVED_SCOPES


SUPPORTED_ORDINALS = frozenset(TouchOrdinal)
APPROVED_PRICE_FIELDS = frozenset({f.value for f in PriceField})
BASIS_EVENT_DEFINITIONS = {
    BASIS_TRADABLE: TRADABLE_EVENT_DEFINITIONS,
    BASIS_LAST_TRADE: LAST_TRADE_EVENT_DEFINITIONS,
}
SUPPORTED_ENTRY_OPS = frozenset(EntryOp)
SUPPORTED_PATH_OPS = frozenset(
    {
        PathOp.REACH,
        PathOp.DROP_TO,
        PathOp.RISE_TO,
        PathOp.RECOVER,
        PathOp.BOUNCE,
        PathOp.REVERT,
        PathOp.MAXIMUM_MOVE,
        PathOp.MINIMUM_MOVE,
        PathOp.NEVER_REACH,
        PathOp.HORIZON_WIN,
        PathOp.HORIZON_LOSS,
    }
)


def unsupported_operations(question: ResearchQuestion) -> list[str]:
    reasons: list[str] = []
    for e in question.entry_conditions:
        if e.ordinal not in SUPPORTED_ORDINALS:
            reasons.append(f"{e.ordinal.value} has no approved candle-close definition.")
        if e.price_field not in APPROVED_PRICE_FIELDS:
            reasons.append(
                f"Price field {e.price_field} is not approved. Approved fields are "
                f"{', '.join(sorted(APPROVED_PRICE_FIELDS))}."
            )
        if e.event_definition not in APPROVED_EVENT_DEFINITIONS:
            reasons.append(f"Event definition {e.event_definition} is not approved.")
        elif e.event_definition not in BASIS_EVENT_DEFINITIONS.get(e.basis(), frozenset()):
            # A tradable price field must never carry a last-trade definition,
            # or vice versa: that would relabel print data as executable.
            reasons.append(
                f"Event definition {e.event_definition} does not match price field {e.price_field}."
            )
        if e.resolved_operation() not in SUPPORTED_ENTRY_OPS:
            reasons.append(f"{e.resolved_operation().value} has no approved candle-close definition.")
        if e.direction not in (None, "up", "down"):
            reasons.append(f"direction {e.direction} is not approved.")
    for p in question.path_conditions:
        if p.op not in SUPPORTED_PATH_OPS:
            reasons.append(f"{p.op.value} has no approved candle-close definition.")
        if p.op in (PathOp.HORIZON_WIN, PathOp.HORIZON_LOSS):
            if p.horizon_kind not in ("game", "market") or p.horizon_minutes is None or int(p.horizon_minutes) < 1:
                reasons.append("Time horizon requires game or market kind and minutes >= 1.")
    return reasons


def draft_unsupported_families(entry_families: list[str], path_families: list[str]) -> list[str]:
    out: list[str] = []
    for f in entry_families:
        key = str(f or "").strip().lower()
        if key in RESERVED_FAMILIES:
            out.append(f)
        elif f in UNSUPPORTED_ENTRY:
            out.append(f)
        elif f in IMPLEMENTED_ENTRY_OPS or f in TOUCH_FAMILIES or f == "clock":
            pass
        else:
            out.append(f)
    for f in path_families:
        key = str(f or "").strip().lower()
        if key in RESERVED_FAMILIES:
            out.append(f)
        elif f in UNSUPPORTED_PATH:
            out.append(f)
    return out


def reserved_scope_names(names: list[str]) -> list[str]:
    reserved = {s.value for s in RESERVED_SCOPES} | {s.value.lower() for s in RESERVED_SCOPES}
    reserved |= RESERVED_FAMILIES
    out: list[str] = []
    for n in names:
        key = str(n or "").strip()
        if key in reserved or key.lower() in reserved or key.upper() in reserved:
            out.append(n)
    return out
