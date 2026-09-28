"""Empirical delta: backward return on O_t; forward market_response via db.response."""

from __future__ import annotations

from typing import Any

from roller.measurement.backward import backward_measurements
from roller.measurement.response import build_response


def backward_delta(candles, as_of, end_of_day: bool = False) -> dict[str, Any]:
    return backward_measurements(candles, as_of, end_of_day=end_of_day)


def forward_market_response(cfg, **kwargs) -> dict[str, Any]:
    return build_response(cfg, **kwargs)
