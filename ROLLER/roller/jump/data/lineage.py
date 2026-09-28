"""JumpLineage. Terminate at the deepest exposed source. Never invent row ids."""

from __future__ import annotations

import uuid
from typing import Any

from roller.jump.data.models import LINEAGE_SCHEMA, LIVE_EXECUTION, now_iso


def _parent(
    system_id: str,
    resource_id: str,
    *,
    schema: str = "v1",
    dataset_id: str = "",
    universe_id: str = "",
    n: Any = None,
) -> dict[str, Any]:
    return {
        "system_id": system_id,
        "resource_id": resource_id,
        "schema": schema,
        "dataset_id": dataset_id,
        "universe_id": universe_id,
        "n": n,
    }


def for_result(capability: str, result: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    parents: list[dict[str, Any]] = []
    source_files: list[str] = []
    source_tables: list[str] = []
    source_rows: list[dict[str, Any]] = []
    identity_keys: list[dict[str, str]] = []
    transformations: list[str] = ["jump.read_only_composition"]

    trade_id = str(result.get("trade_id") or params.get("trade_id") or "")
    ticker = str(result.get("ticker") or params.get("ticker") or "")
    as_of = params.get("as_of") or result.get("as_of")
    if trade_id:
        identity_keys.append({"kind": "trade_id", "value": trade_id})
    if ticker:
        identity_keys.append({"kind": "ticker", "value": ticker})
    event_id = str(result.get("event_id") or "")
    if event_id:
        identity_keys.append({"kind": "event_id", "value": event_id})

    if capability.startswith("AUSTIN") or result.get("source_system") == "austin":
        parents.append(
            _parent(
                "austin",
                "austin.query_at",
                dataset_id="austin_nba_2q3q_604",
                universe_id=str(result.get("universe") or "choosin_nba_2q3q_604"),
                n=result.get("n"),
            )
        )
        source_files.append("ROLLER/roller/austin/")
        transformations.append("persist=False historical query_at")
        if ticker:
            parents.append(_parent("roller", "warehouse.game_market_links", dataset_id="roller.nba"))
            source_tables.append("nba.game_market_links")
            # Row identity only if the warehouse actually returned a match later.
            source_rows.append(
                {
                    "system_id": "austin",
                    "kind": "trade",
                    "trade_id": trade_id,
                    "ticker": ticker,
                    "note": "Austin trade identity. ROLLER row id not invented.",
                }
            )

    if capability.startswith("CHOOSIN") or result.get("source_system") == "choosin_texas":
        parents.append(
            _parent(
                "choosin_texas",
                "choosin.get_trade_context",
                dataset_id="choosin_derived_four_936",
                universe_id=str(result.get("universe") or "derived_four_936"),
                n=result.get("n"),
            )
        )
        transformations.append("STATIC population prior")

    if result.get("source_system") in {"ballhog", "tk_ultra"}:
        parents.append(_parent("austin", "austin.query_at", dataset_id="austin_nba_2q3q_604", universe_id="choosin_nba_2q3q_604"))
        parents.append(
            _parent(
                "choosin_texas",
                "choosin.get_trade_context",
                dataset_id="choosin_derived_four_936",
                universe_id="derived_four_936",
            )
        )
        parents.append(_parent(str(result.get("source_system")), capability))

    if result.get("source_system") == "roller":
        table = str(result.get("table") or "")
        if table:
            source_tables.append(f"nba.{table}")
        parents.append(_parent("roller", f"warehouse.{table or 'pointer'}", dataset_id="roller.nba"))
        handle = result.get("handle") if isinstance(result.get("handle"), dict) else {}
        if handle.get("location"):
            source_files.append(str(handle.get("location")))

    return {
        "schema": LINEAGE_SCHEMA,
        "lineage_id": uuid.uuid4().hex[:16],
        "result_system": "jump",
        "result_resource": capability,
        "result_timestamp": now_iso(),
        "as_of": as_of,
        "parents": parents,
        "source_files": source_files,
        "source_tables": source_tables,
        "source_rows": source_rows,
        "identity_keys": identity_keys,
        "transformations": transformations,
        "query_id": None,
        "copy": False,
        "live_execution": LIVE_EXECUTION,
        "note": "Lineage stops at the deepest registered source. Missing warehouse row ids are omitted.",
    }


def show_source(capability: str, result: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    lineage = for_result(capability, result, params)
    return {
        "product": result.get("source_system") or "jump",
        "model": capability,
        "universe": result.get("universe"),
        "n": result.get("n"),
        "dataset": (lineage["parents"][0]["dataset_id"] if lineage["parents"] else None),
        "file_table": (lineage["source_tables"] or lineage["source_files"] or [None])[0],
        "row_identity": lineage["identity_keys"],
        "timestamp": result.get("source_timestamp") or result.get("as_of"),
        "source_basis": result.get("data_mode"),
        "upstream_dependencies": lineage["parents"],
        "lineage": lineage,
        "live_execution": LIVE_EXECUTION,
    }
