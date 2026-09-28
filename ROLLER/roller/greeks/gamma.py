"""Empirical gamma: finite-difference acceleration. No default smoothing."""

from __future__ import annotations

from typing import Any


def acceleration_from_backward(backward_section: dict[str, Any]) -> dict[str, Any]:
    data = (backward_section or {}).get("data") or {}
    meas = (data.get("measurements") or {}).get("market_acceleration_1m") or {}
    return {
        "measurement_name": "market_acceleration_1m",
        "finite_difference": "(K_t-K_{t-1})-(K_{t-1}-K_{t-2})",
        "input_axis": "yes_bid_close",
        "sampling_interval": "1m",
        "smoothing_policy": "none",
        **meas,
    }
