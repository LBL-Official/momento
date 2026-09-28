"""Descriptive persistence timing. Does not redefine Discovery warning counts."""

from __future__ import annotations

from typing import Any

from roller.austin.experiments.interpretation import warning_denominators
from roller.austin.experiments.persistence.landmarks import landmark_states
from roller.austin.experiments.persistence.util import as_float, clock_minutes_between
from roller.austin.experiments.statistics import warning_rows


def _damage_class(minutes: float | None, *, event_exists: bool) -> str:
    if not event_exists:
        return "NO_DAMAGE_EVENT"
    if minutes is None:
        return "UNAVAILABLE"
    if minutes > 0:
        return "BEFORE_DAMAGE"
    return "AT_OR_AFTER_DAMAGE"


def _first_t40(event: dict[str, Any]) -> dict[str, Any] | None:
    later = event.get("_later") or []
    first = event["_first"]
    if first.get("t40_already"):
        return first
    return next((r for r in later if r.get("t40_already") or r.get("hit_40_after")), None)


def _worst_price_row(event: dict[str, Any]) -> dict[str, Any] | None:
    first = event["_first"]
    later = event.get("_later") or []
    rows = [first, *later]
    priced = [r for r in rows if r.get("current_price_cents") is not None]
    if not priced:
        return None
    return min(priced, key=lambda r: int(r["current_price_cents"]))


def warning_persistence_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for event in events:
        states = landmark_states(event)
        t0 = states["t0"]
        t1 = states["t1"]
        t2 = states["t2"]
        t3 = states["t3"]
        t40 = _first_t40(event)
        worst = _worst_price_row(event)
        later = event.get("_later") or []
        settle = later[-1] if later else t0
        t1_neg = t1 is not None and as_float(t1.get("conditional_ev_cents")) is not None and float(t1["conditional_ev_cents"]) < 0
        t2_neg = t2 is not None and as_float(t2.get("conditional_ev_cents")) is not None and float(t2["conditional_ev_cents"]) < 0
        t3_neg = t3 is not None and as_float(t3.get("conditional_ev_cents")) is not None and float(t3["conditional_ev_cents"]) < 0
        t0_t40 = clock_minutes_between(t0, t40)
        t1_t40 = clock_minutes_between(t1, t40) if t1_neg else None
        t2_t40 = clock_minutes_between(t2, t40) if t2_neg else None
        t3_t40 = clock_minutes_between(t3, t40) if t3_neg else None
        t0_worst = clock_minutes_between(t0, worst)
        t1_worst = clock_minutes_between(t1, worst) if t1_neg else None
        t2_worst = clock_minutes_between(t2, worst) if t2_neg else None
        t3_worst = clock_minutes_between(t3, worst) if t3_neg else None
        out.append(
            {
                "trade_id": event["trade_id"],
                "source_experiment_id": event["source_experiment_id"],
                "negative_ev_class": event["negative_ev_class"],
                "won": event.get("won"),
                "time_t0_to_T40": t0_t40,
                "time_t1_negative_to_T40": t1_t40,
                "time_t2_negative_to_T40": t2_t40,
                "time_t3_negative_to_T40": t3_t40,
                "time_t0_to_worst_price": t0_worst,
                "time_t1_negative_to_worst_price": t1_worst,
                "time_t2_negative_to_worst_price": t2_worst,
                "time_t3_negative_to_worst_price": t3_worst,
                "time_t0_to_settlement": clock_minutes_between(t0, settle),
                "time_t1_to_settlement": clock_minutes_between(t1, settle) if t1_neg else None,
                "time_t2_to_settlement": clock_minutes_between(t2, settle) if t2_neg else None,
                "time_t3_to_settlement": clock_minutes_between(t3, settle) if t3_neg else None,
                "t0_to_T40_class": _damage_class(t0_t40, event_exists=t40 is not None),
                "t1_negative_to_T40_class": _damage_class(t1_t40, event_exists=t1_neg and t40 is not None),
                "t2_negative_to_T40_class": _damage_class(t2_t40, event_exists=t2_neg and t40 is not None),
                "t3_negative_to_T40_class": _damage_class(t3_t40, event_exists=t3_neg and t40 is not None),
                "t0_to_worst_class": _damage_class(t0_worst, event_exists=worst is not None),
                "t1_negative_to_worst_class": _damage_class(t1_worst, event_exists=t1_neg and worst is not None),
                "t2_negative_to_worst_class": _damage_class(t2_worst, event_exists=t2_neg and worst is not None),
                "t3_negative_to_worst_class": _damage_class(t3_worst, event_exists=t3_neg and worst is not None),
                "note": "descriptive mechanism timing; not validated warning",
            }
        )
    return out


def preserved_warning(trades: list[dict[str, Any]], queries: list[dict[str, Any]]) -> dict[str, Any]:
    rows = warning_rows(trades, queries)
    denoms = warning_denominators(trades, queries)
    losses = [r for r in rows if r.get("won") is False]
    available_losses = [r for r in losses if r.get("class") == "WARNING_AVAILABLE"]
    return {
        **denoms,
        "warning_before_damage_recall_among_losses": {
            "n": len(available_losses),
            "n_losses": len(losses),
            "note": "preserved Discovery definition; not redefined",
        },
    }


WARNING_FIELDS = [
    "trade_id",
    "source_experiment_id",
    "negative_ev_class",
    "won",
    "time_t0_to_T40",
    "time_t1_negative_to_T40",
    "time_t2_negative_to_T40",
    "time_t3_negative_to_T40",
    "time_t0_to_worst_price",
    "time_t1_negative_to_worst_price",
    "time_t2_negative_to_worst_price",
    "time_t3_negative_to_worst_price",
    "time_t0_to_settlement",
    "time_t1_to_settlement",
    "time_t2_to_settlement",
    "time_t3_to_settlement",
    "t0_to_T40_class",
    "t1_negative_to_T40_class",
    "t2_negative_to_T40_class",
    "t3_negative_to_T40_class",
    "t0_to_worst_class",
    "t1_negative_to_worst_class",
    "t2_negative_to_worst_class",
    "t3_negative_to_worst_class",
    "note",
]
