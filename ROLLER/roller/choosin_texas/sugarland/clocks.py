"""Start clocks. A stored schedule match is not an entry-time snapshot."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from roller.choosin_texas.sugarland.constants import SCHEDULE_QUARANTINE_SEC


def _utc_date(ts: datetime) -> datetime.date:
    return ts.astimezone(timezone.utc).date()


def classify_stored_schedule(
    scheduled: datetime | None,
    actual: datetime | None,
) -> dict[str, str]:
    """Return primary clock role and quarantine flag.

    Primary research clock is actual start when it exists.
    Stored scheduled time is never labeled implementable.
    """
    if actual is None:
        return {
            "primary_role": "NO_ACTUAL_START",
            "schedule_relation": "STORED_SCHEDULE_UNAVAILABLE" if scheduled is None else "STORED_SCHEDULE_ONLY",
            "quarantine": "",
            "note": "RETROSPECTIVE_ACTUAL_START unavailable",
        }
    if scheduled is None:
        return {
            "primary_role": "RETROSPECTIVE_ACTUAL_START",
            "schedule_relation": "STORED_SCHEDULE_UNAVAILABLE",
            "quarantine": "",
            "note": "stored schedule absent; sensitivity unavailable",
        }
    delta = abs((actual - scheduled).total_seconds())
    day_gap = abs((_utc_date(actual) - _utc_date(scheduled)).days)
    if delta > SCHEDULE_QUARANTINE_SEC or day_gap >= 2:
        return {
            "primary_role": "RETROSPECTIVE_ACTUAL_START",
            "schedule_relation": "STORED_SCHEDULE_SENSITIVITY",
            "quarantine": "SCHEDULE_EXCEPTION",
            "note": "stored schedule differs from actual beyond the quarantine rule",
        }
    if day_gap == 1:
        relation = "UTC_DATE_ROLLOVER"
    elif delta == 0:
        relation = "STORED_MATCH_NOT_IMPLEMENTABLE"
    else:
        relation = "STORED_SCHEDULE_SENSITIVITY"
    return {
        "primary_role": "RETROSPECTIVE_ACTUAL_START",
        "schedule_relation": relation,
        "quarantine": "",
        "note": "matching or near stored timestamps are not an entry-time snapshot",
    }


def endpoint(start: datetime, minutes: int = 30) -> datetime:
    return start - timedelta(minutes=minutes)
