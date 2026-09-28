"""Jump warehouse HTTP handlers. Read-only desk. No parquet writes."""

from __future__ import annotations

from typing import Any

from roller.jump.errors import JumpError
from roller.jump.versions import LIVE_EXECUTION
from roller.jump.warehouse.parquet_desk import (
    adapter_for,
    reset_connections,
    table_spec,
)
from roller.jump.warehouse.queries import (
    create_saved,
    delete_saved,
    get_saved,
    list_saved,
    patch_saved,
)
from roller.jump.warehouse.registry import get_warehouse, list_warehouses, require_available
from roller.jump.warehouse.relationships import relationship_graph, save_layout
from roller.jump.warehouse.sql_guard import assert_readonly_sql


def handle_list() -> dict[str, Any]:
    rows = [row.as_dict() for row in list_warehouses()]
    return {
        "warehouses": rows,
        "count": len(rows),
        "live_execution": LIVE_EXECUTION,
        "writable": False,
    }


def handle_get(warehouse_id: str) -> dict[str, Any]:
    rec = get_warehouse(warehouse_id)
    body = rec.as_dict()
    if rec.status != "AVAILABLE":
        return {
            **body,
            "tables": [],
            "unavailable": True,
        }
    desk = adapter_for(warehouse_id)
    return desk.inspect()


def handle_tables(warehouse_id: str) -> dict[str, Any]:
    desk = adapter_for(warehouse_id)
    return {
        "warehouse_id": warehouse_id,
        "tables": desk.list_tables(),
        "unavailable_sources": desk.unavailable_sources(),
        "live_execution": LIVE_EXECUTION,
    }


def handle_table(warehouse_id: str, table: str) -> dict[str, Any]:
    return adapter_for(warehouse_id).describe_table(table)


def handle_columns(warehouse_id: str, table: str) -> dict[str, Any]:
    desk = adapter_for(warehouse_id)
    return {
        "warehouse_id": warehouse_id,
        "table": table,
        "columns": desk.columns(table),
        "live_execution": LIVE_EXECUTION,
    }


def handle_rows(
    warehouse_id: str,
    table: str,
    *,
    limit: int | None = None,
    page: int | None = None,
    sort: str | None = None,
    order: str = "asc",
    columns: str | list[str] | None = None,
    filters: Any = None,
) -> dict[str, Any]:
    proj = None
    if isinstance(columns, list):
        proj = [str(c) for c in columns]
    elif isinstance(columns, str) and columns.strip():
        proj = [part.strip() for part in columns.split(",") if part.strip()]
    from roller.jump.warehouse.parquet_desk import _parse_filters

    return adapter_for(warehouse_id).preview_rows(
        table,
        columns=proj,
        limit=limit or 100,
        page=page or 1,
        sort=sort,
        order=order,
        filters=_parse_filters(filters),
    )


def handle_stats(warehouse_id: str, table: str, *, compute: bool = False) -> dict[str, Any]:
    return adapter_for(warehouse_id).stats(table, compute=compute)


def handle_lineage(warehouse_id: str, table: str) -> dict[str, Any]:
    return adapter_for(warehouse_id).lineage(table)


def handle_dictionary(warehouse_id: str) -> dict[str, Any]:
    return adapter_for(warehouse_id).dictionary()


def handle_files(warehouse_id: str) -> dict[str, Any]:
    return adapter_for(warehouse_id).physical_files()


def handle_relationships(warehouse_id: str) -> dict[str, Any]:
    return relationship_graph(warehouse_id)


def handle_relationships_layout(warehouse_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = body or {}
    layout = payload.get("layout") if isinstance(payload.get("layout"), dict) else payload
    return save_layout(warehouse_id, layout if isinstance(layout, dict) else {})


def handle_query(warehouse_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = body or {}
    sql = str(payload.get("sql") or "")
    limit = payload.get("limit")
    return adapter_for(warehouse_id).query(sql, limit=int(limit) if limit else 100)


def handle_refresh(warehouse_id: str) -> dict[str, Any]:
    reset_connections()
    rec = get_warehouse(warehouse_id)
    if rec.status != "AVAILABLE":
        raise JumpError("WAREHOUSE_UNAVAILABLE", rec.unavailable_reason or rec.id)
    return adapter_for(warehouse_id).refresh_metadata()


def handle_validate(warehouse_id: str) -> dict[str, Any]:
    rec = get_warehouse(warehouse_id)
    if rec.status != "AVAILABLE":
        return {
            "warehouse_id": rec.id,
            "status": "WAREHOUSE_UNAVAILABLE",
            "source_uri": rec.source_uri,
            "reason": rec.unavailable_reason,
            "live_execution": LIVE_EXECUTION,
        }
    return adapter_for(warehouse_id).validate()


def handle_views(warehouse_id: str) -> dict[str, Any]:
    require_available(warehouse_id)
    return {
        "warehouse_id": warehouse_id,
        "views": list_saved("view", warehouse_id=warehouse_id),
        "materialized": False,
        "live_execution": LIVE_EXECUTION,
    }


def handle_view_create(warehouse_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    require_available(warehouse_id)
    payload = body or {}
    return create_saved(
        warehouse_id=warehouse_id,
        name=str(payload.get("name") or ""),
        sql=str(payload.get("sql") or ""),
        kind="view",
        description=str(payload.get("description") or ""),
    )


def handle_queries_list(warehouse_id: str | None = None) -> dict[str, Any]:
    return {
        "queries": list_saved("query", warehouse_id=warehouse_id),
        "live_execution": LIVE_EXECUTION,
    }


def handle_query_get(query_id: str) -> dict[str, Any]:
    return {"query": get_saved(query_id, kind="query"), "live_execution": LIVE_EXECUTION}


def handle_query_create(body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = body or {}
    warehouse_id = str(payload.get("warehouse_id") or "").strip()
    require_available(warehouse_id)
    assert_readonly_sql(str(payload.get("sql") or ""))
    return create_saved(
        warehouse_id=warehouse_id,
        name=str(payload.get("name") or ""),
        sql=str(payload.get("sql") or ""),
        kind="query",
        description=str(payload.get("description") or ""),
    )


def handle_query_patch(query_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    return patch_saved(query_id, body or {}, kind="query")


def handle_query_delete(query_id: str) -> dict[str, Any]:
    return delete_saved(query_id, kind="query")


__all__ = [
    "handle_list",
    "handle_get",
    "handle_tables",
    "handle_table",
    "handle_columns",
    "handle_rows",
    "handle_stats",
    "handle_lineage",
    "handle_dictionary",
    "handle_files",
    "handle_relationships",
    "handle_relationships_layout",
    "handle_query",
    "handle_refresh",
    "handle_validate",
    "handle_views",
    "handle_view_create",
    "handle_queries_list",
    "handle_query_get",
    "handle_query_create",
    "handle_query_patch",
    "handle_query_delete",
    "table_spec",
]
