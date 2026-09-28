"""Object Inspector — O_t at I(t) via authoritative observation path.

Optional fundamental / greeks are query-time measurements (not part of O_t).
Null and NOT_CONSTRUCTIBLE are preserved; never coerced to 0.
"""

from __future__ import annotations

from typing import Any

from roller import Roller
from roller.dashboard_adapter.serialize import to_jsonable
from roller.point_in_time.filters import AsOfRequiredError

INFORMATION_MODE_PIT = "POINT_IN_TIME"

_SECTION_KEYS = (
    "GAME_STATE",
    "TEAM_STATE",
    "PLAYER_STATE",
    "LINEUP_STATE",
    "MARKET_STATE",
    "INFORMATION_STATE",
    "TRAJECTORY",
    "POSSESSIONS",
    "BACKWARD_MEASUREMENTS",
)


class ObjectInspectorError(ValueError):
    """Explicit Object Inspector validation / binding failure."""


def _measurement_envelope(payload: Any, *, error: str | None = None) -> dict[str, Any]:
    if error is not None:
        return {"status": "AUTHORITATIVE_BINDING_FAILED", "error": error, "data": None}
    if payload is None:
        return {"status": "UNAVAILABLE", "data": None}
    if isinstance(payload, dict):
        status = payload.get("status")
        if status in (None, ""):
            # Greeks / fundamental often embed status; treat presence as AVAILABLE
            # unless an explicit constructibility status is set.
            status = "AVAILABLE"
        return {"status": status, "data": payload}
    return {"status": "AVAILABLE", "data": payload}


def _section_constructibility(observation: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key in _SECTION_KEYS:
        sec = observation.get(key)
        if not isinstance(sec, dict):
            out.append({"name": key, "status": "UNAVAILABLE", "note": "section missing"})
            continue
        status = sec.get("status") or "UNAVAILABLE"
        out.append(
            {
                "name": key,
                "status": status,
                "source_availability_status": sec.get("source_availability_status"),
            }
        )
    return out


def _greek_constructibility(greeks_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not greeks_payload or not isinstance(greeks_payload, dict):
        return []
    observed = greeks_payload.get("observed")
    items: list[dict[str, Any]] = []
    if isinstance(observed, dict):
        for name, body in observed.items():
            if isinstance(body, dict):
                items.append(
                    {
                        "name": name,
                        "status": body.get("status") or body.get("constructibility") or "AVAILABLE",
                        "value_present": body.get("value") is not None,
                    }
                )
            else:
                items.append({"name": name, "status": "AVAILABLE", "value_present": body is not None})
    # Also surface top-level status if present
    if "status" in greeks_payload and not items:
        items.append({"name": "greeks", "status": greeks_payload.get("status")})
    return items


def build_object_payload(
    internal_game_id: str,
    *,
    as_of: str | None = None,
    include_measurements: bool = True,
    db: Roller | None = None,
) -> dict[str, Any]:
    """Build Object Inspector payload for one game at as_of."""
    if as_of is None or str(as_of).strip() == "":
        raise ObjectInspectorError("as_of is required for POINT-IN-TIME object inspection")
    if not internal_game_id or str(internal_game_id).strip() == "":
        raise ObjectInspectorError("internal_game_id is required")

    roller = db or Roller()
    try:
        observation = roller.observation(internal_game_id, as_of=as_of)
    except AsOfRequiredError as exc:
        raise ObjectInspectorError(str(exc)) from exc
    except KeyError as exc:
        raise ObjectInspectorError(f"GAME NOT FOUND: {internal_game_id}") from exc
    except Exception as exc:  # noqa: BLE001
        raise ObjectInspectorError(f"AUTHORITATIVE BINDING FAILED: {type(exc).__name__}: {exc}") from exc

    fundamental_env: dict[str, Any] = {
        "status": "NOT_REQUESTED",
        "data": None,
        "note": "MEASUREMENT ≠ EDGE; F_t ≠ TRUE PROBABILITY",
    }
    greeks_env: dict[str, Any] = {
        "status": "NOT_REQUESTED",
        "data": None,
        "note": "MEASUREMENT ≠ EDGE; Δ/Γ/Θ ≠ EDGE",
    }
    greek_constructibility: list[dict[str, Any]] = []

    if include_measurements:
        oid = observation.get("observation_id")
        if oid:
            try:
                fundamental_env = _measurement_envelope(roller.fundamental(oid))
                fundamental_env["note"] = "MEASUREMENT ≠ EDGE; F_t ≠ TRUE PROBABILITY"
            except Exception as exc:  # noqa: BLE001
                fundamental_env = _measurement_envelope(None, error=f"{type(exc).__name__}: {exc}")
                fundamental_env["note"] = "MEASUREMENT ≠ EDGE; F_t ≠ TRUE PROBABILITY"
            try:
                greeks_payload = roller.greeks(oid)
                greeks_env = _measurement_envelope(greeks_payload)
                greeks_env["note"] = "MEASUREMENT ≠ EDGE; Δ/Γ/Θ/BASIS ≠ EDGE"
                if isinstance(greeks_payload, dict):
                    greek_constructibility = _greek_constructibility(greeks_payload)
            except Exception as exc:  # noqa: BLE001
                greeks_env = _measurement_envelope(None, error=f"{type(exc).__name__}: {exc}")
                greeks_env["note"] = "MEASUREMENT ≠ EDGE; Δ/Γ/Θ/BASIS ≠ EDGE"

    payload = {
        "internal_game_id": internal_game_id,
        "as_of": as_of,
        "information_mode": INFORMATION_MODE_PIT,
        "identity": {
            "observation_id": observation.get("observation_id"),
            "internal_game_id": observation.get("internal_game_id"),
            "sport": observation.get("sport"),
            "season": observation.get("season"),
            "state_schema_version": observation.get("state_schema_version"),
        },
        "time": {
            "as_of": as_of,
            "observation_time": observation.get("observation_time"),
        },
        "observation": {
            "status": "AVAILABLE",
            "data": {k: observation.get(k) for k in _SECTION_KEYS if k in observation},
        },
        "state": observation.get("GAME_STATE"),
        "market": observation.get("MARKET_STATE"),
        "measurements": {
            "backward": observation.get("BACKWARD_MEASUREMENTS"),
            "fundamental": fundamental_env,
            "greeks": greeks_env,
        },
        "constructibility": {
            "observation_sections": _section_constructibility(observation),
            "greeks": greek_constructibility,
            "rules": [
                "NULL ≠ 0",
                "NOT_CONSTRUCTIBLE ≠ 0",
                "MEASUREMENT ≠ EDGE",
                "F_t ≠ TRUE PROBABILITY",
            ],
        },
        "caveats": [
            "POINT-IN-TIME MODE",
            "MEASUREMENT ≠ EDGE",
            "CANDLE PATH ≠ FILL",
            "O_t does not include future labels or FIRST80",
        ],
    }
    return to_jsonable(payload)
