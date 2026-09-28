"""Backward measurements M_{≤t}. Visible candles only. Not future responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from roller.measurement.integers import parse_e4
from roller.state.missingness import section
from roller.timeutil import apply_as_of, resolve_cutoff, series_to_utc

MEASUREMENT_VERSION = "v1"
PATH_STATUS = "UNORDERED_SUMMARY"


def _point(
    name: str,
    value: int | None,
    status: str,
    **extra: Any,
) -> dict[str, Any]:
    body = {
        "measurement_name": name,
        "measurement_version": MEASUREMENT_VERSION,
        "value": value,
        "status": status,
        "source_resolution": "1m",
        "k_field": "yes_bid_close",
        "information_boundary": "backward",
        "path_information_status": PATH_STATUS,
    }
    body.update(extra)
    return body


def visible_candles(candles: pd.DataFrame, as_of, end_of_day: bool = False) -> pd.DataFrame:
    if candles is None or candles.empty:
        return pd.DataFrame()
    cutoff = as_of if isinstance(as_of, datetime) else resolve_cutoff(as_of, end_of_day=end_of_day)
    out = apply_as_of(candles, cutoff)
    if out.empty:
        return out
    if "team_side" in out.columns:
        home = out[out["team_side"].astype(str) == "home"]
        if not home.empty:
            out = home
    ts = series_to_utc(out["available_at"])
    return out.assign(_t=ts).dropna(subset=["_t"]).sort_values("_t").drop(columns=["_t"])


def backward_measurements(candles: pd.DataFrame, as_of, end_of_day: bool = False) -> dict[str, Any]:
    vis = visible_candles(candles, as_of, end_of_day=end_of_day)
    if vis.empty:
        return section("PARTIAL", {"measurements": {}, "n_visible_candles": 0})

    closes = [parse_e4(v) for v in vis["yes_bid_close"].tolist()]
    opens = [parse_e4(v) for v in vis["yes_bid_open"].tolist()] if "yes_bid_open" in vis.columns else [None] * len(vis)
    highs = [parse_e4(v) for v in vis["yes_bid_high"].tolist()] if "yes_bid_high" in vis.columns else [None] * len(vis)
    lows = [parse_e4(v) for v in vis["yes_bid_low"].tolist()] if "yes_bid_low" in vis.columns else [None] * len(vis)

    last_c, last_o, last_h, last_l = closes[-1], opens[-1], highs[-1], lows[-1]
    prev_c = closes[-2] if len(closes) >= 2 else None

    if last_c is not None and prev_c is not None:
        ret = _point("market_return_1m_backward", last_c - prev_c, "valid")
    else:
        ret = _point("market_return_1m_backward", None, "insufficient_history")

    if last_c is not None and last_o is not None:
        otc = _point("open_to_close_delta_1m", last_c - last_o, "valid")
    else:
        otc = _point("open_to_close_delta_1m", None, "insufficient_history")

    if last_h is not None and last_l is not None:
        hl = _point("high_low_range_1m", last_h - last_l, "valid")
    else:
        hl = _point("high_low_range_1m", None, "insufficient_history")

    known_closes = [c for c in closes if c is not None]
    if len(known_closes) < 2:
        vol = _point("close_to_close_realized_volatility", None, "insufficient_history", abs_change_sum=0, n_changes=0)
    else:
        diffs = [abs(known_closes[i] - known_closes[i - 1]) for i in range(1, len(known_closes))]
        vol = _point(
            "close_to_close_realized_volatility",
            int(sum(diffs)),
            "valid",
            abs_change_sum=int(sum(diffs)),
            n_changes=len(diffs),
        )

    if last_c is None or last_o is None or last_h is None or last_l is None:
        eff = _point("directional_efficiency", None, "insufficient_history")
    else:
        num = abs(last_c - last_o)
        den = last_h - last_l
        if den == 0:
            eff = _point("directional_efficiency", None, "undefined_zero_range", numerator_e4=num, denominator_e4=0)
        else:
            eff = _point(
                "directional_efficiency",
                None,
                "valid",
                numerator_e4=num,
                denominator_e4=den,
                milliratio=(num * 1000) // den,
            )

    if len(known_closes) < 3:
        acc = _point("market_acceleration_1m", None, "insufficient_history")
    else:
        d1 = known_closes[-1] - known_closes[-2]
        d0 = known_closes[-2] - known_closes[-3]
        acc = _point("market_acceleration_1m", d1 - d0, "valid")

    data = {
        "n_visible_candles": int(len(vis)),
        "measurements": {
            "market_return_1m_backward": ret,
            "open_to_close_delta_1m": otc,
            "high_low_range_1m": hl,
            "close_to_close_realized_volatility": vol,
            "directional_efficiency": eff,
            "market_acceleration_1m": acc,
        },
    }
    return section("REAL", data)
