"""ROLLER warehouse read adapter. Pointers only. Never copies parquet."""

from __future__ import annotations

from typing import Any

from roller.jump.data.models import LIVE_EXECUTION, NBA_WAREHOUSE, UNAVAILABLE
from roller.jump.errors import JumpError


def _rows(table: str, params: dict[str, Any]) -> dict[str, Any]:
    from roller.jump.warehouse.api import handle_rows

    warehouse_id = str(params.get("warehouse_id") or NBA_WAREHOUSE)
    filters = list(params.get("filters") or [])
    ticker = params.get("ticker")
    if ticker and not any(str(item.get("column")) == "ticker" for item in filters):
        filters.append({"column": "ticker", "op": "eq", "value": ticker})
    game_id = params.get("internal_game_id") or params.get("game_id")
    if game_id and not any(str(item.get("column")) == "internal_game_id" for item in filters):
        filters.append({"column": "internal_game_id", "op": "eq", "value": game_id})
    as_of = params.get("as_of")
    if as_of and table in {"observations"} and not any(str(item.get("column")) == "available_at" for item in filters):
        filters.append({"column": "available_at", "op": "lte", "value": as_of})
    try:
        body = handle_rows(
            warehouse_id,
            table,
            limit=int(params.get("limit") or 50),
            page=int(params.get("page") or 1),
            filters=filters,
        )
    except JumpError as exc:
        return {
            "availability": UNAVAILABLE,
            "source_system": "roller",
            "warehouse_id": warehouse_id,
            "table": table,
            "error_code": exc.code,
            "detail": exc.message,
            "live_execution": LIVE_EXECUTION,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "availability": UNAVAILABLE,
            "source_system": "roller",
            "warehouse_id": warehouse_id,
            "table": table,
            "detail": f"{type(exc).__name__}: {exc}",
            "live_execution": LIVE_EXECUTION,
        }
    rows = body.get("rows") if isinstance(body, dict) else None
    return {
        "availability": "OBSERVED" if rows is not None else UNAVAILABLE,
        "source_system": "roller",
        "owner": "ROLLER",
        "warehouse_id": warehouse_id,
        "table": table,
        "data_mode": "WAREHOUSE_POINTER",
        "permission": "QUERY",
        "write": "DENY",
        "row_count": body.get("n") or body.get("row_count") or (len(rows) if isinstance(rows, list) else 0),
        "rows": rows if isinstance(rows, list) else [],
        "live_execution": LIVE_EXECUTION,
        "handle": {
            "dataset_id": f"roller.{warehouse_id}.{table}",
            "owner": "roller",
            "location": f"/jump/warehouses/{warehouse_id}/tables/{table}/rows",
            "copy": False,
        },
    }


def game_identity(params: dict[str, Any]) -> dict[str, Any]:
    if params.get("ticker"):
        return _rows("game_market_links", params)
    return _rows("games", params)


def observations(params: dict[str, Any]) -> dict[str, Any]:
    return _rows("observations", params)


def pbp(params: dict[str, Any]) -> dict[str, Any]:
    return _rows("pbp", params)


def settlement(params: dict[str, Any]) -> dict[str, Any]:
    return _rows("settlements", params)


def warehouse_query(params: dict[str, Any]) -> dict[str, Any]:
    table = str(params.get("table") or params.get("resource") or "games")
    return _rows(table, params)


def dataset_handle(params: dict[str, Any] | None = None) -> dict[str, Any]:
    from roller.jump.warehouse.registry import get_warehouse

    payload = params if isinstance(params, dict) else {}
    warehouse_id = str(payload.get("warehouse_id") or NBA_WAREHOUSE)
    rec = get_warehouse(warehouse_id)
    body = rec.as_dict()
    manifest = body.get("manifest") if isinstance(body.get("manifest"), dict) else {}
    return {
        "schema": "jump.dataset_handle.v0",
        "dataset_id": f"roller.{warehouse_id}",
        "owner": "roller",
        "source_system": "roller",
        "schema_version": "warehouse_v1",
        "row_count": manifest.get("observation_rows"),
        "location": body.get("source_uri"),
        "query_capabilities": [
            "ROLLER_GAME_IDENTITY",
            "ROLLER_OBSERVATIONS",
            "ROLLER_PBP",
            "ROLLER_SETTLEMENT",
            "WAREHOUSE_QUERY",
        ],
        "filters_supported": ["ticker", "internal_game_id", "limit", "page"],
        "status": body.get("status"),
        "copy": False,
        "live_execution": LIVE_EXECUTION,
        "unavailable_reason": body.get("unavailable_reason"),
    }
