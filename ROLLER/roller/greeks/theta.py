"""Clock-associated response. Pure clock isolation is PARTIAL unless controlled."""

from __future__ import annotations

from typing import Any

from roller.measurement.integers import parse_e4


def clock_isolation_status(score_start: Any, score_end: Any, n_events_in_window: int) -> dict[str, Any]:
    s0 = parse_e4(score_start)
    s1 = parse_e4(score_end)
    same_score = s0 is not None and s1 is not None and s0 == s1
    if same_score and n_events_in_window == 0:
        return {
            "status": "PARTIAL",
            "pure_clock_isolation": False,
            "note": "same score and no recorded events still does not prove hidden events were absent",
        }
    return {
        "status": "PARTIAL",
        "pure_clock_isolation": False,
        "note": "clock-associated response is not isolated from basketball events",
    }
