#!/usr/bin/env python3
"""Portfolio / sizing / risk-of-ruin research. Configurable; not live allocations.

Candle paths are not fills. Gross P&L uses +1R / −2R. Fees/slippage are
explicit stress parameters, not KalshiFeeModel.
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict

import numpy as np

from common import (
    EV_UNCONDITIONAL,
    OUT,
    Q_UNCONDITIONAL,
    SEED,
    ev_from_q,
    split_rows,
    utc_now,
    write_json,
)
from eval_lib import load_analysis_rows

# Research parameters — not MLB/WNBA live fractions.
CONFIG = {
    "starting_bankroll": 10000.0,
    "position_fraction": 0.02,
    "constant_nominal": 200.0,
    "max_concurrent": 5,
    "daily_exposure_cap_frac": 0.10,
    "weekly_exposure_cap_frac": 0.25,
    "loss_limit_frac": 0.20,
    "fee_per_trade_frac": 0.0,
    "slippage_r": 0.0,
    "n_mc": 2000,
    "dd_thresholds": [0.05, 0.10, 0.15, 0.20, 0.25],
    "win_rate_stress": [None, 0.725, 0.70, 0.68, 0.67],
}


def trade_r(y40: int, slippage_r: float) -> float:
    # survive +1R, barrier −2R, minus optional slippage
    return ((-2.0 if y40 else 1.0) - slippage_r)


def chronological_equity(rows, size_fn, start, fee_frac, slippage_r, max_dd_stop=None):
    equity = start
    hwm = start
    peak = start
    max_dd = 0.0
    curve = []
    daily_pnl = defaultdict(float)
    for r in sorted(rows, key=lambda x: (x.get("game_date") or "", x.get("entry_decision_time") or 0)):
        dd = 0.0 if peak <= 0 else (peak - equity) / peak
        if max_dd_stop is not None and dd >= max_dd_stop:
            curve.append(equity)
            continue
        stake = size_fn(equity, hwm, dd)
        if stake <= 0 or equity <= 0:
            curve.append(equity)
            continue
        r_mult = trade_r(int(r.get("Y_40_CLOSE") or 0), slippage_r)
        pnl = stake * r_mult - stake * fee_frac
        equity = equity + pnl
        hwm = max(hwm, equity)
        peak = max(peak, equity)
        max_dd = max(max_dd, 0.0 if peak <= 0 else (peak - equity) / peak)
        daily_pnl[r.get("game_date")] += pnl
        curve.append(equity)
    return {
        "terminal": equity,
        "max_dd": max_dd,
        "curve": curve,
        "daily_pnl": dict(daily_pnl),
        "n": len(rows),
    }


def size_constant(nominal):
    def fn(equity, hwm, dd):
        return min(nominal, max(equity, 0.0))

    return fn


def size_fractional(frac):
    def fn(equity, hwm, dd):
        return max(equity, 0.0) * frac

    return fn


def size_hwm(frac):
    def fn(equity, hwm, dd):
        return min(equity, hwm) * frac

    return fn


def size_dd_responsive(frac, schedule=None):
    schedule = schedule or [(0.03, 1.0), (0.05, 0.75), (0.08, 0.50), (1.0, 0.25)]

    def fn(equity, hwm, dd):
        scale = 0.25
        for thresh, s in schedule:
            if dd < thresh:
                scale = s
                break
        return max(equity, 0.0) * frac * scale

    return fn


def sharpe(daily):
    xs = np.array(list(daily.values()), dtype=float)
    if len(xs) < 2:
        return None
    sd = float(xs.std(ddof=1))
    if sd <= 0:
        return None
    return float(xs.mean() / sd * math.sqrt(365))


def sortino(daily):
    xs = np.array(list(daily.values()), dtype=float)
    if len(xs) < 2:
        return None
    neg = xs[xs < 0]
    if len(neg) < 1:
        return None
    ds = float(np.sqrt(np.mean(neg**2)))
    if ds <= 0:
        return None
    return float(xs.mean() / ds * math.sqrt(365))


def mc_ruin(p_win, n_trades, size_model, cfg, rng, block_p=None):
    """IID Bernoulli unless block_p provided as empirical day-level rates."""
    start = cfg["starting_bankroll"]
    frac = cfg["position_fraction"]
    n_mc = cfg["n_mc"]
    results = []
    for _ in range(n_mc):
        equity = start
        hwm = start
        peak = start
        max_dd = 0.0
        for i in range(n_trades):
            dd = 0.0 if peak <= 0 else (peak - equity) / peak
            if size_model == "constant":
                stake = min(cfg["constant_nominal"], max(equity, 0))
            elif size_model == "fractional":
                stake = max(equity, 0) * frac
            elif size_model == "hwm":
                stake = min(equity, hwm) * frac
            else:
                scale = 1.0
                if dd >= 0.08:
                    scale = 0.25
                elif dd >= 0.05:
                    scale = 0.50
                elif dd >= 0.03:
                    scale = 0.75
                stake = max(equity, 0) * frac * scale
            win = rng.random() < p_win
            r_mult = 1.0 if win else -2.0
            equity = equity + stake * r_mult
            hwm = max(hwm, equity)
            peak = max(peak, equity)
            max_dd = max(max_dd, 0.0 if peak <= 0 else (peak - equity) / peak)
            if equity <= 0:
                equity = 0.0
                break
        results.append({"terminal": equity, "max_dd": max_dd, "ruined": equity <= 0.01 * start})
    dd = np.array([r["max_dd"] for r in results])
    term = np.array([r["terminal"] for r in results])
    out = {
        "p_win": p_win,
        "n_trades": n_trades,
        "size_model": size_model,
        "p_ruin_1pct": float(np.mean(term <= 0.01 * start)),
        "median_terminal": float(np.median(term)),
        "median_dd": float(np.median(dd)),
        "p95_dd": float(np.quantile(dd, 0.95)),
        "p99_dd": float(np.quantile(dd, 0.99)),
        "p_dd": {str(t): float(np.mean(dd >= t)) for t in cfg["dd_thresholds"]},
    }
    return out


def block_bootstrap_dd(rows, cfg, rng, n_mc=None):
    """Resample game dates with replacement (cluster risk)."""
    n_mc = n_mc or cfg["n_mc"]
    by_date = defaultdict(list)
    for r in rows:
        by_date[r.get("game_date")].append(r)
    dates = list(by_date.keys())
    start = cfg["starting_bankroll"]
    frac = cfg["position_fraction"]
    dds = []
    for _ in range(n_mc):
        equity = start
        peak = start
        max_dd = 0.0
        sampled = rng.choice(dates, size=len(dates), replace=True)
        for d in sampled:
            for r in by_date[d]:
                stake = max(equity, 0) * frac
                r_mult = trade_r(int(r.get("Y_40_CLOSE") or 0), 0.0)
                equity = equity + stake * r_mult
                peak = max(peak, equity)
                max_dd = max(max_dd, 0.0 if peak <= 0 else (peak - equity) / peak)
                if equity <= 0:
                    equity = 0
                    break
            if equity <= 0:
                break
        dds.append(max_dd)
    dds = np.array(dds)
    return {
        "median_dd": float(np.median(dds)),
        "p95_dd": float(np.quantile(dds, 0.95)),
        "p99_dd": float(np.quantile(dds, 0.99)),
        "p_dd": {str(t): float(np.mean(dds >= t)) for t in cfg["dd_thresholds"]},
    }


def summarize_path(path, name):
    curve = path["curve"]
    return {
        "name": name,
        "n": path["n"],
        "terminal": path["terminal"],
        "max_dd": path["max_dd"],
        "sharpe": sharpe(path["daily_pnl"]),
        "sortino": sortino(path["daily_pnl"]),
        "equity_curve_downsample": curve[:: max(1, len(curve) // 80)] if curve else [],
    }


def main() -> int:
    rng = np.random.default_rng(SEED)
    rows = load_analysis_rows()
    primary = [
        r
        for r in rows
        if r.get("alignment_confidence") in ("HIGH", "MEDIUM")
    ]
    primary = sorted(primary, key=lambda x: (x.get("game_date") or "", x.get("entry_decision_time") or 0))
    cfg = CONFIG
    fee = cfg["fee_per_trade_frac"]
    slip = cfg["slippage_r"]
    start = cfg["starting_bankroll"]
    frac = cfg["position_fraction"]

    paths = {
        "A_constant_nominal": chronological_equity(
            primary, size_constant(cfg["constant_nominal"]), start, fee, slip
        ),
        "B_fixed_fractional": chronological_equity(
            primary, size_fractional(frac), start, fee, slip
        ),
        "C_high_water_mark": chronological_equity(
            primary, size_hwm(frac), start, fee, slip
        ),
        "D_drawdown_responsive": chronological_equity(
            primary, size_dd_responsive(frac), start, fee, slip
        ),
    }
    summaries = {k: summarize_path(v, k) for k, v in paths.items()}

    n = len(primary)
    p_hist = 1.0 - (sum(int(r["Y_40_CLOSE"]) for r in primary) / n if n else Q_UNCONDITIONAL)
    mc = []
    for model in ("constant", "fractional", "hwm", "dd"):
        for wr in cfg["win_rate_stress"]:
            p = p_hist if wr is None else wr
            mc.append(mc_ruin(p, n, model, cfg, rng))

    # serial: daily barrier rate autocorrelation
    by_date = defaultdict(list)
    for r in primary:
        by_date[r.get("game_date")].append(int(r["Y_40_CLOSE"]))
    dates = sorted(d for d in by_date if d)
    daily_q = [sum(by_date[d]) / len(by_date[d]) for d in dates]
    ac1 = None
    if len(daily_q) > 3:
        a = np.array(daily_q[1:], dtype=float)
        b = np.array(daily_q[:-1], dtype=float)
        if a.std() > 0 and b.std() > 0:
            ac1 = float(np.corrcoef(a, b)[0, 1])

    block = block_bootstrap_dd(primary, cfg, rng, n_mc=1500)

    write_json(
        OUT / "experiments" / "portfolio.json",
        {
            "written_utc": utc_now(),
            "seed": SEED,
            "config": cfg,
            "disclaimer": (
                "Research simulation. Not live sizing. Not a fill model. "
                "R multiples assume 80→100 vs 80→40. Concurrent-cap is not "
                "path-simulated beyond sequential equity; overlapping positions "
                "are a residual limitation."
            ),
            "historical_survival": p_hist,
            "sizing_paths": summaries,
            "monte_carlo": mc,
            "daily_q_lag1_autocorr": ac1,
            "block_bootstrap_by_game_date": block,
            "n_primary": n,
        },
    )
    print(f"portfolio n={n} survival={p_hist:.4f} ac1={ac1}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
