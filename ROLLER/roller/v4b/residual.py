"""R = M − E[M|core_v1]. Insufficient support is null, not 0."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from roller.v4b.baseline import parse_measurement_value
from roller.v4b.types import ExactRational, MeasurementPoint


def compute_residual(
    observed: MeasurementPoint,
    baseline: dict[str, Any],
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "measurement_name": observed.name,
        "contains_future_information": True,
        "measurement_available_at": observed.measurement_available_at,
        "value": None,
        "standardized": None,
        "status": "INSUFFICIENT_SUPPORT",
        "note": "undefined residual; insufficient support is not 0",
    }
    support = (baseline or {}).get("support") or {}
    if (baseline or {}).get("status") != "valid" or not support.get("sufficient"):
        return out
    m = None if observed.value is None else observed.value.fraction()
    expected = parse_measurement_value((baseline or {}).get("expected"))
    if m is None or expected is None:
        out["status"] = "INSUFFICIENT_SUPPORT"
        out["note"] = "undefined residual; missing M or expected is not 0"
        return out
    units = observed.value.units if observed.value is not None else "e4"
    residual = m - expected
    out["value"] = ExactRational.from_fraction(residual, units).public()
    out["status"] = "valid"
    out["note"] = None
    out["support"] = support
    disp = (baseline or {}).get("dispersion") or {}
    mad = parse_measurement_value(disp)
    if mad is None and disp.get("numerator") is not None:
        mad = parse_measurement_value(disp)
    if mad is not None and mad > 0:
        out["standardized"] = ExactRational.from_fraction(residual / mad, "mad_units").public()
    else:
        out["standardized"] = None
        if mad == 0:
            out["standardized_status"] = "MAD_ZERO"
    return out


def standardized_residual(residual: Fraction, mad: Fraction) -> ExactRational | None:
    if mad <= 0:
        return None
    return ExactRational.from_fraction(residual / mad, "mad_units")
