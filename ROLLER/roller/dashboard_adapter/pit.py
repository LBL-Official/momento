"""Thin PIT façade — imports Roller only. No research math."""

from __future__ import annotations

from typing import Any

from roller import Roller


def open_roller(root: Any = None) -> Roller:
    """Construct the authoritative PIT database handle."""
    return Roller(root) if root is not None else Roller()


def as_of_state(db: Roller, as_of: str, *, end_of_day: bool = False):
    """Bound information set I(t)."""
    return db.as_of(as_of, end_of_day=end_of_day)
