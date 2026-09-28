"""Descriptive statistics that do not retune 78/67."""

from __future__ import annotations

import math
import random
from collections import Counter
from decimal import Decimal
from typing import Any

from first78.portfolio import replay


def sharpe(values: list[float], periods_per_year: int) -> dict[str, Any]:
    n = len(values)
    if n < 2:
        return {"n": n, "sharpe": None, "annualized_sharpe": None, "reason": "N_LT_2"}
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    if var == 0:
        return {"n": n, "sharpe": None, "annualized_sharpe": None, "reason": "ZERO_VARIANCE", "mean": mean}
    sd = math.sqrt(var)
    ratio = mean / sd
    return {
        "n": n,
        "mean": mean,
        "stdev": sd,
        "sharpe_unannualized": ratio,
        "annualized_sharpe": ratio * math.sqrt(periods_per_year),
        "periods_per_year": periods_per_year,
        "risk_free_rate": 0,
        "reason": None,
    }


def max_drawdown(equity: list[int]) -> dict[str, Any]:
    if not equity:
        return {"max_drawdown_pct": None, "reason": "EMPTY"}
    peak = equity[0]
    peak_i = 0
    worst = 0.0
    trough_i = 0
    worst_peak_i = 0
    for i, value in enumerate(equity):
        if value > peak:
            peak = value
            peak_i = i
        if peak > 0:
            dd = 1 - (value / peak)
            if dd > worst:
                worst = dd
                trough_i = i
                worst_peak_i = peak_i
    return {
        "max_drawdown_fraction": worst,
        "peak_index": worst_peak_i,
        "trough_index": trough_i,
        "peak_equity_cents": equity[worst_peak_i],
        "trough_equity_cents": equity[trough_i],
    }


def binomial_records(win_cents: int, loss_cents: int, p: Decimal) -> list[dict[str, Any]]:
    """Eleven fixed-size ten-trade records. loss_cents is the absolute loss."""
    rows = []
    ev = Decimal(0)
    for k in range(11):
        pnl = k * win_cents - (10 - k) * loss_cents
        prob = _binom_pmf(10, k, p)
        contrib = prob * Decimal(pnl)
        ev += contrib
        rows.append(
            {
                "wins": k,
                "losses": 10 - k,
                "pnl_cents": pnl,
                "probability": format(prob, "f"),
                "ev_contribution_cents": format(contrib, "f"),
            }
        )
    rows.append({"wins": "SUM", "losses": "", "pnl_cents": "", "probability": "1", "ev_contribution_cents": format(ev, "f")})
    return rows


def _binom_pmf(n: int, k: int, p: Decimal) -> Decimal:
    return Decimal(math.comb(n, k)) * (p ** k) * ((1 - p) ** (n - k))


def transition_matrix(labels: list[str]) -> dict[str, Any]:
    states = ["W", "L", "F"]
    counts = {a: Counter() for a in states}
    for prev, nxt in zip(labels, labels[1:]):
        if prev in counts and nxt in states:
            counts[prev][nxt] += 1
    probs = {}
    for state in states:
        total = sum(counts[state].values())
        if total == 0:
            probs[state] = {s: None for s in states}
        else:
            probs[state] = {s: counts[state][s] / total for s in states}
    return {"counts": {a: dict(counts[a]) for a in states}, "probs": probs, "n_transitions": max(0, len(labels) - 1)}


def block_bootstrap_equity(
    candidates: list[dict[str, Any]],
    *,
    block: int,
    n_paths: int,
    seed: int,
    entry_price_cents: int = 78,
    stop_price_cents: int = 67,
) -> list[int]:
    by_day: dict[str, list[dict[str, Any]]] = {}
    for cand in candidates:
        by_day.setdefault(cand["local_day"], []).append(cand)
    days = sorted(by_day)
    if not days:
        return []
    rng = random.Random(seed)
    out = []
    span = max(1, len(days) - block + 1)
    for i in range(n_paths):
        picked: list[str] = []
        while len(picked) < len(days):
            start = rng.randrange(span)
            picked.extend(days[start : start + block])
        picked = picked[: len(days)]
        built = []
        cursor = 1_800_000_000
        for day in picked:
            group = by_day[day]
            base = min(int(c["signal_ts"]) for c in group)
            shift = cursor - base
            for cand in group:
                nxt = {k: v for k, v in cand.items() if k != "path"}
                nxt["signal_ts"] = int(cand["signal_ts"]) + shift
                nxt["exit_ts"] = int(cand["exit_ts"]) + shift
                nxt["cash_ts"] = int(cand["cash_ts"]) + shift
                nxt["game_id"] = f"{cand['game_id']}-p{i}-{shift}"
                built.append(nxt)
            cursor += 86400 * max(block, 1) + 5
        book = replay(
            built,
            entry_price_cents=entry_price_cents,
            stop_price_cents=stop_price_cents,
        )
        out.append(book.ending_equity_cents)
    return out
