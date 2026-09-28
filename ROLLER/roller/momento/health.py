"""Aggregate 19-system health. UNKNOWN is valid. No fake green."""

from __future__ import annotations

import time
from typing import Any

from roller.momento.adapters import probe_health
from roller.momento.registry import LIVE_EXECUTION, load_registry

PROBE_SQL = "SELECT sport, count(*) AS n FROM games GROUP BY 1"
QUERY_MARKETS = ("nba", "ncaab")
_CONNECTION_TTL_SEC = 5.0
_CONNECTION_CACHE: tuple[float, dict[str, Any]] | None = None


def _query_draft(leagues: list[str]) -> dict[str, Any]:
    return {
        "universe": {
            "sports": ["Basketball"],
            "leagues": leagues,
            "seasons": ["2025-2026"],
            "dateFrom": "2025-10-10",
            "dateTo": "2026-06-13",
            "markets": ["kalshi"],
            "marketData": ["candles"],
            "dataSources": [],
        },
        "entryConditions": [
            {
                "id": "e1",
                "family": "first_touch",
                "priceCents": 80,
                "touchN": 1,
                "periodWindows": [
                    {"period": "Q2"},
                    {"period": "Q3"},
                    {"period": "H1_2"},
                    {"period": "H2_1"},
                ],
            }
        ],
        "exitConditions": [
            {
                "id": "p-loss",
                "kind": "path",
                "family": "reach",
                "priceCents": 35,
                "outcome": "loss",
            },
            {
                "id": "h-win",
                "kind": "terminal",
                "family": "hold_expiration_win",
                "outcome": "win",
            },
        ],
        "teFilters": {"scoreSide": "leading", "absDiff": "6_10"},
        "recognizedIntent": {"status": "EMPTY"},
        "status": "DRAFT",
    }


def _probe_warehouse(warehouse_id: str) -> dict[str, Any]:
    from roller.jump.errors import JumpError
    from roller.jump.warehouse.api import handle_query
    from roller.jump.warehouse.registry import get_warehouse

    rec = get_warehouse(warehouse_id)
    if rec.status != "AVAILABLE":
        return {
            "warehouse_id": warehouse_id,
            "status": rec.status,
            "query": "UNAVAILABLE",
            "reason": rec.unavailable_reason,
            "returned": None,
            "n": None,
            "rows": [],
        }
    try:
        out = handle_query(warehouse_id, {"sql": PROBE_SQL, "limit": 10})
        rows = list(out.get("rows") or [])
        n = rows[0].get("n") if rows else None
        return {
            "warehouse_id": warehouse_id,
            "status": rec.status,
            "query": "OK",
            "reason": None,
            "returned": out.get("returned"),
            "n": n,
            "rows": rows,
        }
    except JumpError as exc:
        return {
            "warehouse_id": warehouse_id,
            "status": rec.status,
            "query": "UNAVAILABLE",
            "reason": exc.message,
            "returned": None,
            "n": None,
            "rows": [],
        }


def _compile_leagues(leagues: list[str]) -> dict[str, Any]:
    from roller.research_query.compiler import compile_draft

    try:
        compiled = compile_draft(_query_draft(leagues))
        return {
            "status": "OK",
            "execution_path": compiled.execution_path.value,
            "available": list(compiled.available),
            "unavailable": list(compiled.unavailable),
            "leagues": list(leagues),
        }
    except Exception as exc:  # noqa: BLE001 — connection probe must not crash
        return {
            "status": "UNAVAILABLE",
            "execution_path": None,
            "available": [],
            "unavailable": [type(exc).__name__],
            "leagues": list(leagues),
            "reason": type(exc).__name__,
        }


def connection_view() -> dict[str, Any]:
    """ROLLER + NBA/NCAAB query readiness. Missing stays UNAVAILABLE, never $0."""
    global _CONNECTION_CACHE
    now = time.monotonic()
    if _CONNECTION_CACHE is not None and now - _CONNECTION_CACHE[0] < _CONNECTION_TTL_SEC:
        return _CONNECTION_CACHE[1]
    markets = {wid: _probe_warehouse(wid) for wid in QUERY_MARKETS}
    research = {
        "nba": _compile_leagues(["NBA"]),
        "ncaab": _compile_leagues(["NCAAB"]),
        "combined": _compile_leagues(["NBA", "NCAAB"]),
    }
    connected = all(markets[wid]["query"] == "OK" for wid in QUERY_MARKETS) and all(
        research[key]["status"] == "OK" for key in ("nba", "ncaab")
    )
    body = {
        "schema": "momento.connection.v0",
        "live_execution": LIVE_EXECUTION,
        "roller": {"status": "CONNECTED", "port": 8791, "health": "/health"},
        "markets": markets,
        "research_query": research,
        "connected": connected,
        "detail": "NBA and NCAAB query ready" if connected else "UNAVAILABLE",
        "probe_sql": PROBE_SQL,
    }
    _CONNECTION_CACHE = (now, body)
    return body


def aggregate_health() -> dict[str, Any]:
    registry = load_registry()
    systems = [probe_health(row.id) for row in registry.systems]
    states = {row["state"] for row in systems}
    return {
        "live_execution": LIVE_EXECUTION,
        "nba_bot": "NOT_IMPLEMENTED",
        "count": len(systems),
        "states_present": sorted(states),
        "frontend_probe": "UNKNOWN",
        "systems": systems,
    }


def ingestion_view() -> dict[str, Any]:
    ingest = probe_health("data_ingestion")
    return {
        "system_id": "data_ingestion",
        "autojest": "NOT_IMPLEMENTED",
        "consumers": ["database"],
        "health": ingest,
        "live_execution": False,
        "submits": False,
    }


def reconciliation_view() -> dict[str, Any]:
    """Observe-only. Unread exchange state is UNAVAILABLE, never a fill."""
    return {
        "schema": "momento.reconciliation.observe.v0",
        "system_id": "trade_reconciliation",
        "status": "OBSERVATION_UNAVAILABLE",
        "availability": "UNAVAILABLE",
        "fills": "UNAVAILABLE",
        "positions": "UNAVAILABLE",
        "matched": None,
        "yes_quantity": None,
        "no_quantity": None,
        "pnl": "UNAVAILABLE",
        "submits": False,
        "execution_enabled": False,
        "live_execution": False,
        "oms": False,
        "note": "Exchange state unread. Observe-only. Not Vital. Not an OMS. Missing is UNAVAILABLE.",
    }
