"""Baseline PIT eligibility. Both clocks; equality hidden."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from roller.timeutil import parse_utc, parse_utc_required


def baseline_eligible(
    response_i: dict[str, Any],
    *,
    observation_time_t,
    cutoff_t=None,
) -> bool:
    """eligible iff observation_time_i < t AND response_available_at_i < cutoff_t."""
    t = observation_time_t if isinstance(observation_time_t, datetime) else parse_utc_required(observation_time_t)
    cutoff = cutoff_t if cutoff_t is not None else t
    if not isinstance(cutoff, datetime):
        cutoff = parse_utc_required(cutoff)
    obs_i = parse_utc(response_i.get("observation_time"))
    avail_i = parse_utc(response_i.get("response_available_at"))
    if obs_i is None or avail_i is None:
        return False
    return obs_i < t and avail_i < cutoff
