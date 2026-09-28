"""Threshold candle-path payoffs. Not fills and not net EV."""

from __future__ import annotations


def gross_threshold_cents(*, terminal: str | None, stopped: bool, stop_cents: int, entry_cents: int = 78) -> int | None:
    if terminal not in {"yes", "no"}:
        return None
    if stopped:
        return int(stop_cents) - int(entry_cents)
    if terminal == "yes":
        return 100 - int(entry_cents)
    return -int(entry_cents)


def cell_name(*, terminal: str | None, stopped: bool) -> str:
    if terminal == "yes" and not stopped:
        return "YES_NO_STOP"
    if terminal == "yes" and stopped:
        return "YES_STOP"
    if terminal == "no" and not stopped:
        return "NO_NO_STOP"
    if terminal == "no" and stopped:
        return "NO_STOP"
    return "UNRESOLVED"
