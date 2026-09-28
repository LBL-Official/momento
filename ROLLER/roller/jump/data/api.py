"""Jump canonical data-plane HTTP handlers."""

from __future__ import annotations

from typing import Any

from roller.jump.data.catalog import source, sources
from roller.jump.data.context import compose
from roller.jump.data.export import dataset_handles, export_dataset
from roller.jump.data.lineage import show_source
from roller.jump.data.models import DEFAULT_TRADE_ID, LIVE_EXECUTION, SCHEMA
from roller.jump.data.router import capabilities, dispatch
from roller.jump.data.tree import from_context
from roller.jump.errors import JumpError


def handle_sources() -> dict[str, Any]:
    rows = sources()
    return {
        "schema": SCHEMA,
        "sources": rows,
        "n": len(rows),
        "capabilities": capabilities(),
        "live_execution": LIVE_EXECUTION,
        "write": "DENY",
    }


def handle_source(system_id: str) -> dict[str, Any]:
    return source(system_id)


def _clean(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value not in (None, "")}


def handle_query(body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = body if isinstance(body, dict) else {}
    capability = str(payload.get("capability") or payload.get("query_type") or "").strip()
    if not capability:
        raise JumpError("INVALID_INPUT", "capability required")
    params = _clean(dict(payload))
    params.pop("capability", None)
    params.pop("query_type", None)
    return dispatch(capability, params)


def handle_context(trade_id: str | None = None, as_of: str | None = None) -> dict[str, Any]:
    context = compose(trade_id or DEFAULT_TRADE_ID, as_of)
    return {**context, "tree": from_context(context)}


def handle_lineage(resource_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = _clean(body if isinstance(body, dict) else {})
    capability = str(payload.get("capability") or resource_id or "AUSTIN_QUERY_AT").strip()
    aliases = {
        "austin": "AUSTIN_QUERY_AT",
        "choosin": "CHOOSIN_TRADE_CONTEXT",
        "choosin_texas": "CHOOSIN_TRADE_CONTEXT",
        "ballhog": "BALLHOG_INTENT",
        "tk_ultra": "TK_ULTRA_ASSESSMENT",
        "roller": "ROLLER_OBSERVATIONS",
    }
    capability = aliases.get(capability, capability)
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    if not result:
        queried = dispatch(capability, payload)
        result = queried.get("result") or {}
        payload = {**payload, "as_of": queried.get("as_of")}
    return show_source(capability, result, payload)


def handle_datasets() -> dict[str, Any]:
    rows = dataset_handles()
    return {"schema": "jump.dataset_handle.v0", "datasets": rows, "n": len(rows), "live_execution": LIVE_EXECUTION}


def handle_export(body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = body if isinstance(body, dict) else {}
    dataset_id = str(payload.get("dataset_id") or "").strip()
    if not dataset_id:
        raise JumpError("INVALID_INPUT", "dataset_id required")
    return export_dataset(dataset_id, payload)
