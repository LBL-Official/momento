"""Capability router. Systimo approves the tunnel; Jump does not own the source."""

from __future__ import annotations

import uuid
from typing import Any, Callable

from roller.jump.data.adapters import austin, ballhog, choosin, drevo, positman, roller, systimo, tk_ultra, vital
from roller.jump.data.catalog import require_query_connection
from roller.jump.data.models import LIVE_EXECUTION, SCHEMA, now_iso
from roller.jump.errors import JumpError

Handler = Callable[[dict[str, Any]], dict[str, Any]]

HANDLERS: dict[str, Handler] = {
    "AUSTIN_QUERY_AT": austin.query_at_payload,
    "AUSTIN_GET_TRADE": austin.get_trade_payload,
    "AUSTIN_REPLAY": austin.replay_payload,
    "AUSTIN_UNIVERSE": lambda _p: austin.list_universe(),
    "CHOOSIN_TRADE_CONTEXT": choosin.trade_context,
    "WAREHOUSE_QUERY": roller.warehouse_query,
    "ROLLER_GAME_IDENTITY": roller.game_identity,
    "ROLLER_OBSERVATIONS": roller.observations,
    "ROLLER_PBP": roller.pbp,
    "ROLLER_SETTLEMENT": roller.settlement,
    "ROLLER_DATASET": lambda p: roller.dataset_handle(p),
    "BALLHOG_INTENT": ballhog.intent,
    "TK_ULTRA_ASSESSMENT": tk_ultra.assess,
    "POSITMAN_PLAN": positman.plan,
    "DREVO_DECISION": drevo.decision,
    "VITAL_BOT_STATUS": vital.status,
    "SYSTIMO_CATALOG": systimo.catalog,
}


def envelope(
    *,
    capability: str,
    connection: dict[str, str],
    result: dict[str, Any],
    params: dict[str, Any],
    query_id: str,
    lineage_id: str | None,
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "query_id": query_id,
        "source_system": connection.get("source_system_id") or result.get("source_system"),
        "source_resource": connection.get("source_interface") or capability,
        "connection_id": connection.get("connection_id"),
        "capability": capability,
        "as_of": params.get("as_of"),
        "data_mode": result.get("data_mode") or connection.get("data_mode"),
        "universe": result.get("universe"),
        "n": result.get("n"),
        "result": result,
        "provenance": {
            "owner": connection.get("source_system_id"),
            "adapter": connection.get("adapter"),
            "permission": connection.get("permission"),
            "copy": False,
            "live_execution": LIVE_EXECUTION,
        },
        "lineage_id": lineage_id,
        "warnings": warnings,
        "completed_at": now_iso(),
        "live_execution": LIVE_EXECUTION,
    }


def dispatch(capability: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(params or {})
    query_id = uuid.uuid4().hex[:16]
    connection = require_query_connection(capability)
    handler = HANDLERS.get(capability)
    if handler is None:
        raise JumpError("UNREGISTERED_INTERFACE", f"no Jump handler for {capability}")
    warnings: list[str] = []
    result = handler(payload)
    if result.get("availability") == "UNAVAILABLE":
        warnings.append(str(result.get("detail") or result.get("error_code") or "UNAVAILABLE"))
    lineage_id = None
    if payload.get("with_lineage"):
        from roller.jump.data.lineage import for_result

        lineage = for_result(capability, result, payload)
        lineage_id = lineage.get("lineage_id")
        result = {**result, "lineage": lineage}
    return envelope(
        capability=capability,
        connection=connection,
        result=result,
        params=payload,
        query_id=query_id,
        lineage_id=lineage_id,
        warnings=warnings,
    )


def capabilities() -> list[str]:
    return sorted(HANDLERS)
