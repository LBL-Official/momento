"""Market-path features at first-80. Candle windows end at ENTRY_DECISION_TIME."""

from __future__ import annotations

from common import HIT80, e4_to_cents, mean, stdev


def _closes(window):
    return [r["bid_c"] for r in window]


def _rets_cents(window):
    out = []
    for i in range(1, len(window)):
        a, b = window[i - 1]["bid_c"], window[i]["bid_c"]
        if a is None or b is None:
            out.append(None)
        else:
            out.append(e4_to_cents(b - a))
    return out


def _ranges_cents(window):
    out = []
    for r in window:
        if r["bid_h"] is not None and r["bid_l"] is not None:
            out.append(e4_to_cents(r["bid_h"] - r["bid_l"]))
        else:
            out.append(None)
    return out


def window_ending_at(rows, idx, n_candles):
    if idx is None or n_candles <= 0:
        return None
    start = idx + 1 - n_candles
    if start < 0:
        return None
    return rows[start : idx + 1]


def minutes_since_below(rows, idx, level_e4: int) -> float | None:
    if idx is None:
        return None
    entry_ts = rows[idx]["ts"]
    last = None
    for j in range(idx, -1, -1):
        c = rows[j]["bid_c"]
        if c is not None and c < level_e4:
            last = rows[j]["ts"]
            break
    if last is None:
        return None
    return (entry_ts - last) / 60.0


def market_features(series, entry_ts: int) -> dict:
    idx = None
    for i, r in enumerate(series):
        if r["ts"] == entry_ts:
            idx = i
            break
    q = series[idx] if idx is not None else None
    out = {
        "distance_above_80_cents": None
        if q is None or q["bid_c"] is None
        else e4_to_cents(q["bid_c"] - HIT80),
        "spread_cents": None
        if q is None or q["bid_c"] is None or q["ask_c"] is None
        else e4_to_cents(q["ask_c"] - q["bid_c"]),
        "volume_hundredths": None if q is None else q["vol"],
        "range_1m_cents": None
        if q is None or q["bid_h"] is None or q["bid_l"] is None
        else e4_to_cents(q["bid_h"] - q["bid_l"]),
        "entry_contiguous_1m": idx is not None,
    }
    for n, lab in ((1, "1m"), (5, "5m"), (15, "15m")):
        w = window_ending_at(series, idx, n)
        rets = _rets_cents(w) if w else []
        ranges = _ranges_cents(w) if w else []
        closes = _closes(w) if w else []
        first_c = closes[0] if closes else None
        last_c = closes[-1] if closes else None
        mom = None
        if first_c is not None and last_c is not None:
            mom = e4_to_cents(last_c - first_c)
        highs = [r["bid_h"] for r in w if r["bid_h"] is not None] if w else []
        lows = [r["bid_l"] for r in w if r["bid_l"] is not None] if w else []
        win_high = max(highs) if highs else None
        win_low = min(lows) if lows else None
        up = sum(1 for x in rets if x is not None and x > 0)
        down = sum(1 for x in rets if x is not None and x < 0)
        dist_high = None
        dist_low = None
        if last_c is not None and win_high is not None:
            dist_high = e4_to_cents(last_c - win_high)
        if last_c is not None and win_low is not None:
            dist_low = e4_to_cents(last_c - win_low)
        out[f"momentum_{lab}_cents"] = mom
        out[f"vol_{lab}_cents"] = stdev(rets)
        out[f"range_{lab}_mean_cents"] = mean(ranges)
        out[f"up_count_{lab}"] = up if w else None
        out[f"down_count_{lab}"] = down if w else None
        out[f"dist_from_{lab}_high_cents"] = dist_high
        out[f"dist_from_{lab}_low_cents"] = dist_low
        out[f"_n_candles_{lab}"] = None if w is None else len(w)
    # acceleration: last 1m change minus previous 1m change
    acc = None
    if idx is not None and idx >= 2:
        a = series[idx]["bid_c"]
        b = series[idx - 1]["bid_c"]
        c = series[idx - 2]["bid_c"]
        if a is not None and b is not None and c is not None:
            acc = e4_to_cents((a - b) - (b - c))
    out["market_acceleration_cents"] = acc
    out["minutes_from_50_to_80"] = minutes_since_below(series, idx, 5000)
    out["minutes_from_60_to_80"] = minutes_since_below(series, idx, 6000)
    out["minutes_from_70_to_80"] = minutes_since_below(series, idx, 7000)
    if q is not None and series:
        first_ts = series[0]["ts"]
        out["minutes_since_first_gw_candle"] = (entry_ts - first_ts) / 60.0
    else:
        out["minutes_since_first_gw_candle"] = None
    close_ts = None
    # minutes to close filled by caller if known
    out["feat_distance_from_80_cents"] = out["distance_above_80_cents"]
    out["feat_spread_cents"] = out["spread_cents"]
    out["feat_vol_1m_cents"] = out["vol_1m_cents"]
    out["feat_vol_5m_cents"] = out["vol_5m_cents"]
    out["feat_vol_15m_cents"] = out["vol_15m_cents"]
    out["feat_momentum_1m_cents"] = out["momentum_1m_cents"]
    out["feat_momentum_5m_cents"] = out["momentum_5m_cents"]
    out["feat_momentum_15m_cents"] = out["momentum_15m_cents"]
    out["feat_range_1m_cents"] = out["range_1m_cents"]
    return out
