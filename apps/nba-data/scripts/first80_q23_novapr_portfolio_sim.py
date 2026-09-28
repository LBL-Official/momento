#!/usr/bin/env python3
"""NBA 2Q/3Q FIRST80 Nov–Apr portfolio simulation (research only).

Projects 2026-27 Nov 1–Apr 11 trade count from the frozen 2025-26
Q2+Q3 FIRST80 tape (regular-season analog Nov 1–Apr 12 2025-26).

Sizing: 5% of start-of-day bankroll *per bet*, not per day. Same-day
trades share SOD size. Hard cap 6 bets / 30% of SOD bankroll. Extra
prints that day are skipped (first 6 by first_80_timestamp). Bankroll
compounds after the day's P&L. Arrival is the observed daily
occurrence vector — not one flat bet per calendar day.

Outcomes: 50/30/20 loser slip on the 40 signal (50% fill 40, 30% slip
to 20, 20% slip to 10). That raw mix is +3.419% of debit; the sim
haircuts P&L so expected debit return is the conservative 3.000%,
not 3.214% and not 3.419%. Winner-touches stay −40¢. Not a constant
+3% per trade.

Zero fee. Candle path. Does not change live FIRST01. Does not invent L2.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first80_quarter_barrier_survival as Q  # noqa: E402

OUT = Q.OUT.parent / "first80_q23_novapr_portfolio_sim"

WINDOW_START = date(2025, 11, 1)
WINDOW_END = date(2026, 4, 12)  # 2025-26 RS Sunday
PROJECT_START = date(2026, 11, 1)
PROJECT_END = date(2027, 4, 11)  # 2026-27 RS Sunday
EXPECTED_WINDOW_N = 508
EXPECTED_WINDOW_Q2 = 260
EXPECTED_WINDOW_Q3 = 248
EXPECTED_WINDOW_WEEKS = 24
EXPECTED_SURVIVE_604 = 450
EXPECTED_WTOUCH_604 = 55
EXPECTED_LOSE_604 = 99
EXPECTED_N_604 = 604

B0_CENTS = 2_000_000  # $20,000
FRACTION_PCT = 5  # per bet
MAX_TRADES_PER_DAY = 6
MAX_DAY_FRACTION_PCT = MAX_TRADES_PER_DAY * FRACTION_PCT  # 30
ENTRY_CENTS = Q.ENTRY_CENTS  # 80
EXPECTED_CAPPED_N = 499
EXPECTED_DROPPED = 9
EXPECTED_DAYS_OVER_CAP = 9
NAIVE_DEBIT_RETURN_PCT = 3  # constant-+3% path
CONSERVATIVE_DEBIT_RETURN_PCT = 3  # locked mean after haircut
N_SIM = 10_000
SEED = 20260905

# Per-contract P&L cents. Exit signal is still 40.
PNL_SURVIVE = Q.WIN_PNL_CENTS  # +20
PNL_WTOUCH = 40 - Q.ENTRY_CENTS  # −40
PNL_L40 = 40 - Q.ENTRY_CENTS  # −40
PNL_L20 = 20 - Q.ENTRY_CENTS  # −60
PNL_L10 = 10 - Q.ENTRY_CENTS  # −70

# Conservative loser fills: 50% at 40, 30% slip to 20, 20% slip to 10.
LOSE_AT_40_WGT = 50
LOSE_AT_20_WGT = 30
LOSE_AT_10_WGT = 20
# 0.50*(−40)+0.30*(−60)+0.20*(−70) = −52
LOSE_MIX_PNL = (
    LOSE_AT_40_WGT * PNL_L40 + LOSE_AT_20_WGT * PNL_L20 + LOSE_AT_10_WGT * PNL_L10
) // 100

# 604 book raw sum: 450*(+20)+55*(−40)+99*(−52) = 1,652¢ → 3.4189% of debit.
RAW_BOOK_SUM_CENTS = (
    EXPECTED_SURVIVE_604 * PNL_SURVIVE
    + EXPECTED_WTOUCH_604 * PNL_WTOUCH
    + EXPECTED_LOSE_604 * LOSE_MIX_PNL
)
# Haircut so E[pnl] = 2.4¢ = 3.000% of 80¢.
# 2.4 * 604 / 1652 = 1812/2065.
EDGE_SCALE_NUM = 1812
EDGE_SCALE_DEN = 2065

# Class weights over 6040: 450/604, 55/604, 99/604 * {50,30,20}%.
WEIGHTS_6040 = (
    EXPECTED_SURVIVE_604 * 10,  # 4500
    EXPECTED_WTOUCH_604 * 10,  # 550
    EXPECTED_LOSE_604 * LOSE_AT_40_WGT // 10,  # 495
    EXPECTED_LOSE_604 * LOSE_AT_20_WGT // 10,  # 297
    EXPECTED_LOSE_604 * LOSE_AT_10_WGT // 10,  # 198
)
PNL_TABLE = np.array([PNL_SURVIVE, PNL_WTOUCH, PNL_L40, PNL_L20, PNL_L10], dtype=np.int64)


class IdentityHalt(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def game_date_of(row: dict) -> date:
    return date.fromisoformat(str(row["game_date"])[:10])


def load_q23_rows() -> list[dict]:
    rows = Q._pq().read_table(Q.OUT / "trades.parquet").to_pylist()
    return [r for r in rows if r.get("entry_quarter_bucket") in ("Q2", "Q3")]


def window_rows(rows: list[dict] | None = None) -> list[dict]:
    rows = rows if rows is not None else load_q23_rows()
    out = [r for r in rows if WINDOW_START <= game_date_of(r) <= WINDOW_END]
    q2 = sum(1 for r in out if r["entry_quarter_bucket"] == "Q2")
    q3 = sum(1 for r in out if r["entry_quarter_bucket"] == "Q3")
    if len(out) != EXPECTED_WINDOW_N or q2 != EXPECTED_WINDOW_Q2 or q3 != EXPECTED_WINDOW_Q3:
        raise IdentityHalt(f"HALT window n={len(out)} q2={q2} q3={q3}")
    return sorted(out, key=lambda r: (game_date_of(r), int(r["first_80_timestamp"])))


def loser_mix_pnl_cents() -> int:
    if LOSE_AT_40_WGT + LOSE_AT_20_WGT + LOSE_AT_10_WGT != 100:
        raise IdentityHalt("HALT loser weights")
    if LOSE_MIX_PNL != -52:
        raise IdentityHalt(f"HALT mix {LOSE_MIX_PNL}")
    if RAW_BOOK_SUM_CENTS != 1652:
        raise IdentityHalt(f"HALT book {RAW_BOOK_SUM_CENTS}")
    return LOSE_MIX_PNL


def mix_probs_604() -> np.ndarray:
    loser_mix_pnl_cents()
    if sum(WEIGHTS_6040) != EXPECTED_N_604 * 10:
        raise IdentityHalt(f"HALT weights {WEIGHTS_6040}")
    return np.array(WEIGHTS_6040, dtype=np.float64) / (EXPECTED_N_604 * 10)


def apply_conservative_edge(raw_pnl_cents: np.ndarray) -> np.ndarray:
    """Haircut raw 50/30/20 P&L so E[debit return] = 3.000%, not 3.419%.

    Does not change the exit signal. T40 still fires the trade. This only
    scales cents so the conservative 3% mean is locked.
    """
    num = raw_pnl_cents.astype(np.int64) * EDGE_SCALE_NUM
    den = EDGE_SCALE_DEN
    pos = num >= 0
    mag = np.where(pos, num, -num)
    rounded = (mag + den // 2) // den
    return np.where(pos, rounded, -rounded)


def expected_debit_return_pct(probs: np.ndarray | None = None) -> float:
    p = mix_probs_604() if probs is None else probs
    ev_cents = float(p @ PNL_TABLE.astype(np.float64))
    return ev_cents / ENTRY_CENTS * 100.0


def calendar_days(start: date, end: date) -> list[date]:
    out = []
    cur = start
    while cur <= end:
        out.append(cur)
        cur += timedelta(days=1)
    return out


def iso_week_key(d: date) -> tuple[int, int]:
    iso = d.isocalendar()
    return (iso.year, iso.week)


def arrival_from_window(rows: list[dict]) -> dict:
    days = calendar_days(WINDOW_START, WINDOW_END)
    by_day: dict[date, list[dict]] = defaultdict(list)
    for r in rows:
        by_day[game_date_of(r)].append(r)
    daily_n = [len(by_day[d]) for d in days]
    daily_capped = [min(n, MAX_TRADES_PER_DAY) for n in daily_n]
    week_n: dict[tuple[int, int], int] = Counter()
    week_capped: dict[tuple[int, int], int] = Counter()
    week_labels: list[tuple[int, int]] = []
    seen = set()
    for d in days:
        k = iso_week_key(d)
        if k not in seen:
            seen.add(k)
            week_labels.append(k)
        week_n[k] += len(by_day[d])
        week_capped[k] += min(len(by_day[d]), MAX_TRADES_PER_DAY)
    if len(week_labels) != EXPECTED_WINDOW_WEEKS:
        raise IdentityHalt(f"HALT weeks {len(week_labels)}")
    if sum(daily_n) != EXPECTED_WINDOW_N:
        raise IdentityHalt(f"HALT daily sum {sum(daily_n)}")
    if sum(daily_capped) != EXPECTED_CAPPED_N:
        raise IdentityHalt(f"HALT capped {sum(daily_capped)}")
    if MAX_DAY_FRACTION_PCT != 30:
        raise IdentityHalt(f"HALT day cap {MAX_DAY_FRACTION_PCT}")
    month_n = Counter((game_date_of(r).year, game_date_of(r).month) for r in rows)
    return {
        "days": [d.isoformat() for d in days],
        "daily_n": daily_n,
        "daily_n_capped": daily_capped,
        "n_calendar_days": len(days),
        "n_active_days": sum(1 for n in daily_n if n > 0),
        "n_zero_days": sum(1 for n in daily_n if n == 0),
        "n_trades": sum(daily_n),
        "n_trades_capped": sum(daily_capped),
        "n_dropped_over_cap": sum(daily_n) - sum(daily_capped),
        "days_over_cap": sum(1 for n in daily_n if n > MAX_TRADES_PER_DAY),
        "max_same_day": max(daily_n),
        "max_same_day_traded": max(daily_capped),
        "mean_per_active_day": round(sum(daily_n) / sum(1 for n in daily_n if n > 0), 4),
        "mean_per_calendar_day": round(sum(daily_n) / len(days), 4),
        "iso_weeks": [
            {
                "year": y,
                "week": w,
                "n": week_n[(y, w)],
                "n_capped": week_capped[(y, w)],
                "label": f"{y}-W{w:02d}",
            }
            for y, w in week_labels
        ],
        "n_iso_weeks": len(week_labels),
        "trades_per_week_mean": round(sum(daily_n) / len(week_labels), 4),
        "trades_per_week_capped_mean": round(sum(daily_capped) / len(week_labels), 4),
        "trades_per_week_min": min(week_n[k] for k in week_labels),
        "trades_per_week_max": max(week_n[k] for k in week_labels),
        "trades_per_week_capped_min": min(week_capped[k] for k in week_labels),
        "trades_per_week_capped_max": max(week_capped[k] for k in week_labels),
        "month_n": {f"{y}-{m:02d}": n for (y, m), n in sorted(month_n.items())},
        "window_class": {
            "n": len(rows),
            "survive": sum(1 for r in rows if r["W"] and not r["T40"]),
            "winner_touch": sum(1 for r in rows if r["W"] and r["T40"]),
            "lose": sum(1 for r in rows if not r["W"]),
        },
    }


def contracts_from_bankroll_cents(bankroll_cents: int) -> int:
    """Contracts for one 5% bet. Not a daily budget."""
    if bankroll_cents <= 0:
        return 0
    debit = bankroll_cents * FRACTION_PCT // 100
    return debit // ENTRY_CENTS


def cap_daily_n(daily_n: list[int]) -> list[int]:
    return [min(int(n), MAX_TRADES_PER_DAY) for n in daily_n]


def naive_3pct_end_cents(daily_n: list[int], start_cents: int = B0_CENTS) -> int:
    """Every *taken* bet earns exactly 3% of that bet's 5% debit. Daily compound.

    Days are capped at 6 bets / 30% of SOD bankroll.
    """
    b = int(start_cents)
    for n in cap_daily_n(daily_n):
        if n <= 0:
            continue
        c = contracts_from_bankroll_cents(b)
        # 3% of 80¢ = 2.4¢/contract = 12/5.
        pnl = n * (c * 12 // 5)
        b += pnl
    return b


def simulate_paths(
    daily_n: list[int],
    n_sim: int = N_SIM,
    seed: int = SEED,
    start_cents: int = B0_CENTS,
    probs: np.ndarray | None = None,
) -> dict:
    """IID draws from the locked 5-class mix. Same arrival for every path.

    Same-day trades all size off start-of-day bankroll, then compound.
    Money is integer cents and integer contracts.
    """
    p = mix_probs_604() if probs is None else probs
    taken = cap_daily_n(daily_n)
    n_trades = int(sum(taken))
    rng = np.random.default_rng(seed)
    # (n_sim, n_trades) outcome indices 0..4
    draws = rng.choice(5, size=(n_sim, n_trades), p=p)
    pnl = PNL_TABLE[draws]  # int64

    b = np.full(n_sim, start_cents, dtype=np.int64)
    peak = b.copy()
    min_b = b.copy()
    max_dd_bp = np.zeros(n_sim, dtype=np.int64)  # peak-to-trough, basis points
    daily_ret = np.zeros((n_sim, len(taken)), dtype=np.float64)
    week_end_idx = []
    cursor = 0
    for t, n in enumerate(taken):
        prev = b.copy()
        if n > 0:
            contracts = (b * FRACTION_PCT // 100) // ENTRY_CENTS
            day_pnl_per = pnl[:, cursor : cursor + n].sum(axis=1)
            b = b + apply_conservative_edge(contracts * day_pnl_per)
            cursor += n
        daily_ret[:, t] = np.where(prev > 0, b.astype(np.float64) / prev.astype(np.float64) - 1.0, 0.0)
        min_b = np.minimum(min_b, b)
        peak = np.maximum(peak, b)
        dd = np.where(peak > 0, (peak - b) * 10000 // peak, 0)
        max_dd_bp = np.maximum(max_dd_bp, dd)
        week_end_idx.append(t)
    if cursor != n_trades:
        raise IdentityHalt(f"HALT cursor {cursor} != {n_trades}")
    return {
        "end_cents": b,
        "min_cents": min_b,
        "max_dd_bp": max_dd_bp,
        "daily_ret": daily_ret,
        "n_sim": n_sim,
        "n_trades": n_trades,
        "seed": seed,
        "_week_end_idx": week_end_idx,
        "_end_path_cents": b,  # alias
    }


def simulate_with_weekly(
    daily_n: list[int],
    day_dates: list[date],
    n_sim: int = N_SIM,
    seed: int = SEED,
    start_cents: int = B0_CENTS,
    probs: np.ndarray | None = None,
) -> dict:
    """Same as simulate_paths plus weekly bankroll percentiles."""
    p = mix_probs_604() if probs is None else probs
    taken = cap_daily_n(daily_n)
    n_trades = int(sum(taken))
    rng = np.random.default_rng(seed)
    draws = rng.choice(5, size=(n_sim, n_trades), p=p)
    pnl = PNL_TABLE[draws]
    b = np.full(n_sim, start_cents, dtype=np.int64)
    peak = b.copy()
    min_b = b.copy()
    max_dd_bp = np.zeros(n_sim, dtype=np.int64)
    daily_ret = np.zeros((n_sim, len(taken)), dtype=np.float64)
    week_keys = []
    week_labels = []
    seen = set()
    for d in day_dates:
        k = iso_week_key(d)
        if k not in seen:
            seen.add(k)
            week_keys.append(k)
            week_labels.append(f"{k[0]}-W{k[1]:02d}")
    weekly_b = np.zeros((n_sim, len(week_keys)), dtype=np.int64)
    week_pos = {k: i for i, k in enumerate(week_keys)}
    cursor = 0
    for t, n in enumerate(taken):
        prev = b.copy()
        if n > 0:
            contracts = (b * FRACTION_PCT // 100) // ENTRY_CENTS
            day_pnl_per = pnl[:, cursor : cursor + n].sum(axis=1)
            b = b + apply_conservative_edge(contracts * day_pnl_per)
            cursor += n
        daily_ret[:, t] = np.where(prev > 0, b.astype(np.float64) / prev.astype(np.float64) - 1.0, 0.0)
        min_b = np.minimum(min_b, b)
        peak = np.maximum(peak, b)
        dd = np.where(peak > 0, (peak - b) * 10000 // peak, 0)
        max_dd_bp = np.maximum(max_dd_bp, dd)
        weekly_b[:, week_pos[iso_week_key(day_dates[t])]] = b
    if cursor != n_trades:
        raise IdentityHalt(f"HALT cursor {cursor} != {n_trades}")
    return {
        "end_cents": b,
        "min_cents": min_b,
        "max_dd_bp": max_dd_bp,
        "daily_ret": daily_ret,
        "weekly_cents": weekly_b,
        "week_labels": week_labels,
        "n_sim": n_sim,
        "n_trades": n_trades,
        "seed": seed,
    }


def pctile(arr: np.ndarray, q: float) -> float:
    return float(np.quantile(arr.astype(np.float64), q))


def dollars(cents: float) -> float:
    return round(cents / 100.0, 2)


def sharpe_rows(daily_ret: np.ndarray, daily_n: list[int]) -> dict:
    """Per-path Sharpe, rf=0. Calendar includes off days. Trading-day drops zeros."""
    n_cal = daily_ret.shape[1]
    active = np.array([n > 0 for n in daily_n], dtype=bool)
    cal_mean = daily_ret.mean(axis=1)
    cal_std = daily_ret.std(axis=1, ddof=1)
    cal_sharpe_season = np.where(cal_std > 0, cal_mean / cal_std * math.sqrt(n_cal), 0.0)
    cal_sharpe_365 = np.where(cal_std > 0, cal_mean / cal_std * math.sqrt(365.0), 0.0)
    act = daily_ret[:, active]
    n_act = int(active.sum())
    act_mean = act.mean(axis=1)
    act_std = act.std(axis=1, ddof=1)
    act_sharpe_season = np.where(act_std > 0, act_mean / act_std * math.sqrt(n_act), 0.0)
    act_sharpe_252 = np.where(act_std > 0, act_mean / act_std * math.sqrt(252.0), 0.0)

    def pack(x: np.ndarray) -> dict:
        return {
            "p05": round(float(np.quantile(x, 0.05)), 4),
            "p25": round(float(np.quantile(x, 0.25)), 4),
            "p50": round(float(np.quantile(x, 0.50)), 4),
            "p75": round(float(np.quantile(x, 0.75)), 4),
            "p95": round(float(np.quantile(x, 0.95)), 4),
            "mean": round(float(x.mean()), 4),
        }

    return {
        "n_calendar_days": n_cal,
        "n_active_days": n_act,
        "rf": 0,
        "calendar_daily_return": pack(cal_mean),
        "calendar_daily_vol": pack(cal_std),
        "calendar_sharpe_season": pack(cal_sharpe_season),
        "calendar_sharpe_annualized_365": pack(cal_sharpe_365),
        "active_day_return": pack(act_mean),
        "active_day_vol": pack(act_std),
        "active_sharpe_season": pack(act_sharpe_season),
        "active_sharpe_annualized_252": pack(act_sharpe_252),
    }


def risk_of_ruin(end: np.ndarray, min_b: np.ndarray, max_dd_bp: np.ndarray, start: int) -> dict:
    n = len(end)
    return {
        "definition": (
            "Each bet is 5% of SOD bankroll. Day cap is 6 bets / 30%. "
            "Worst taken-out is −87.5% of a bet (10¢ slip on the 40 "
            "signal) = 4.375% of SOD per bet, 26.25% of SOD if all 6 "
            "max-slip. B=0 is not reachable in this window. Ruin is "
            "start-relative and peak-to-trough — not classical "
            "gambler's ruin."
        ),
        "p_end_below_start": round(float((end < start).mean()), 4),
        "p_end_below_75pct_start": round(float((end < start * 75 // 100).mean()), 4),
        "p_end_below_50pct_start": round(float((end < start * 50 // 100).mean()), 4),
        "p_touch_75pct_start": round(float((min_b < start * 75 // 100).mean()), 4),
        "p_touch_50pct_start": round(float((min_b < start * 50 // 100).mean()), 4),
        "p_touch_25pct_start": round(float((min_b < start * 25 // 100).mean()), 4),
        "p_peak_dd_ge_20pct": round(float((max_dd_bp >= 2000).mean()), 4),
        "p_peak_dd_ge_35pct": round(float((max_dd_bp >= 3500).mean()), 4),
        "p_peak_dd_ge_50pct": round(float((max_dd_bp >= 5000).mean()), 4),
        "median_max_dd_pct": round(float(np.median(max_dd_bp)) / 100.0, 2),
        "p95_max_dd_pct": round(float(np.quantile(max_dd_bp, 0.95)) / 100.0, 2),
        "n_paths": n,
    }


def terminal_distribution(end: np.ndarray, start: int) -> dict:
    qs = (0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99)
    return {
        "start_dollars": dollars(start),
        "mean_dollars": dollars(float(end.mean())),
        "std_dollars": dollars(float(end.std(ddof=1))),
        "percentiles_dollars": {f"p{int(q*100):02d}": dollars(pctile(end, q)) for q in qs},
        "mean_multiple": round(float(end.mean()) / start, 4),
        "median_multiple": round(float(np.median(end)) / start, 4),
    }


def weekly_fan(weekly_cents: np.ndarray, labels: list[str], start: int) -> dict:
    return {
        "labels": labels,
        "start_dollars": dollars(start),
        "p05": [dollars(pctile(weekly_cents[:, i], 0.05)) for i in range(weekly_cents.shape[1])],
        "p25": [dollars(pctile(weekly_cents[:, i], 0.25)) for i in range(weekly_cents.shape[1])],
        "p50": [dollars(pctile(weekly_cents[:, i], 0.50)) for i in range(weekly_cents.shape[1])],
        "p75": [dollars(pctile(weekly_cents[:, i], 0.75)) for i in range(weekly_cents.shape[1])],
        "p95": [dollars(pctile(weekly_cents[:, i], 0.95)) for i in range(weekly_cents.shape[1])],
    }


def histogram_dollars(end: np.ndarray, lo: int, hi: int, step: int) -> dict:
    """Inclusive [lo, hi) bins in dollars, plus below/above tails."""
    d = end.astype(np.float64) / 100.0
    edges = list(range(lo, hi + step, step))
    labels = []
    counts = []
    for a, b in zip(edges[:-1], edges[1:]):
        labels.append(f"${a//1000}k–${b//1000}k")
        counts.append(int(((d >= a) & (d < b)).sum()))
    below = int((d < lo).sum())
    above = int((d >= hi).sum())
    return {
        "bin_labels": [f"<{lo//1000}k"] + labels + [f"≥{hi//1000}k"],
        "counts": [below] + counts + [above],
        "n": int(len(end)),
    }


def analyze(n_sim: int = N_SIM, seed: int = SEED) -> dict:
    rows = window_rows()
    arrival = arrival_from_window(rows)
    daily_n = arrival["daily_n"]
    days = [date.fromisoformat(s) for s in arrival["days"]]
    probs = mix_probs_604()
    raw_edge = expected_debit_return_pct(probs)
    if abs(raw_edge - 3.4189) > 0.002:
        raise IdentityHalt(f"HALT raw edge {raw_edge}")
    sim = simulate_with_weekly(daily_n, days, n_sim=n_sim, seed=seed)
    naive = naive_3pct_end_cents(daily_n)
    taken = cap_daily_n(daily_n)
    end = sim["end_cents"]
    return {
        "written_utc": utc_now(),
        "research_only": True,
        "live_execution_changed": False,
        "assumption": (
            "2026-27 Nov 1–Apr 11 uses the 2025-26 Nov 1–Apr 12 regular-season "
            "Q2+Q3 FIRST80 daily occurrence vector (508 prints / 24 ISO weeks). "
            "Each *bet* debits 5% of start-of-day bankroll — not 5% per day. "
            "Hard cap 6 bets / 30% SOD (9 overflow prints dropped → 499 taken). "
            "Exit SIGNAL is still first close-path 40 — adverse fills are "
            "still T40 trades. 20¢/10¢ are slippage take-outs on that 40, "
            "not a 20-stop or 10-stop. Losers: 50% fill 40 / 30% slip 20 / "
            "20% slip 10 (raw mix +3.419% of debit). Winner-touches stay "
            "−40¢ (no slip). P&L haircut locks expected debit return at "
            "3.000%, not 3.214% and not 3.419%. Zero fee. MODELED — not a "
            "fill, not live."
        ),
        "projection": {
            "season": "2026-27",
            "user_window": "Nov–Apr",
            "official_rs": "2026-10-20 to 2027-04-11",
            "sim_window": f"{PROJECT_START.isoformat()} to {PROJECT_END.isoformat()}",
            "analog_window": f"{WINDOW_START.isoformat()} to {WINDOW_END.isoformat()}",
            "analog_reason": (
                "2025-26 regular season ended Sunday Apr 12; 2026-27 ends "
                "Sunday Apr 11. Same 82-game season. October and playoffs "
                "excluded because the request is Nov–Apr."
            ),
            "n_prints": arrival["n_trades"],
            "n_trades_taken": arrival["n_trades_capped"],
            "n_dropped_over_cap": arrival["n_dropped_over_cap"],
            "n_iso_weeks": arrival["n_iso_weeks"],
            "prints_per_week_mean": arrival["trades_per_week_mean"],
            "trades_per_week_mean": arrival["trades_per_week_capped_mean"],
            "trades_per_week_min": arrival["trades_per_week_capped_min"],
            "trades_per_week_max": arrival["trades_per_week_capped_max"],
            "n_active_days": arrival["n_active_days"],
            "max_same_day_prints": arrival["max_same_day"],
            "max_same_day_traded": arrival["max_same_day_traded"],
            "max_same_day_notional_pct_of_bankroll": MAX_DAY_FRACTION_PCT,
            "excluded_october_rs_q23": 42,
            "excluded_playoffs_q23": 21,
        },
        "sizing": {
            "start_bankroll_dollars": 20000.0,
            "fraction_of_bankroll_per_bet": 0.05,
            "max_bets_per_day": MAX_TRADES_PER_DAY,
            "max_day_fraction_of_bankroll": 0.30,
            "entry_cents": ENTRY_CENTS,
            "start_contracts_per_bet": contracts_from_bankroll_cents(B0_CENTS),
            "compound": "daily_start_of_day",
            "overflow_rule": "first_6_by_first_80_timestamp",
            "integer_contracts": True,
            "integer_cents": True,
            "fee": 0,
        },
        "edge": {
            "exit_signal": "FIRST_CLOSE_PATH_40",
            "adverse_fill_still_counted_at_40": True,
            "slippage_is_fill_only": True,
            "stated_by_user": "conservative 3% return on trades",
            "raw_50_30_20_mix_pct_of_debit": round(raw_edge, 4),
            "conservative_locked_pct_of_debit": CONSERVATIVE_DEBIT_RETURN_PCT,
            "naive_constant_pct": NAIVE_DEBIT_RETURN_PCT,
            "survive_pnl_cents": int(PNL_SURVIVE),
            "winner_touch_pnl_cents": int(PNL_WTOUCH),
            "loser_mix_pnl_cents": loser_mix_pnl_cents(),
            "loser_fill_weights": {
                "at_40": LOSE_AT_40_WGT,
                "slip_20": LOSE_AT_20_WGT,
                "slip_10": LOSE_AT_10_WGT,
            },
            "class_source": "frozen 2Q+3Q n=604 classes; 50/30/20 loser fills; 3.000% edge haircut",
            "probs": {
                "survive": round(float(probs[0]), 6),
                "winner_touch": round(float(probs[1]), 6),
                "lose_40": round(float(probs[2]), 6),
                "lose_20": round(float(probs[3]), 6),
                "lose_10": round(float(probs[4]), 6),
            },
        },
        "arrival": arrival,
        "simulation": {
            "n_sim": n_sim,
            "seed": seed,
            "engine": "iid_5class_t40_signal_503020_slip_3pct_edge_5pct_bet_cap6",
        },
        "naive_3pct_end_dollars": dollars(naive),
        "naive_3pct_multiple": round(naive / B0_CENTS, 4),
        "terminal": terminal_distribution(end, B0_CENTS),
        "risk_of_ruin": risk_of_ruin(end, sim["min_cents"], sim["max_dd_bp"], B0_CENTS),
        "sharpe": sharpe_rows(sim["daily_ret"], taken),
        "weekly_fan": weekly_fan(sim["weekly_cents"], sim["week_labels"], B0_CENTS),
        "histogram_end_dollars": histogram_dollars(end, 10000, 80000, 5000),
        "variance": {
            "per_trade_debit_return_std_pct": round(
                float(
                    np.sqrt(
                        probs
                        @ (PNL_TABLE.astype(np.float64) * EDGE_SCALE_NUM / EDGE_SCALE_DEN / ENTRY_CENTS)
                        ** 2
                        - (CONSERVATIVE_DEBIT_RETURN_PCT / 100.0) ** 2
                    )
                )
                * 100.0,
                2,
            ),
            "terminal_std_dollars": dollars(float(end.std(ddof=1))),
            "terminal_iqr_dollars": [
                dollars(pctile(end, 0.25)),
                dollars(pctile(end, 0.75)),
            ],
        },
    }


def write_outputs(summary: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    t = summary["terminal"]["percentiles_dollars"]
    print("wrote", OUT / "summary.json")
    print(
        "taken",
        summary["projection"]["n_trades_taken"],
        "per week",
        summary["projection"]["trades_per_week_mean"],
        "naive3",
        summary["naive_3pct_end_dollars"],
        "median",
        t["p50"],
        "p05",
        t["p05"],
        "p95",
        t["p95"],
        "P(end<start)",
        summary["risk_of_ruin"]["p_end_below_start"],
        "P(50% start)",
        summary["risk_of_ruin"]["p_touch_50pct_start"],
        "sharpe252 p50",
        summary["sharpe"]["active_sharpe_annualized_252"]["p50"],
    )


def main() -> int:
    write_outputs(analyze())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
