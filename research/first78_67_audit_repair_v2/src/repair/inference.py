"""Centered studentized cluster bootstrap and account returns."""

from __future__ import annotations

import math
import random
from collections import defaultdict


def per_contract(trades: list[dict]) -> float | None:
    vals = [int(t["net_pnl_cents"]) / int(t["contracts"]) for t in trades if int(t["contracts"]) > 0]
    if not vals:
        return None
    return sum(vals) / len(vals)


def studentized_cluster_p(trades: list[dict], *, draws: int, seed: int, min_days: int = 10) -> dict:
    by_day: dict[str, list[float]] = defaultdict(list)
    for trade in trades:
        contracts = int(trade["contracts"])
        if contracts <= 0:
            continue
        by_day[str(trade["local_day"])].append(int(trade["net_pnl_cents"]) / contracts)
    days = sorted(by_day)
    if len(days) < min_days:
        return {"status": "P_VALUE_NOT_ESTIMABLE", "reason": "INSUFFICIENT_EVIDENCE", "n_days": len(days)}
    observed_vals = [v for day in days for v in by_day[day]]
    observed = sum(observed_vals) / len(observed_vals)

    def stat(sample_days: list[str]) -> tuple[float, float]:
        vals = [v for day in sample_days for v in by_day[day]]
        mean = sum(vals) / len(vals)
        day_means = [sum(by_day[day]) / len(by_day[day]) for day in sample_days]
        if len(set(day_means)) < 2:
            return mean, 0.0
        center = sum(day_means) / len(day_means)
        var = sum((x - center) ** 2 for x in day_means) / (len(day_means) - 1)
        return mean, math.sqrt(var / len(day_means))

    t_mean, se = stat(days)
    if se == 0:
        return {"status": "P_VALUE_NOT_ESTIMABLE", "reason": "ZERO_CLUSTER_SE", "n_days": len(days), "observed_mean": observed}
    t_obs = (t_mean - 0.0) / se
    rng = random.Random(seed)
    extreme = 0
    used = 0
    for _ in range(draws):
        picked = [days[rng.randrange(len(days))] for _ in days]
        mean, se_star = stat(picked)
        if se_star == 0:
            continue
        used += 1
        t_star = (mean - observed) / se_star
        if t_star >= t_obs:
            extreme += 1
    if used == 0:
        return {"status": "P_VALUE_NOT_ESTIMABLE", "reason": "NO_FINITE_BOOTSTRAP_SE", "n_days": len(days)}
    return {
        "status": "ESTIMATED",
        "n_days": len(days),
        "observed_mean_cents_per_contract": observed,
        "one_sided_p": (1 + extreme) / (used + 1),
        "draws_used": used,
        "null": "centered studentized cluster bootstrap",
    }


def holm(items: list[tuple[str, float]]) -> list[dict]:
    ordered = sorted(items, key=lambda item: item[1])
    m = len(ordered)
    running = 0.0
    rows = []
    for i, (name, pval) in enumerate(ordered):
        running = max(running, min(1.0, (m - i) * pval))
        rows.append({"endpoint": name, "raw_p": pval, "holm_p": running})
    return rows


def account_returns(equity: list[float]) -> list[float | None]:
    out: list[float | None] = []
    for prev, cur in zip(equity, equity[1:]):
        if prev == 0:
            out.append(None)
        else:
            out.append(cur / prev - 1)
    return out


def max_drawdown_fraction(series: list[float]) -> float:
    peak = series[0]
    worst = 0.0
    for value in series:
        peak = max(peak, value)
        if peak:
            worst = max(worst, 1 - value / peak)
    return worst
