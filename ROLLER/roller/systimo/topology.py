"""Quadrant topology. Missing or partial V1 tables are PRE_V1, not a crash."""

from __future__ import annotations

from roller.systimo.errors import SystimoError
from roller.systimo.store import CsvStore
from roller.systimo.store.schema import TOPOLOGY_TABLES

RESERVED_CAPACITY = 10
DRAWN_SLOTS = 80
MIN_CAPACITY = DRAWN_SLOTS + RESERVED_CAPACITY
SYSTEM_TYPES = (
    "database",
    "data_analysis",
    "fair_odds_modeling",
    "in_house_odds_modeling",
    "data_modeling",
    "game_modeling",
    "signal_generation",
    "momento_systems",
    "algorithmic_execution",
    "dynamic_risk_engine",
    "trade_breakdown",
    "position_stratification",
    "position_management",
    "hedging_analysis",
    "relative_value_hedging",
    "system_maintenance",
    "data_ingestion",
    "trade_reconciliation",
    "system_orchestration",
)


def topology_files_present(store: CsvStore | None = None) -> dict[str, bool]:
    store = store or CsvStore()
    return {name: store.path_for(name).is_file() for name in TOPOLOGY_TABLES}


def topology_status(store: CsvStore | None = None) -> str:
    present = topology_files_present(store)
    if not any(present.values()) or not all(present.values()):
        return "PRE_V1"
    return "V1"


def require_v1(store: CsvStore | None = None) -> CsvStore:
    store = store or CsvStore()
    if topology_status(store) != "V1":
        raise SystimoError("PRE_V1", "topology tables are missing or partial", 409)
    return store


def load(store: CsvStore | None = None) -> dict[str, list[dict[str, str]]]:
    store = require_v1(store)
    return {name: store.read(name) for name in TOPOLOGY_TABLES}


def instance_map(rows: dict[str, list[dict[str, str]]]) -> dict[str, dict[str, str]]:
    return {row["instance_id"]: row for row in rows["instances"]}


def services_for_scope(rows: dict[str, list[dict[str, str]]], scope: str) -> list[dict[str, str]]:
    """Enabled autostart services for a scope. Shared services are included. Quad-only services are not."""
    by_instance = instance_map(rows)
    wanted: set[str] = set()
    for binding in rows["service_bindings"]:
        inst = by_instance.get(binding["instance_id"])
        if inst is None:
            continue
        if scope == "all" or inst["quadrant_id"] in {scope, "global"}:
            wanted.add(binding["service_id"])
    selected = []
    for service in rows["services"]:
        if service["service_id"] not in wanted:
            continue
        if service["enabled"] != "true" or service["autostart"] != "true":
            continue
        if service["ownership_mode"] in {"external", "unmanaged"}:
            continue
        if scope != "all" and service["scope"] not in {scope, "shared", "global"}:
            continue
        selected.append(service)
    return selected
