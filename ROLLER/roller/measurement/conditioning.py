"""Deterministic conditioning. No unsupervised clustering."""

from __future__ import annotations

import json
from typing import Any

from roller.config import RollerConfig
from roller.io_csv import sha256_bytes
from roller.measurement.integers import parse_e4
from roller.state.capabilities import capability


def _dig(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict) and part not in cur and "data" in cur and isinstance(cur["data"], dict):
            cur = cur["data"]
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    if isinstance(cur, dict) and "value" in cur:
        return cur.get("value")
    return cur


def _width_bucket(value: Any, width: int) -> str | None:
    parsed = parse_e4(value)
    if parsed is None:
        return None
    return str((parsed // width) * width)


def _edge_bucket(value: Any, edges: list[int]) -> str | None:
    parsed = parse_e4(value)
    if parsed is None:
        return None
    ordered = sorted(int(e) for e in edges)
    for i, edge in enumerate(ordered):
        if parsed < edge:
            lo = "-inf" if i == 0 else str(ordered[i - 1])
            return f"[{lo},{edge})"
    return f"[{ordered[-1]},+inf)"


def _sign_bucket(value: Any) -> str | None:
    parsed = parse_e4(value)
    if parsed is None:
        return None
    if parsed > 0:
        return "leading"
    if parsed < 0:
        return "trailing"
    return "tied"


def condition_observation(cfg: RollerConfig, observation: dict[str, Any]) -> dict[str, Any]:
    spec = cfg.conditioning or {}
    version = str(spec.get("conditioning_schema_version") or "conditioning_schema_v1")
    dims: dict[str, Any] = {}
    sport = observation.get("sport")
    for dim in spec.get("dimensions") or []:
        name = dim["name"]
        required = dim.get("requires_sport_capability")
        if required and capability(str(sport or ""), required) != "REAL":
            dims[name] = "NOT_SUPPORTED"
            continue
        source = dim["source"]
        if source == "sport":
            raw = sport
        elif source == "POSSESSIONS.latest_end_status":
            poss = ((observation.get("POSSESSIONS") or {}).get("data") or {}).get("possessions") or []
            raw = poss[-1].get("end_status") if poss else None
        else:
            raw = _dig(observation, source)
        kind = dim.get("type")
        if kind == "identity":
            dims[name] = None if raw in (None, "") else str(raw)
        elif kind == "width":
            dims[name] = _width_bucket(raw, int(dim.get("width") or 60))
        elif kind == "edges":
            dims[name] = _edge_bucket(raw, list(dim.get("edges") or []))
        elif kind == "sign":
            dims[name] = _sign_bucket(raw)
        else:
            dims[name] = None if raw in (None, "") else str(raw)
    payload = json.dumps(
        {"conditioning_schema_version": version, "dimensions": dims},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    digest = sha256_bytes(payload.encode("utf-8"))[:16]
    return {
        "condition_id": f"C_{digest}",
        "conditioning_schema_version": version,
        "dimensions": dims,
    }
