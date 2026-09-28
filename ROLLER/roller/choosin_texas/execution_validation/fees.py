"""Fee classification follows the modeled order role. Unknown schedules stay open."""

from __future__ import annotations

from typing import Any

from roller.choosin_texas.execution_validation.policy import FEE_SNAPSHOT
from roller.choosin_texas.models import ChoosinTexasError


def historical_fee_status() -> dict[str, Any]:
    return {
        "historical_book": "FEES_UNAVAILABLE",
        "snapshot": dict(FEE_SNAPSHOT),
        "reason": (
            "The quadratic series snapshot is dated 2026-09-03 and the cited PDF "
            "is effective 2026-07-07. Both are after the paired book's last entries. "
            "Maker zero is not applied to the historical book."
        ),
    }


def fee_for_role(
    *,
    role: str,
    filled_contracts: int,
    order_ts: str,
    series: str,
    schedule: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return a fee only when the role and a covering schedule both say so.

    A crossing order is never priced as a maker. An unfilled post-only
    rejection is not a maker fill. Unknown taker schedules stay unavailable.
    """
    if role == "POST_ONLY_REJECT":
        return {
            "role": role,
            "status": "NO_FILL",
            "fee_cents": 0,
            "reason": "A rejected post-only order is not a maker fill.",
        }
    if filled_contracts < 0:
        raise ChoosinTexasError("LOCK_MISMATCH", "filled contracts are negative")
    if filled_contracts == 0 or role == "RESTING_UNFILLED":
        return {
            "role": "RESTING_UNFILLED",
            "status": "NO_FILL",
            "fee_cents": None,
            "reason": "An unfilled resting order is not classified as a maker fill.",
        }
    if role == "TAKER":
        covered = schedule is not None and _covers(schedule, order_ts, series)
        return {
            "role": "TAKER",
            "status": "FEES_UNAVAILABLE",
            "fee_cents": None,
            "schedule_covers_timestamp": covered,
            "reason": "A crossing order is a taker. Maker zero is not applied. The taker amount is not charged without a date-matched formula result.",
        }
    if role == "MAKER":
        if (
            schedule is not None
            and _covers(schedule, order_ts, series)
            and schedule.get("fee_type") == "quadratic"
            and schedule.get("maker_fee_cents") == 0
        ):
            return {
                "role": "MAKER",
                "status": "VERIFIED_ZERO",
                "fee_cents": 0,
                "provenance": schedule.get("provenance"),
            }
        return {
            "role": "MAKER",
            "status": "FEES_UNAVAILABLE",
            "fee_cents": None,
            "reason": "No covering maker schedule.",
        }
    raise ChoosinTexasError("LOCK_MISMATCH", f"unknown fee role {role}")


def _covers(schedule: dict[str, Any], order_ts: str, series: str) -> bool:
    if series not in schedule.get("series", []):
        return False
    start = schedule.get("effective_from")
    end = schedule.get("effective_through")
    if not start or not end:
        return False
    return str(start) <= str(order_ts) <= str(end)
