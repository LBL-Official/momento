"""Residual R_t = Y - E[Y|C]. Insufficient support is undefined, not zero."""

from __future__ import annotations

from typing import Any

from roller.measurement.integers import parse_e4


def compute_residual(response: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    y = parse_e4((response or {}).get("value"))
    expected = (baseline or {}).get("expected") or {}
    support = (baseline or {}).get("support") or {}
    out = {
        "observation_id": (response or {}).get("observation_id") or (baseline or {}).get("observation_id"),
        "measurement_name": "response_residual",
        "response_measurement": (response or {}).get("measurement_name"),
        "horizon": (response or {}).get("horizon") or (baseline or {}).get("horizon"),
        "contains_future_information": True,
        "information_boundary": "forward",
        "value": None,
        "residual_status": "INSUFFICIENT_SUPPORT",
    }
    if (baseline or {}).get("status") != "valid" or not support.get("sufficient"):
        out["note"] = "undefined residual; insufficient support is not 0"
        return out
    if y is None or expected.get("mean_status") != "observed":
        out["residual_status"] = "INSUFFICIENT_SUPPORT"
        out["note"] = "undefined residual; missing Y or expected value is not 0"
        return out
    n = int(expected.get("n") or 0)
    total = int(expected.get("sum") or 0)
    if n <= 0:
        out["note"] = "undefined residual; insufficient support is not 0"
        return out
    # exact: residual = y - sum/n  →  (y*n - sum) / n
    out.update(
        {
            "value": None,
            "numerator": y * n - total,
            "denominator": n,
            "residual_status": "valid",
            "support": support,
        }
    )
    return out
