"""Result-envelope identity. No unexplained row disappearance."""

from __future__ import annotations

from typing import Any

from roller.research_query.measurements import measure_rows
from roller.research_query.models import TerminalOutcome


EXCLUSION_KEYS = (
    "empty_ticker",
    "untradable_only",
    "no_nth_touch",
    "period_unaligned",
    "clock_unaligned",
    "period_filter",
    "clock_filter",
    "tie_same_minute",
    "and_intersection_drop",
)


def _i(d: dict[str, Any], key: str) -> int:
    try:
        return int(d.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def build_identity(
    *,
    universe_tickers: int,
    exclusions: dict[str, int],
    entry_eligible: int,
    entry_rows: list[dict[str, Any]],
    terminal: TerminalOutcome,
    reported_n: int,
    path_requested: bool,
) -> dict[str, Any]:
    ex = {k: _i(exclusions, k) for k in EXCLUSION_KEYS}
    excl_sum = sum(ex.values())
    metrics = measure_rows(entry_rows)
    p = metrics["partition"]
    joint = int(p["joint_n"])
    yes = int(metrics["terminal_yes"])
    missing = int(metrics["terminal_missing"])
    no = int(metrics["terminal_available"]) - yes
    measured = len(entry_rows)
    return {
        "universe_tickers": int(universe_tickers),
        "exclusions": ex,
        "exclusion_sum": excl_sum,
        "entry_eligible": int(entry_eligible),
        "measured_eligible": measured,
        "path_requested": bool(path_requested),
        "path_true": int(metrics["path_true"]),
        "path_false": int(metrics["path_available"]) - int(metrics["path_true"]),
        "terminal": terminal.value,
        "terminal_is_measurement_filter": terminal is not TerminalOutcome.BOTH,
        "terminal_yes": yes,
        "terminal_no": no,
        "terminal_missing": missing,
        "reported_n": int(reported_n),
        "joint_n": joint,
        "equations": {
            "universe_minus_exclusions_eq_entry": (
                int(universe_tickers) - excl_sum == int(entry_eligible)
            ),
            "yes_plus_no_plus_missing_eq_measured": (
                yes + no + missing == measured
            ),
            "abcd_eq_joint": (
                int(p["T_AND_W"])
                + int(p["T_AND_NOT_W"])
                + int(p["NOT_T_AND_W"])
                + int(p["NOT_T_AND_NOT_W"])
                == joint
            ),
            "joint_plus_missing_eq_measured": joint + missing == measured,
            "entry_eq_measured": int(entry_eligible) == measured,
        },
    }


def identity_holds(identity: dict[str, Any]) -> bool:
    eqs = identity.get("equations") or {}
    return all(bool(v) for v in eqs.values())
