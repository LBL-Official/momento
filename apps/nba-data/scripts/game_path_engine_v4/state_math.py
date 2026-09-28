"""Causal state-block calculations. Prefixes: game_ market_ path_ dyn_ econ_ coupling_."""

from __future__ import annotations

import numpy as np

from common import DSTAR_C, e4_to_cents


def pe(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return None
    tv = sum(abs(b - a) for a, b in zip(xs, xs[1:]))
    if tv <= 0:
        return None
    return abs(xs[-1] - xs[0]) / tv


def stdev(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return None
    return float(np.std(xs, ddof=1))


def rng(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    return float(max(xs) - min(xs))


def minutes_since_below(cents, level):
    last = None
    for i, c in enumerate(cents):
        if c is not None and c < level:
            last = i
    if last is None:
        return None
    return float(len(cents) - 1 - last)


def lookback(seq, idx, minutes):
    t = seq[idx]["ts"]
    out = []
    for j in range(idx, -1, -1):
        if t - seq[j]["ts"] > minutes * 60:
            break
        out.append(seq[j])
    out.reverse()
    return out


def bid_cents_list(window):
    return [e4_to_cents(q["bid_c"]) for q in window if q["bid_c"] is not None]


def mom(seq, idx, minutes):
    w = lookback(seq, idx, minutes)
    if len(w) < 2:
        return None
    a, b = e4_to_cents(w[0]["bid_c"]), e4_to_cents(w[-1]["bid_c"])
    if a is None or b is None:
        return None
    return b - a


def vol_proxy(seq, idx, minutes):
    w = lookback(seq, idx, minutes)
    cents = bid_cents_list(w)
    if len(cents) < 3:
        return None
    d = np.diff(cents)
    return float(np.std(d, ddof=1)) if len(d) >= 2 else None


def dstar(d, tau_s):
    if d is None or tau_s is None:
        return None
    return d / ((max(tau_s, 0.0) + DSTAR_C) ** 0.5)


def lsi(abs_d, sig, vel, acc, lam, gam):
    if abs_d is None:
        return None
    s = 0.0 if sig is None else abs(sig)
    v = 0.0 if vel is None else abs(vel)
    a = 0.0 if acc is None else abs(acc)
    return abs_d / (1.0 + s + lam * v + gam * a)


def u_game(abs_d, tau_s, sig, n_lc):
    if abs_d is None:
        return None
    tau = 0.0 if tau_s is None else max(tau_s, 0.0)
    s = 0.0 if sig is None else abs(sig)
    n = 0 if n_lc is None else n_lc
    return ((tau + DSTAR_C) ** 0.5) * (1.0 + s) * (1.0 + n) / (1.0 + abs_d)
