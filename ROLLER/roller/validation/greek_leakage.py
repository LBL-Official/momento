"""V3 leakage: O_t stays clean; baseline uses both clocks."""

from __future__ import annotations

from typing import Any

from roller.measurement.eligibility import baseline_eligible


FORBIDDEN_OBS_KEYS = {
    "labels",
    "response",
    "baseline",
    "residual",
    "Y",
    "fundamental",
    "F_t",
    "FUNDAMENTAL",
    "greeks",
    "GREEKS",
    "v4b",
    "v4c",
    "V4C",
}


def audit_observation_clean(obs: dict[str, Any]) -> list[str]:
    errors = []
    for key in obs:
        low = str(key).lower()
        if key in FORBIDDEN_OBS_KEYS or low in FORBIDDEN_OBS_KEYS:
            errors.append(f"observation contains forbidden key {key}")
        if "label" in low:
            errors.append(f"observation key {key} looks like a label")
        if low.endswith("_response") and key != "BACKWARD_MEASUREMENTS":
            errors.append(f"observation key {key} looks like a forward response")
    if "contains_future_information" in obs:
        errors.append("observation carries contains_future_information")
    back = (obs.get("BACKWARD_MEASUREMENTS") or {}).get("data") or {}
    for name, meas in (back.get("measurements") or {}).items():
        if meas.get("contains_future_information"):
            errors.append(f"backward measurement {name} marked future")
        if meas.get("information_boundary") == "forward":
            errors.append(f"backward measurement {name} has forward boundary")
    return errors


def audit_response_future(row: dict[str, Any]) -> list[str]:
    errors = []
    if row.get("contains_future_information") is not True:
        errors.append("response missing contains_future_information=true")
    if not row.get("response_available_at"):
        errors.append("response missing response_available_at")
    for field in ("observation_time", "response_start_time", "response_end_time", "horizon"):
        if not row.get(field):
            errors.append(f"response missing {field}")
    return errors


def audit_baseline_eligibility_example() -> list[str]:
    """Synthetic two-clock contract used by unit tests; also documents the invariant."""
    a = {
        "observation_time": "2025-12-20T10:00:00Z",
        "response_available_at": "2025-12-20T10:05:00Z",
    }
    errors = []
    if baseline_eligible(a, observation_time_t="2025-12-20T10:02:00Z"):
        errors.append("10:00/10:05 response eligible at 10:02")
    if baseline_eligible(a, observation_time_t="2025-12-20T10:05:00Z"):
        errors.append("equality at 10:05 must be hidden")
    if not baseline_eligible(a, observation_time_t="2025-12-20T10:06:00Z"):
        errors.append("10:00/10:05 response should be eligible at 10:06")
    return errors
