"""V4B leakage: three clocks stay distinct; current game excluded; O_t stays clean."""

from __future__ import annotations

from typing import Any

from roller.v4b.baseline import measurement_eligible
from roller.v4b.candles import visible_home_candles


FORBIDDEN_OBS_KEYS = {"greeks", "GREEKS", "v4b", "v4c", "market_fundamental_basis"}


def audit_observation_excludes_greeks(obs: dict[str, Any]) -> list[str]:
    errors = []
    for key in obs:
        low = str(key).lower()
        if key in FORBIDDEN_OBS_KEYS or low in FORBIDDEN_OBS_KEYS:
            errors.append(f"observation contains forbidden key {key}")
        if low.startswith("v4b") or low.startswith("v4c") or low == "greeks":
            errors.append(f"observation key {key} looks like a Greek architecture object")
    return errors


def audit_measurement_not_before_inputs(measurement_available_at, *input_times) -> list[str]:
    from roller.timeutil import parse_utc

    maa = parse_utc(measurement_available_at)
    if maa is None:
        return []
    errors = []
    for raw in input_times:
        ts = parse_utc(raw)
        if ts is not None and maa < ts:
            errors.append(f"measurement_available_at {maa} precedes input {ts}")
    return errors


def audit_v4b_eligibility_example() -> list[str]:
    """Historical measurement at 10:05. Equality hidden. Current game excluded."""
    historical = {
        "internal_game_id": "GAME_A",
        "measurement_available_at": "2025-12-20T10:05:00Z",
        "condition_id": "C_CORE",
        "measurement_name": "market_delta_1m",
        "status": "valid",
        "value": {"numerator": 10, "denominator": 1, "units": "e4"},
    }
    errors = []
    if measurement_eligible(
        historical, target_cutoff="2025-12-20T10:02:00Z", target_game="GAME_B", condition_id="C_CORE"
    ):
        errors.append("measurement at 10:05 eligible for cutoff 10:02")
    if measurement_eligible(
        historical, target_cutoff="2025-12-20T10:05:00Z", target_game="GAME_B", condition_id="C_CORE"
    ):
        errors.append("equality on measurement_available_at must be hidden")
    if not measurement_eligible(
        historical, target_cutoff="2025-12-20T10:06:00Z", target_game="GAME_B", condition_id="C_CORE"
    ):
        errors.append("10:05 measurement should be eligible at 10:06")
    if measurement_eligible(
        historical, target_cutoff="2025-12-20T10:06:00Z", target_game="GAME_A", condition_id="C_CORE"
    ):
        errors.append("current game identity must be excluded")
    if measurement_eligible(
        historical, target_cutoff="2025-12-20T10:06:00Z", target_game="GAME_B", condition_id="C_OTHER"
    ):
        errors.append("core_v1 cell mismatch must be excluded")
    return errors


def audit_visible_candles_half_open(candles, cutoff) -> list[str]:
    import pandas as pd

    from roller.timeutil import parse_utc

    errors = []
    vis = visible_home_candles(candles if candles is not None else pd.DataFrame(), cutoff)
    cut = parse_utc(cutoff)
    for c in vis:
        if cut is not None and not (c.available_at_dt < cut):
            errors.append(f"visible candle at or after cutoff: {c.available_at}")
    return errors


def run_v4b_validate() -> dict[str, Any]:
    """Called after run_integrity. Do not fold into the V1 integrity walker."""
    errors = []
    errors.extend(audit_v4b_eligibility_example())
    return {"status": "FAIL" if errors else "PASS", "errors": errors}
