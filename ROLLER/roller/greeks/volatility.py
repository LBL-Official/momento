"""Market volatility proxies. Not Vega. Not basketball-state volatility."""

from __future__ import annotations

from typing import Any


def backward_volatility(backward_section: dict[str, Any]) -> dict[str, Any]:
    data = (backward_section or {}).get("data") or {}
    meas = data.get("measurements") or {}
    return {
        "close_to_close_realized_volatility": meas.get("close_to_close_realized_volatility"),
        "high_low_range_1m": meas.get("high_low_range_1m"),
        "directional_efficiency": meas.get("directional_efficiency"),
        "note": "market candle volatility ≠ basketball-state volatility ≠ Vega",
    }
