"""STAX request and schema validation."""

from __future__ import annotations

from typing import Any

from roller.stax.models import StaxError
from roller.stax.versions import STAX_SCHEMA


CLIENT_OVERRIDE_FIELDS = frozenset(
    {
        "execution_path",
        "dataset",
        "dataset_version",
        "dataset_fingerprint",
        "n",
        "N",
        "population_n",
        "version_id",
        "version",
        "reference_match",
        "compiled_universe",
    }
)


def strip_client_overrides(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Client cannot dictate execution path, dataset, N, or version id."""
    payload = dict(payload or {})
    for key in CLIENT_OVERRIDE_FIELDS:
        payload.pop(key, None)
    return payload


FORBIDDEN_TIMEFRAME_FIELDS = (
    "timeframe_mode",
    "rolling",
    "to_current_data",
    "last_n_days",
    "lookback_days",
)


def reject_rolling_fields(payload: dict[str, Any] | None) -> None:
    payload = payload or {}
    found = [k for k in FORBIDDEN_TIMEFRAME_FIELDS if payload.get(k) not in (None, False, "", "FIXED")]
    if "timeframe_mode" in payload and str(payload.get("timeframe_mode") or "").upper() not in {"", "FIXED"}:
        found.append("timeframe_mode")
    if found:
        raise StaxError(
            "STAX_ROLLING_UNSUPPORTED",
            "V1 timeframes are fixed. Rolling windows are not defined.",
            {"fields": sorted(set(found))},
        )


def require_name(name: Any) -> str:
    text = str(name or "").strip()
    if not text:
        raise StaxError("STAX_NAME_REQUIRED", "STAX NAME is required")
    return text


def require_schema(payload: dict[str, Any] | None) -> None:
    payload = payload or {}
    schema = payload.get("stax_schema_version") or payload.get("schema_version")
    if schema and schema != STAX_SCHEMA:
        raise StaxError(
            "STAX_SCHEMA_INVALID",
            f"unsupported schema {schema}",
            {"expected": STAX_SCHEMA},
        )
