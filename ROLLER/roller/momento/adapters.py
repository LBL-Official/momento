"""Delegate to existing desks. Do not copy engines. Never fake green."""

from __future__ import annotations

from typing import Any

from roller.momento.registry import SystemRecord, load_registry
from roller.momento.systems.notes import LOGIC_NOTES


def system_payload(row: SystemRecord) -> dict[str, Any]:
    return {
        "id": row.id,
        "display_name": row.display_name,
        "short_name": row.short_name,
        "visual_subtitle": row.extra.get("visual_subtitle"),
        "bracket_round": row.bracket_round,
        "bracket_position": row.bracket_position,
        "purpose": row.purpose,
        "status": row.status,
        "version": row.version,
        "implementation_paths": list(row.implementation_paths),
        "research_paths": list(row.research_paths),
        "frontend_target": dict(row.frontend_target),
        "backend_target": dict(row.backend_target),
        "api_namespace": row.api_namespace,
        "upstream_systems": list(row.upstream_systems),
        "downstream_systems": list(row.downstream_systems),
        "input_contracts": list(row.input_contracts),
        "output_contracts": list(row.output_contracts),
        "health_check": row.health_check,
        "feature_flags": list(row.feature_flags),
        "live_capability": False,
        "migration_sources": list(row.migration_sources),
        "notes": row.notes,
        "extra": dict(row.extra),
    }


def logic_payload(row: SystemRecord) -> dict[str, Any]:
    return {
        "system_id": row.id,
        "status": row.status,
        "logic": LOGIC_NOTES.get(row.id, row.purpose),
        "implementation_paths": list(row.implementation_paths),
        "limitations": row.notes,
        "live_execution": False,
    }


def _meta(system_id: str) -> dict[str, Any]:
    row = load_registry().by_id().get(system_id)
    return {
        "version": row.version if row else None,
        "feature_flags": list(row.feature_flags) if row else [],
        "research_vs_live": "research",
        "frontend_probe": "UNKNOWN",
        "live_capability": False,
    }


def _unknown(system_id: str, detail: str) -> dict[str, Any]:
    body = {
        "system_id": system_id,
        "state": "UNKNOWN",
        "ok": None,
        "live_execution": False,
        "detail": detail,
    }
    body.update(_meta(system_id))
    return body


def _state(system_id: str, state: str, detail: str, *, ok: bool | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    body = {
        "system_id": system_id,
        "state": state,
        "ok": ok,
        "live_execution": False,
        "detail": detail,
    }
    body.update(_meta(system_id))
    if extra:
        body.update(extra)
    return body


def probe_health(system_id: str) -> dict[str, Any]:
    row = load_registry().by_id().get(system_id)
    if row is None:
        return _unknown(system_id, "unknown system")
    if system_id == "database":
        from roller.jump.warehouse.registry import get_warehouse

        nba = get_warehouse("nba")
        ncaab = get_warehouse("ncaab")
        return _state(
            system_id,
            "RESEARCH_ONLY",
            f"ROLLER warehouse. NBA {nba.status}. NCAAB {ncaab.status}.",
            ok=True,
            extra={
                "delegate": "/momento/connection",
                "nba": nba.status,
                "ncaab": ncaab.status,
            },
        )
    if system_id == "data_analysis":
        from roller.superasi.versions import CODE_VERSION

        return _state(system_id, "RESEARCH_ONLY", f"SuperASI {CODE_VERSION}.", ok=True, extra={"delegate": "/superasi"})
    if system_id == "trade_breakdown":
        from roller.choosin_texas.api import handle_health

        payload = handle_health()
        return _state(
            system_id,
            "RESEARCH_ONLY",
            "Choosin Texas locked desk.",
            ok=bool(payload.get("ok")),
            extra={"delegate": "/choosin-texas/health", "payload": payload},
        )
    if system_id == "dynamic_risk_engine":
        from roller.dre.api import handle_health

        payload = handle_health()
        return _state(
            system_id,
            "RESEARCH_ONLY",
            "DRE adapter. Not crates/risk. Not execution policy.",
            ok=bool(payload.get("ok")),
            extra={"delegate": "/dre/health", "payload": payload},
        )
    if system_id == "relative_value_hedging":
        try:
            from roller.momento.tk_ultra import handle_desk

            payload = handle_desk()
            return _state(
                system_id,
                "RESEARCH_ONLY",
                "TK Ultra desk. Formula only. Not market truth.",
                ok=None,
                extra={"delegate": "/momento/tk-ultra", "title": payload.get("title")},
            )
        except Exception as exc:  # noqa: BLE001 — fail open to UNKNOWN
            return _unknown(system_id, f"TK Ultra unread: {type(exc).__name__}")
    if system_id == "hedging_analysis":
        from roller.ballhog.api import handle_health

        payload = handle_health()
        return _state(
            system_id,
            "RESEARCH_ONLY",
            "Ballhog exposure-removal optimizer. Not a fill. Not execution.",
            ok=bool(payload.get("ok")),
            extra={"delegate": "/ballhog/health", "payload": payload},
        )
    if system_id == "position_stratification":
        from roller.austin.api import handle_health

        payload = handle_health()
        return _state(
            system_id,
            "RESEARCH_ONLY",
            "Austin package. Not crates/risk. Not execution policy.",
            ok=bool(payload.get("ok")),
            extra={"delegate": "/austin/health", "payload": payload},
        )
    if system_id == "data_ingestion":
        try:
            from roller.auto_roller.status import status_payload

            payload = status_payload()
            return _state(
                system_id,
                "PARTIAL",
                "auto_roller status. Autojest NOT_IMPLEMENTED.",
                ok=True,
                extra={"delegate": "/auto-roller/status", "payload": payload},
            )
        except Exception as exc:  # noqa: BLE001 — fail open to UNKNOWN
            return _unknown(system_id, f"auto_roller unread: {type(exc).__name__}")
    if system_id == "system_maintenance":
        return _probe_systimo(system_id)
    if row.status == "NOT_IMPLEMENTED":
        return _state(system_id, "NOT_IMPLEMENTED", row.notes, ok=None)
    if row.status == "PARTIAL":
        return _state(system_id, "RESEARCH_ONLY", row.notes, ok=None)
    return _state(system_id, "RESEARCH_ONLY", row.notes, ok=None)


def _probe_systimo(system_id: str) -> dict[str, Any]:
    try:
        from roller.systimo.api import handle_health

        payload = handle_health()
        return _state(
            system_id,
            "PARTIAL",
            "Systimo Frontend. Momento LS remains the live-host observe adapter.",
            ok=bool(payload.get("ok")),
            extra={
                "delegate": "/systimo/health",
                "payload": payload,
                "ls_observe": "adapter",
            },
        )
    except Exception as exc:  # noqa: BLE001 — fail closed to UNKNOWN
        return _unknown(system_id, f"Systimo unread: {type(exc).__name__}")
