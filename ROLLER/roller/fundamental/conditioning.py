"""core_v1 conditioning. Separate from V3 conditioning.json."""

from __future__ import annotations

import json
from typing import Any

from roller.config import RollerConfig
from roller.io_csv import sha256_bytes
from roller.measurement.conditioning import _dig, _edge_bucket, _width_bucket
from roller.state.clock import elapsed_game_seconds


DEFAULT_SCHEMA = "core_v1"


def schema_spec(cfg: RollerConfig, schema_version: str | None = None) -> dict[str, Any]:
    block = cfg.fundamental_conditioning or {}
    name = schema_version or block.get("default_schema") or DEFAULT_SCHEMA
    schemas = block.get("schemas") or {}
    if name not in schemas:
        raise KeyError(f"unknown fundamental conditioning schema: {name!r}")
    return schemas[name]


def support_floors(cfg: RollerConfig) -> dict[str, int]:
    block = (cfg.fundamental_conditioning or {}).get("support") or {}
    return {
        "minimum_observations": int(block.get("minimum_observations") or 3),
        "minimum_unique_games": int(block.get("minimum_unique_games") or 2),
        "minimum_unique_dates": int(block.get("minimum_unique_dates") or 1),
        "minimum_unique_seasons": int(block.get("minimum_unique_seasons") or 1),
    }


def _field(state: dict[str, Any], source: str) -> Any:
    if source in state:
        return state.get(source)
    return _dig(state, source)


def condition_state(
    cfg: RollerConfig,
    state: dict[str, Any],
    *,
    schema_version: str | None = None,
) -> dict[str, Any]:
    spec = schema_spec(cfg, schema_version)
    version = str(spec.get("conditioning_schema_version") or schema_version or DEFAULT_SCHEMA)
    dims: dict[str, Any] = {}
    missing: list[str] = []
    for dim in spec.get("dimensions") or []:
        name = dim["name"]
        raw = _field(state, dim["source"])
        kind = dim.get("type")
        if kind == "identity":
            dims[name] = None if raw in (None, "") else str(raw)
        elif kind == "width":
            dims[name] = _width_bucket(raw, int(dim.get("width") or 60))
        elif kind == "edges":
            dims[name] = _edge_bucket(raw, list(dim.get("edges") or []))
        else:
            dims[name] = None if raw in (None, "") else str(raw)
        if dims[name] is None:
            missing.append(name)
    payload = json.dumps(
        {"conditioning_schema_version": version, "dimensions": dims},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    digest = sha256_bytes(payload.encode("utf-8"))[:16]
    status = "INVALID_CONDITION" if missing else "valid"
    return {
        "condition_id": f"C_{digest}",
        "conditioning_schema_version": version,
        "dimensions": dims,
        "raw_dimensions": dims,
        "status": status,
        "missing_dimensions": missing,
    }


def observation_state_fields(observation: dict[str, Any]) -> dict[str, Any]:
    gs = observation.get("GAME_STATE") or {}
    data = gs["data"] if isinstance(gs, dict) and "data" in gs else gs
    if not isinstance(data, dict):
        data = {}
    score = data.get("score") or {}

    def unwrap(field: Any) -> Any:
        if isinstance(field, dict) and "value" in field:
            return field.get("value")
        return field

    period = data.get("period")
    clock = data.get("clock")
    elapsed = data.get("elapsed_game_seconds")
    sport = observation.get("sport") or "NBA"
    if elapsed in (None, "") and period not in (None, "") and clock not in (None, ""):
        elapsed = elapsed_game_seconds(period, clock, sport=sport)
    return {
        "period": period,
        "clock": clock,
        "elapsed_game_seconds": elapsed,
        "score_differential_home": unwrap(score.get("score_differential_home")),
        "home_score": unwrap(score.get("home")),
        "away_score": unwrap(score.get("away")),
    }


def condition_observation(
    cfg: RollerConfig,
    observation: dict[str, Any],
    *,
    schema_version: str | None = None,
) -> dict[str, Any]:
    return condition_state(cfg, observation_state_fields(observation), schema_version=schema_version)
