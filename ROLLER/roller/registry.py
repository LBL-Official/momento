"""Dataset registry: discovery, dependencies, required-path validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from roller.config import RollerConfig, load_json
from roller.io_csv import write_json

REQUIRED_STATUSES = {"required", "operational"}


def registry_path(cfg: RollerConfig) -> Path:
    return cfg.root / "meta" / "dataset_registry.json"


def load_registry(cfg: RollerConfig) -> dict[str, Any]:
    path = registry_path(cfg)
    if not path.is_file():
        return {"datasets": []}
    return load_json(path)


def save_registry(cfg: RollerConfig, registry: dict[str, Any]) -> None:
    write_json(registry_path(cfg), registry)


def dataset_id(sport: str, season: str, name: str) -> str:
    return f"{sport.lower()}_{season.replace('-', '_')}_{name}"


def default_registry(cfg: RollerConfig) -> dict[str, Any]:
    datasets = []
    for sport, seasons in cfg.db_map["sports"].items():
        for season, body in seasons["seasons"].items():
            meta = cfg.season_meta(sport, season)
            for name, rel in body["datasets"].items():
                schema = cfg.schemas["datasets"].get(name) or cfg.schemas["datasets"].get(
                    "team_features" if name == "team_features" else name, {}
                )
                if name == "team_features":
                    schema = cfg.schemas["datasets"]["team_features"]
                elif name in cfg.schemas["datasets"]:
                    schema = cfg.schemas["datasets"][name]
                else:
                    schema = {}
                datasets.append(
                    {
                        "dataset_name": dataset_id(sport, season, name),
                        "sport": sport,
                        "season": season,
                        "path": rel,
                        "format": "csv",
                        "primary_key": schema.get("primary_key", []),
                        "event_time_column": schema.get("event_time_column", "event_timestamp"),
                        "availability_time_column": schema.get(
                            "availability_time_column", "available_at"
                        ),
                        "dependencies": _deps(name, sport, season),
                        "update_frequency": "daily",
                        "update_script": _script(name),
                        "schema_version": "1.0.0",
                        "contains_future_information": bool(
                            schema.get("contains_future_information")
                            or name == "game_state_features"
                        ),
                        "status": "pending",
                        "warehouse_season": meta.get("warehouse_season"),
                    }
                )
    datasets.append(
        {
            "dataset_name": "game_identity",
            "sport": "*",
            "season": "*",
            "path": "meta/game_identity.csv",
            "format": "csv",
            "primary_key": ["internal_game_id"],
            "event_time_column": "game_date",
            "availability_time_column": "created_at",
            "dependencies": [],
            "update_frequency": "daily",
            "update_script": "build_game_identity.py",
            "schema_version": "1.0.0",
            "status": "required",
        }
    )
    return {"datasets": datasets}


def _deps(name: str, sport: str, season: str) -> list[str]:
    games = dataset_id(sport, season, "games")
    if name == "games":
        return ["game_identity"]
    if name == "pbp":
        return [games]
    if name == "kalshi_candles":
        return [games, "game_identity"]
    if name in {"polymarket_candles", "polymarket_markets"}:
        return [games, "game_identity"]
    if name in {"kalshi_markets", "kalshi_trades", "kalshi_orderbook_snapshots"}:
        return [games, "game_identity"]
    if name == "first80_triggers":
        return [games, dataset_id(sport, season, "kalshi_candles")]
    if name in {"team_features", "d2d_daily", "game_state_features"}:
        return [games]
    return []


def _script(name: str) -> str:
    return {
        "games": "canonicalize.py",
        "pbp": "ingest_pbp.py",
        "kalshi_candles": "ingest_kalshi.py",
        "polymarket_candles": "ingest_polymarket.py",
        "polymarket_markets": "ingest_polymarket.py",
        "team_features": "build_team_features.py",
        "d2d_daily": "build_d2d.py",
        "game_state_features": "canonicalize.py",
    }.get(name, "update_roller.py")


def missing_required_paths(cfg: RollerConfig, registry: dict[str, Any] | None = None) -> list[str]:
    reg = registry or load_registry(cfg)
    missing = []
    for ds in reg.get("datasets", []):
        if str(ds.get("status", "")).lower() not in REQUIRED_STATUSES:
            continue
        rel = ds["path"]
        path = cfg.root / rel
        if path.is_file() or path.is_dir() and any(path.glob("*.csv")):
            continue
        missing.append(rel)
    return missing


def upsert_dataset_meta(cfg: RollerConfig, dataset_name: str, **fields: Any) -> None:
    reg = load_registry(cfg)
    found = False
    for ds in reg["datasets"]:
        if ds["dataset_name"] == dataset_name:
            ds.update(fields)
            found = True
            break
    if not found:
        rec = {"dataset_name": dataset_name}
        rec.update(fields)
        reg["datasets"].append(rec)
    save_registry(cfg, reg)
