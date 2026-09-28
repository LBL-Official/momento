"""Daily re-execution of the saved specification. No date expansion."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, time, timedelta, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo

from roller.stax.compatibility import canonicalize_universe
from roller.stax.library import load_head, write_head, write_run
from roller.stax.models import StaxError, utc_now
from roller.stax.versions import DEFAULT_SCHEDULE, DEFAULT_TIMEZONE, LIVE_EXECUTION


def parse_schedule(schedule: str) -> time:
    text = str(schedule or DEFAULT_SCHEDULE).strip()
    parts = text.split(":")
    if len(parts) != 2:
        raise StaxError("STAX_SCHEDULE_INVALID", f"schedule must be HH:MM, got {schedule!r}")
    try:
        return time(int(parts[0]), int(parts[1]))
    except ValueError as exc:
        raise StaxError("STAX_SCHEDULE_INVALID", f"schedule must be HH:MM, got {schedule!r}") from exc


def next_run_at(
    timezone_name: str,
    schedule: str = DEFAULT_SCHEDULE,
    *,
    after: datetime | None = None,
) -> datetime:
    tz = ZoneInfo(timezone_name or DEFAULT_TIMEZONE)
    now = after.astimezone(tz) if after else datetime.now(tz)
    hhmm = parse_schedule(schedule)
    candidate = now.replace(hour=hhmm.hour, minute=hhmm.minute, second=0, microsecond=0)
    if candidate <= now:
        candidate = candidate + timedelta(days=1)
    return candidate


def is_due(head: dict[str, Any], *, now: datetime | None = None) -> bool:
    if not head.get("automation_enabled"):
        return False
    tz_name = str(head.get("timezone") or DEFAULT_TIMEZONE)
    tz = ZoneInfo(tz_name)
    current = now.astimezone(tz) if now else datetime.now(tz)
    nxt = head.get("next_run_at")
    if not nxt:
        return True
    due = datetime.fromisoformat(str(nxt).replace("Z", "+00:00")).astimezone(tz)
    return current >= due


def due_runs(heads: list[dict[str, Any]], *, now: datetime | None = None) -> list[str]:
    return [str(h["stax_id"]) for h in heads if is_due(h, now=now)]


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def arm_automation(
    head: dict[str, Any],
    *,
    enabled: bool,
    timezone_name: str | None = None,
    schedule: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    rec = dict(head)
    rec["automation_enabled"] = bool(enabled)
    if timezone_name:
        rec["timezone"] = timezone_name
    if schedule:
        parse_schedule(schedule)
        rec["automation_schedule"] = schedule
    rec["updated_at"] = utc_now()
    if rec["automation_enabled"]:
        rec["next_run_at"] = _iso(
            next_run_at(
                str(rec.get("timezone") or DEFAULT_TIMEZONE),
                str(rec.get("automation_schedule") or DEFAULT_SCHEDULE),
                after=now,
            )
        )
    return rec


def assert_saved_timeframe(members: list[dict[str, Any]]) -> None:
    """Guard: member universes still carry the saved dates. No 'today' rewrite."""
    for member in members:
        uni = canonicalize_universe(member["universe"])
        member_uni = member.get("universe") or {}
        if member_uni.get("date_from") != uni.date_from or member_uni.get("date_to") != uni.date_to:
            raise StaxError(
                "STAX_TIMEFRAME_MUTATED",
                "automation must not rewrite the saved timeframe",
            )


def run_due(
    stax_id: str,
    *,
    root=None,
    now: datetime | None = None,
    run_stack: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from roller.stax.runner import persist_run, run_stax

    head = load_head(stax_id, root=root)
    members = list(head.get("working_members") or [])
    assert_saved_timeframe(members)
    scheduled = head.get("next_run_at")
    started = utc_now()
    if run_stack is None:
        out = run_stax(stax_id, root=root, automated=True)
    else:
        out = persist_run(stax_id, members, root=root, automated=True, execute_fn=run_stack)
    completed = utc_now()
    execution_id = str(out.get("execution_id") or uuid.uuid4().hex)
    run = {
        "execution_id": execution_id,
        "stax_id": stax_id,
        "stax_version": out.get("version"),
        "scheduled_at": scheduled,
        "started_at": started,
        "completed_at": completed,
        "timezone": head.get("timezone"),
        "strategy_count": out.get("strategy_count"),
        "completed_count": out.get("completed_count"),
        "failed_count": out.get("failed_count"),
        "status": out.get("status"),
        "dataset_versions": [
            (r.get("summary") or {}).get("dataset_version") for r in (out.get("results") or [])
        ],
        "dataset_hashes": [
            (r.get("summary") or {}).get("dataset_version") for r in (out.get("results") or [])
        ],
        "error_metadata": [r.get("error") for r in (out.get("results") or []) if r.get("error")],
        "live_execution": LIVE_EXECUTION,
        "research_automation": True,
        "timeframe_expanded": False,
    }
    write_run(stax_id, run, root=root)
    latest = load_head(stax_id, root=root)
    latest["last_run_at"] = completed
    latest["next_run_at"] = _iso(
        next_run_at(
            str(latest.get("timezone") or DEFAULT_TIMEZONE),
            str(latest.get("automation_schedule") or DEFAULT_SCHEDULE),
            after=now or datetime.now(timezone.utc),
        )
    )
    write_head(latest, root=root)
    return {**out, "run": run}


_LOOP_STARTED = False
_LOOP_LOCK = threading.Lock()


def tick(*, root=None, now: datetime | None = None) -> dict[str, Any]:
    from roller.stax.library import list_stax_ids

    ran = []
    errors = []
    for stax_id in list_stax_ids(root):
        try:
            head = load_head(stax_id, root=root)
        except StaxError:
            continue
        if not is_due(head, now=now):
            continue
        try:
            ran.append(run_due(stax_id, root=root, now=now))
        except Exception as exc:  # noqa: BLE001 — audit; do not abort other stacks
            errors.append({"stax_id": stax_id, "error": str(exc)})
    return {"ran": ran, "errors": errors, "n": len(ran), "live_execution": LIVE_EXECUTION}


def ensure_loop(*, interval_s: int = 60) -> None:
    global _LOOP_STARTED
    with _LOOP_LOCK:
        if _LOOP_STARTED:
            return
        _LOOP_STARTED = True

    def _loop() -> None:
        while True:
            try:
                tick()
            except Exception:
                pass
            threading.Event().wait(interval_s)

    threading.Thread(target=_loop, name="stax-automation", daemon=True).start()
