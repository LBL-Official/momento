"""Deterministic connection health. Not RUNNING. Lock drift is INTEGRITY_DRIFT."""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable

from roller.systimo.models import AUSTIN_N, CHOOSIN_N, now_iso
from roller.systimo.store import CsvStore

CheckFn = Callable[[dict[str, str]], dict[str, Any]]


def _ok(status: str, **extra: Any) -> dict[str, Any]:
    return {"status": status, **extra}


def check_austin_lock(row: dict[str, str]) -> dict[str, Any]:
    from roller.austin.locks import N_TRADES

    expected = row.get("expected_lock") or f"N={AUSTIN_N}"
    if str(N_TRADES) != str(AUSTIN_N) or expected not in {f"N={AUSTIN_N}", f"{AUSTIN_N}", f"N={N_TRADES}"}:
        if str(N_TRADES) != str(AUSTIN_N):
            return _ok(
                "MISCONFIGURED",
                error_code="INTEGRITY_DRIFT",
                error_message=f"Austin N={N_TRADES} expected {AUSTIN_N}",
                n_observed=str(N_TRADES),
            )
    try:
        from roller.dre.adapters.austin import query_at  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        return _ok("UNAVAILABLE", error_code="IMPORT_FAILED", error_message=str(exc))
    return _ok("HEALTHY", n_observed=str(N_TRADES))


def check_choosin_lock(row: dict[str, str]) -> dict[str, Any]:
    from roller.choosin_texas.locks import POOL_N

    if int(POOL_N) != CHOOSIN_N:
        return _ok(
            "MISCONFIGURED",
            error_code="INTEGRITY_DRIFT",
            error_message=f"Choosin N={POOL_N} expected {CHOOSIN_N}",
            n_observed=str(POOL_N),
        )
    try:
        from roller.dre.adapters.choosin import get_trade_context  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        return _ok("UNAVAILABLE", error_code="IMPORT_FAILED", error_message=str(exc))
    return _ok("HEALTHY", n_observed=str(POOL_N))


def check_import(module: str) -> dict[str, Any]:
    try:
        __import__(module)
    except Exception as exc:  # noqa: BLE001
        return _ok("UNAVAILABLE", error_code="IMPORT_FAILED", error_message=str(exc))
    return _ok("HEALTHY")


def check_declared_unavailable(_row: dict[str, str]) -> dict[str, Any]:
    return _ok(
        "UNAVAILABLE",
        error_code="POSITION_MANAGEMENT_NOT_IMPLEMENTED",
        error_message="Position Management is NOT_IMPLEMENTED",
    )


def check_ls(_row: dict[str, str]) -> dict[str, Any]:
    from urllib.error import URLError
    from urllib.request import urlopen

    try:
        with urlopen("http://127.0.0.1:8792/health", timeout=0.4) as resp:
            resp.read(64)
        return _ok("HEALTHY")
    except (URLError, TimeoutError, OSError) as exc:
        return _ok("UNKNOWN", error_code="LS_UNREAD", error_message=str(exc))


