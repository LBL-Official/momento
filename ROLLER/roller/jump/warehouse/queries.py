"""Jump-owned saved queries and logical views. Not materialized parquet."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from roller.jump.errors import JumpError
from roller.jump.versions import LIVE_EXECUTION
from roller.jump.warehouse.catalog import load_catalog, save_catalog
from roller.jump.warehouse.sql_guard import assert_readonly_sql


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _kind_rows(catalog: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    key = "queries" if kind == "query" else "views"
    rows = catalog.get(key) or []
    return [row for row in rows if isinstance(row, dict)]


def list_saved(kind: str = "query", *, warehouse_id: str | None = None, root=None) -> list[dict[str, Any]]:
    catalog = load_catalog(root=root)
    rows = _kind_rows(catalog, kind)
    if warehouse_id:
        rows = [row for row in rows if row.get("warehouse_id") == warehouse_id]
    return rows


def get_saved(saved_id: str, *, kind: str = "query", root=None) -> dict[str, Any]:
    wanted = str(saved_id or "").strip()
    for row in list_saved(kind, root=root):
        if row.get("id") == wanted:
            return row
    raise JumpError("RESULT_NOT_FOUND", f"unknown {kind} {saved_id}")


def create_saved(
    *,
    warehouse_id: str,
    name: str,
    sql: str,
    kind: str = "query",
    description: str = "",
    root=None,
) -> dict[str, Any]:
    stmt = assert_readonly_sql(sql)
    title = str(name or "").strip()
    if not title:
        raise JumpError("QUERY_REJECTED", f"{kind} name is required")
    catalog = load_catalog(root=root)
    key = "queries" if kind == "query" else "views"
    row = {
        "id": str(uuid.uuid4()),
        "kind": kind,
        "warehouse_id": warehouse_id,
        "name": title,
        "sql": stmt,
        "description": str(description or ""),
        "materialized": False,
        "created_at": _utc(),
        "updated_at": _utc(),
        "live_execution": LIVE_EXECUTION,
    }
    catalog.setdefault(key, []).append(row)
    save_catalog(catalog, root=root)
    return row


def patch_saved(saved_id: str, body: dict[str, Any], *, kind: str = "query", root=None) -> dict[str, Any]:
    catalog = load_catalog(root=root)
    key = "queries" if kind == "query" else "views"
    rows = catalog.get(key) or []
    for i, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("id") != saved_id:
            continue
        next_row = dict(row)
        if "name" in body and str(body.get("name") or "").strip():
            next_row["name"] = str(body["name"]).strip()
        if "description" in body:
            next_row["description"] = str(body.get("description") or "")
        if "sql" in body:
            next_row["sql"] = assert_readonly_sql(str(body.get("sql") or ""))
        next_row["updated_at"] = _utc()
        next_row["materialized"] = False
        rows[i] = next_row
        catalog[key] = rows
        save_catalog(catalog, root=root)
        return next_row
    raise JumpError("RESULT_NOT_FOUND", f"unknown {kind} {saved_id}")


def delete_saved(saved_id: str, *, kind: str = "query", root=None) -> dict[str, Any]:
    catalog = load_catalog(root=root)
    key = "queries" if kind == "query" else "views"
    rows = catalog.get(key) or []
    kept = [row for row in rows if not (isinstance(row, dict) and row.get("id") == saved_id)]
    if len(kept) == len(rows):
        raise JumpError("RESULT_NOT_FOUND", f"unknown {kind} {saved_id}")
    catalog[key] = kept
    save_catalog(catalog, root=root)
    return {"status": "ok", "id": saved_id, "kind": kind, "live_execution": LIVE_EXECUTION}
