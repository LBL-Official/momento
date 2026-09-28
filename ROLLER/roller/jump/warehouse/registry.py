"""Discover Phase 8 parquet desks. Jump does not copy them."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from roller.config import RollerConfig
from roller.jump.errors import JumpError
from roller.jump.library import repo_root
from roller.jump.versions import LIVE_EXECUTION
from roller.warehouse.desk import DEFAULT_SEASON, DESK_SPORTS
from roller.warehouse.layout import warehouse_root

WAREHOUSE_SPORTS = (
    ("nba", "NBA", "NBA"),
    ("ncaab", "NCAAB", "NCAAB"),
    ("mlb", "MLB", "MLB"),
    ("wnba", "WNBA", "WNBA"),
    ("atp", "ATP", "TENNIS"),
    ("wta", "WTA", "TENNIS"),
)


@dataclass(frozen=True)
class WarehouseRecord:
    id: str
    canonical_key: str
    display_name: str
    sport: str
    jump_sport: str
    owner: str
    source_system: str
    source_uri: str
    storage_type: str
    query_adapter: str
    status: str
    read_only: bool
    season: str
    description: str
    unavailable_reason: str | None = None
    manifest: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "canonical_key": self.canonical_key,
            "display_name": self.display_name,
            "sport": self.sport,
            "jump_sport": self.jump_sport,
            "owner": self.owner,
            "source_system": self.source_system,
            "source_uri": self.source_uri,
            "storage_type": self.storage_type,
            "query_adapter": self.query_adapter,
            "status": self.status,
            "read_only": self.read_only,
            "season": self.season,
            "description": self.description,
            "unavailable_reason": self.unavailable_reason,
            "live_execution": LIVE_EXECUTION,
            "writable_rows": False,
            "manifest": {
                "games": (self.manifest or {}).get("games"),
                "markets": (self.manifest or {}).get("markets"),
                "observation_rows": (self.manifest or {}).get("observation_rows"),
                "pbp_rows": (self.manifest or {}).get("pbp_rows"),
                "settlements": (self.manifest or {}).get("settlements"),
                "orderbook_data_available": (self.manifest or {}).get("orderbook_data_available"),
                "updated_at": (self.manifest or {}).get("updated_at"),
            }
            if self.manifest
            else None,
        }


def _cfg(root: Path | None = None) -> RollerConfig:
    repo = root or repo_root()
    return RollerConfig(root=repo / "ROLLER")


def _load_manifest(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return body if isinstance(body, dict) else None


def _desk_path(cfg: RollerConfig, sport: str, season: str) -> Path:
    if sport in DESK_SPORTS:
        try:
            return warehouse_root(cfg, sport, season)
        except KeyError:
            pass
    key = str(season or DEFAULT_SEASON).replace("-", "_")
    return cfg.root / "data" / sport.lower() / key / "derived" / "warehouse"


def _record(wid: str, sport: str, jump_sport: str, *, root: Path | None, season: str) -> WarehouseRecord:
    cfg = _cfg(root)
    desk = _desk_path(cfg, sport, season)
    rel = None
    try:
        rel = str(desk.resolve().relative_to((root or repo_root()).resolve()))
    except ValueError:
        rel = str(desk)
    manifest = _load_manifest(desk / "manifest.json")
    present = (desk / "games" / "games.parquet").is_file() and manifest is not None
    if sport not in DESK_SPORTS:
        return WarehouseRecord(
            id=wid,
            canonical_key=f"{sport}_WAREHOUSE",
            display_name=f"{sport} Warehouse",
            sport=sport,
            jump_sport=jump_sport,
            owner="database",
            source_system="ROLLER",
            source_uri=rel,
            storage_type="PARQUET_DIRECTORY",
            query_adapter="duckdb_parquet",
            status="WAREHOUSE_UNAVAILABLE",
            read_only=True,
            season=season,
            description="No Phase 8 parquet desk. Jump does not invent tables.",
            unavailable_reason=f"Phase 8 warehouse missing at {rel}",
        )
    if not present:
        return WarehouseRecord(
            id=wid,
            canonical_key=f"{sport}_WAREHOUSE",
            display_name=f"{sport} Warehouse",
            sport=sport,
            jump_sport=jump_sport,
            owner="database",
            source_system="ROLLER",
            source_uri=rel,
            storage_type="PARQUET_DIRECTORY",
            query_adapter="duckdb_parquet",
            status="WAREHOUSE_UNAVAILABLE",
            read_only=True,
            season=season,
            description="Phase 8 parquet desk not on disk.",
            unavailable_reason=f"missing manifest or games.parquet at {rel}",
        )
    return WarehouseRecord(
        id=wid,
        canonical_key=f"{sport}_WAREHOUSE",
        display_name=f"{sport} Warehouse",
        sport=sport,
        jump_sport=jump_sport,
        owner="database",
        source_system="ROLLER",
        source_uri=rel,
        storage_type="PARQUET_DIRECTORY",
        query_adapter="duckdb_parquet",
        status="AVAILABLE",
        read_only=True,
        season=season,
        description="Phase 8 parquet desk. Pointer, not a copy. Confirm & Run still reads CSV.",
        manifest=manifest,
    )


def list_warehouses(*, root: Path | None = None, season: str = DEFAULT_SEASON) -> list[WarehouseRecord]:
    return [_record(wid, sport, jump_sport, root=root, season=season) for wid, sport, jump_sport in WAREHOUSE_SPORTS]


def get_warehouse(warehouse_id: str, *, root: Path | None = None, season: str = DEFAULT_SEASON) -> WarehouseRecord:
    wanted = str(warehouse_id or "").strip().lower()
    for row in list_warehouses(root=root, season=season):
        if row.id == wanted:
            return row
    raise JumpError("RESULT_NOT_FOUND", f"unknown warehouse {warehouse_id}")


def require_available(warehouse_id: str, *, root: Path | None = None) -> WarehouseRecord:
    row = get_warehouse(warehouse_id, root=root)
    if row.status != "AVAILABLE":
        raise JumpError("WAREHOUSE_UNAVAILABLE", row.unavailable_reason or f"{row.id} unavailable")
    return row