ADAPTERS: dict[str, CheckFn] = {
    "roller.ballhog.adapters.austin": check_austin_lock,
    "roller.tk_ultra.adapters.austin": check_austin_lock,
    "roller.dre.adapters.austin": check_austin_lock,
    "roller.jump.adapters.austin": check_austin_lock,
    "roller.jump.data.adapters.austin": check_austin_lock,
    "roller.ballhog.adapters.choosin": check_choosin_lock,
    "roller.tk_ultra.adapters.choosin": check_choosin_lock,
    "roller.dre.adapters.choosin": check_choosin_lock,
    "roller.jump.adapters.choosin": check_choosin_lock,
    "roller.jump.vital_client": lambda _r: check_import("roller.jump.vital_client"),
    "roller.jump.warehouse.registry": lambda _r: check_import("roller.jump.warehouse.registry"),
    "roller.jump.data.adapters.roller": lambda _r: check_import("roller.jump.data.adapters.roller"),
    "roller.jump.data.adapters.ballhog": lambda _r: check_import("roller.ballhog.api"),
    "roller.jump.data.adapters.tk_ultra": lambda _r: check_import("roller.tk_ultra.api"),
    "roller.jump.data.adapters.systimo": lambda _r: check_import("roller.jump.data.adapters.systimo"),
    "roller.jump.data.adapters.positman": lambda _r: check_import("roller.positman.api"),
    "roller.jump.data.adapters.drevo": lambda _r: check_import("roller.dre.decision"),
    "roller.positman.adapters.ballhog": lambda _r: check_import("roller.positman.adapters.ballhog"),
    "roller.positman.adapters.tk_ultra": lambda _r: check_import("roller.positman.adapters.tk_ultra"),
    "roller.dre.positman_adapter": lambda _r: check_import("roller.dre.positman_adapter"),
    "roller.positman.api": lambda _r: check_import("roller.positman.api"),
    "roller.dre.decision": lambda _r: check_import("roller.dre.decision"),
    "roller.systimo.transitions": lambda _r: check_import("roller.systimo.transitions"),
    "roller.jump.iti": lambda _r: check_import("roller.jump.iti"),
    "roller.tk_ultra.adapters.ballhog": lambda _r: check_import("roller.tk_ultra.adapters.ballhog"),
    "none": check_declared_unavailable,
    "roller.systimo.adapters.ls": check_ls,
}


def check_connection(row: dict[str, str]) -> dict[str, Any]:
    if row.get("lifecycle") == "DECLARED" and row.get("adapter") in {"", "none"}:
        return check_declared_unavailable(row)
    fn = ADAPTERS.get(row.get("adapter") or "")
    if fn is None:
        return _ok("UNKNOWN", error_code="NO_CHECK", error_message="no health adapter")
    return fn(row)


def refresh(store: CsvStore | None = None, *, connection_id: str | None = None) -> dict[str, Any]:
    csv = store or CsvStore()
    rows = csv.read("connections")
    results = []
    for row in rows:
        if connection_id and row["connection_id"] != connection_id:
            continue
        started = time.perf_counter()
        result = check_connection(row)
        latency = str(int((time.perf_counter() - started) * 1000))
        status = str(result.get("status") or "UNKNOWN")
        previous = row.get("health") or "UNKNOWN"
        observed = now_iso()
        event_id = uuid.uuid4().hex[:16]
        snap_id = uuid.uuid4().hex[:16]
        csv.append(
            "connection_events",
            {
                "event_id": event_id,
                "connection_id": row["connection_id"],
                "observed_at": observed,
                "previous_status": previous,
                "new_status": status,
                "check_type": "REFRESH",
                "latency_ms": latency,
                "error_code": result.get("error_code") or "",
                "error_message": result.get("error_message") or "",
                "source_timestamp": observed,
            },
        )
        csv.append(
            "health_snapshots",
            {
                "snapshot_id": snap_id,
                "connection_id": row["connection_id"],
                "observed_at": observed,
                "status": status,
                "check_type": "REFRESH",
                "latency_ms": latency,
                "error_code": result.get("error_code") or "",
                "error_message": result.get("error_message") or "",
                "source_timestamp": observed,
                "n_observed": result.get("n_observed") or "",
            },
        )
        updated = dict(row)
        updated["health"] = status
        updated["last_check_at"] = observed
        updated["latency_ms"] = latency
        updated["reason"] = result.get("error_code") or row.get("reason") or ""
        if status == "HEALTHY":
            updated["last_success_at"] = observed
        else:
            updated["last_failure_at"] = observed
        csv.upsert("connections", updated)
        results.append({"connection_id": row["connection_id"], "health": status, **result})
    from roller.systimo.graph.build import write_generated

    write_generated(csv)
    return {"ok": True, "checked": len(results), "results": results, "generated_at": now_iso()}
