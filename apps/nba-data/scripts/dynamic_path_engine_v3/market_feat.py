"""Causal market-path features at a post-entry state timestamp."""

from __future__ import annotations

import math

from common import HIT40, HIT80, e4_to_cents


def _stdev(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _mean(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    return sum(xs) / len(xs)


def window(series, idx, n):
    if idx is None or n <= 0:
        return None
    start = idx + 1 - n
    if start < 0:
        return None
    return series[start : idx + 1]


def market_at(series, idx, entry_idx, entry_bid_e4):
    q = series[idx]
    bid = q["bid_c"]
    ask = q["ask_c"]
    mid = None if bid is None or ask is None else (bid + ask) / 2.0
    dist40 = None if bid is None else e4_to_cents(bid - HIT40)
    dist80 = None if bid is None else e4_to_cents(bid - HIT80)
    dist_ent = None if bid is None or entry_bid_e4 is None else e4_to_cents(bid - entry_bid_e4)
    norm = None if bid is None else (e4_to_cents(bid) - 40.0) / 40.0
    post = series[entry_idx + 1 : idx + 1] if entry_idx is not None and idx > entry_idx else series[: idx + 1]
    post_c = [r["bid_c"] for r in post if r["bid_c"] is not None]
    mae = mfe = None
    if entry_bid_e4 is not None and post_c:
        mae = e4_to_cents(min(post_c) - entry_bid_e4)
        mfe = e4_to_cents(max(post_c) - entry_bid_e4)
    post_high = max(post_c) if post_c else None
    post_low = min(post_c) if post_c else None
    dd_high = None if bid is None or post_high is None else e4_to_cents(post_high - bid)
    dist_low = None if bid is None or post_low is None else e4_to_cents(bid - post_low)
    rets = []
    for a, b in zip(post, post[1:]):
        if a["bid_c"] is not None and b["bid_c"] is not None:
            rets.append(e4_to_cents(b["bid_c"] - a["bid_c"]))
    net = sum(rets) if rets else None
    tot = sum(abs(x) for x in rets) if rets else None
    peff = None if not tot else (abs(net) / tot if net is not None else None)
    down = up = 0
    for x in reversed(rets):
        if x < 0:
            down += 1
            if up:
                break
        elif x > 0:
            up += 1
            if down:
                break
        else:
            break
    frac_neg = None if not rets else sum(1 for x in rets if x < 0) / len(rets)
    acc = None
    if len(rets) >= 2:
        acc = rets[-1] - rets[-2]
    vel40 = None
    if len(post_c) >= 2 and bid is not None:
        vel40 = e4_to_cents(post_c[-2] - bid)  # positive = moving toward 40
    below = {70: 0, 60: 0, 50: 0}
    for r in post:
        c = r["bid_c"]
        if c is None:
            continue
        if c < 7000:
            below[70] += 1
        if c < 6000:
            below[60] += 1
        if c < 5000:
            below[50] += 1
    approaches = {60: 0, 50: 0, 45: 0}
    for a, b in zip(post_c, post_c[1:]):
        if a > 6000 >= b:
            approaches[60] += 1
        if a > 5000 >= b:
            approaches[50] += 1
        if a > 4500 >= b:
            approaches[45] += 1
    rebound = None
    if len(rets) >= 4 and any(x < 0 for x in rets[-4:-1]):
        rebound = sum(rets[-3:])
    failed_rec = 0
    for i in range(3, len(rets)):
        if rets[i - 3] < 0 and rets[i - 2] < 0 and rets[i - 1] > 0 and rets[i] < 0:
            failed_rec += 1
    pct_entry_bar = None
    if entry_bid_e4 is not None and bid is not None and entry_bid_e4 != HIT40:
        pct_entry_bar = (entry_bid_e4 - bid) / (entry_bid_e4 - HIT40)
    recov = None
    if dd_high is not None and dist_low is not None and (dd_high + dist_low) > 0:
        recov = dist_low / (dd_high + dist_low)
    out = {
        "yes_bid_close_e4": bid,
        "yes_ask_close_e4": ask,
        "estimated_mid_e4": mid,
        "spread_cents": None if bid is None or ask is None else e4_to_cents(ask - bid),
        "distance_to_40_cents": dist40,
        "distance_to_80_cents": dist80,
        "distance_from_entry_cents": dist_ent,
        "norm_position_40_80": norm,
        "mae_since_entry_cents": mae,
        "mfe_since_entry_cents": mfe,
        "drawdown_from_post_entry_high_cents": dd_high,
        "distance_from_post_entry_low_cents": dist_low,
        "path_efficiency": peff,
        "consecutive_down": down,
        "consecutive_up": up,
        "frac_negative_candles": frac_neg,
        "price_acceleration_cents": acc,
        "velocity_toward_40_cents": vel40,
        "minutes_below_70": below[70],
        "minutes_below_60": below[60],
        "minutes_below_50": below[50],
        "n_approaches_60": approaches[60],
        "n_approaches_50": approaches[50],
        "n_approaches_45": approaches[45],
        "rebound_after_weakness_cents": rebound,
        "failed_recoveries": failed_rec,
        "percent_of_entry_to_barrier": pct_entry_bar,
        "recovery_from_drawdown": recov,
        "n_post_entry_candles": len(post),
        "volatility_kind": "1-MINUTE CANDLE VOLATILITY PROXY",
    }
    for n, lab in ((1, "1m"), (3, "3m"), (5, "5m"), (10, "10m"), (15, "15m")):
        w = window(series, idx, n)
        mom = vol = rng = None
        if w and w[0]["bid_c"] is not None and w[-1]["bid_c"] is not None:
            mom = e4_to_cents(w[-1]["bid_c"] - w[0]["bid_c"])
        if w:
            chg = []
            ranges = []
            for j in range(1, len(w)):
                a, b = w[j - 1]["bid_c"], w[j]["bid_c"]
                if a is not None and b is not None:
                    chg.append(e4_to_cents(b - a))
            for r in w:
                if r["bid_h"] is not None and r["bid_l"] is not None:
                    ranges.append(e4_to_cents(r["bid_h"] - r["bid_l"]))
            vol = _stdev(chg)
            rng = _mean(ranges)
        out[f"momentum_{lab}_cents"] = mom
        out[f"vol_{lab}_cents"] = vol
        out[f"range_{lab}_mean_cents"] = rng
        out[f"window_{lab}_complete"] = w is not None
    v5, v15 = out["vol_5m_cents"], out["vol_15m_cents"]
    out["vol_shock"] = None if not v15 else (None if v5 is None else v5 / v15)
    # event-response path label from post-entry returns
    out["path_archetype_rule"] = _rule_label(rets, peff, down, mae)
    return out


def _rule_label(rets, peff, consec_down, mae):
    if not rets or len(rets) < 3:
        return "INSUFFICIENT"
    last3 = rets[-3:]
    net3 = sum(last3)
    osc = sum(1 for a, b in zip(last3, last3[1:]) if a * b < 0)
    if consec_down >= 4 and (mae is not None and mae <= -10):
        return "SHOCK_AND_CONTINUATION"
    if mae is not None and mae <= -8 and last3[-1] > 0 and net3 > 0:
        return "SHOCK_AND_RECOVERY"
    if peff is not None and peff < 0.25 and osc >= 2:
        return "OSCILLATORY_PATH"
    if net3 <= -4 and consec_down >= 2:
        return "GRADUAL_DECAY"
    if peff is not None and peff >= 0.6 and net3 >= 0:
        return "STABLE_PATH"
    return "MIXED"
