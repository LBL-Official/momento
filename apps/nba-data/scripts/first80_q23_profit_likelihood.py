#!/usr/bin/env python3
"""Realistic P(season EV>0) for 2Q+3Q FIRST80 — research only.

The iid binomial table treated last year's P(¬T40) as a known rate
and 499 trades as independent coins. That is not a 2026-27 forecast.

Realistic DGP (still zero fee, still candle path, still not a fill):

1. Season = 24 ISO-week remix of 2025-26 Nov 1–Apr 12 (observed week
   sizes; variable n, mean 508).
2. Week shocks = observed Nov–Apr week P(¬T40) residuals, recentered
   on the scenario mean and clipped to [2%, 98%]. Week 50 printed
   5/11 = 45.5% — that crash is in the residual library.
3. Persist mean is unknown: p* ~ Beta(450, 154) from the frozen 604
   2Q+3Q book. World A and December are hypothesized known means.
4. L∩¬T40 stays 0. T40 splits winner-touch vs loser with scenario
   P(WT|T40). Persist also draws q ~ Beta(55, 99).
5. Each loser independently fills 50/30/20 on the 40 signal
   (−40 / −60 / −70). Not a −52 expected-mix threshold.
6. Clean book: every T40 at −40. Slip book: random fills.
7. Profit = sum of per-contract P&L > 0 (equal weight). This is not
   the 5%/bet bankroll path and not P(end > $20k).

Does not change live FIRST01. Does not invent L2 or fees.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first80_q23_novapr_portfolio_sim as P  # noqa: E402
import first80_quarter_barrier_survival as Q  # noqa: E402

OUT = Q.OUT.parent / "first80_q23_profit_likelihood"

# Frozen 2Q+3Q FIRST80 book (full tape, not Nov–Apr).
BOOK_N = 604
BOOK_SURVIVE = 450
BOOK_WTOUCH = 55
BOOK_LOSE = 99
BOOK_T40 = BOOK_WTOUCH + BOOK_LOSE  # 154

# December 2025 2Q+3Q four-cell (locked).
DEC_N = 85
DEC_SURVIVE = 56
DEC_WTOUCH = 11
DEC_LOSE = 18

# Nov–Apr analog (locked by portfolio sim).
WINDOW_N = 508
WINDOW_SURVIVE = 384
WINDOW_WTOUCH = 44
WINDOW_LOSE = 80
WINDOW_WEEKS = 24
WEEK50_N = 11
WEEK50_SURVIVE = 5

NAIVE_N = 499  # taken after 6/day cap on the analog calendar
N_SIM = 20_000
SEED = 20260905
P_CLIP = (0.02, 0.98)

PNL_SURVIVE = Q.WIN_PNL_CENTS  # +20
PNL_T40_CLEAN = 40 - Q.ENTRY_CENTS  # −40
PNL_L40 = 40 - Q.ENTRY_CENTS  # −40
PNL_L20 = 20 - Q.ENTRY_CENTS  # −60
PNL_L10 = 10 - Q.ENTRY_CENTS  # −70
LOSE_P40 = 0.50
LOSE_P20_GIVEN_NOT40 = 0.60  # 30/50 of the remainder → 20; else 10

# World A: hold P(¬T40|W)=450/505 and P(T40|L)=1; P(W)=0.75.
P_BAR_WORLD_A = 0.75 * BOOK_SURVIVE / 505  # 66.8317...%
Q_WT_WORLD_A = (0.75 * BOOK_WTOUCH / 505) / (1.0 - P_BAR_WORLD_A)
P_BAR_DEC = DEC_SURVIVE / DEC_N
Q_WT_DEC = DEC_WTOUCH / (DEC_WTOUCH + DEC_LOSE)
P_BAR_BOOK = BOOK_SURVIVE / BOOK_N
Q_WT_BOOK = BOOK_WTOUCH / BOOK_T40

CLEAN_BE = 2.0 / 3.0  # EV = 60p − 40 = 0
# 50/30/20 expected loser = −52. Survive +20. T40 mix from 604 book:
# EV = 20p + (−40)(1−p)*q_wt/(1 wait)
# Clean: 20p − 40(1−p) = 60p − 40.
# Slip with L∩¬T40=0: T40 = 1−p; among T40, q = P(WT|T40), rest losers at −52.
# EV = 20p − 40*q*(1−p) − 52*(1−q)*(1−p)
# Persist q = 55/154. Set EV=0 → p_be depends on q.


class IdentityHalt(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slip_breakeven_p(q_wt_given_t40: float) -> float:
    """P(¬T40) that zeros expected slip EV when L∩¬T40=0.

    EV = 20p + [−40 q − 52 (1−q)] (1−p) = 0
    20p + (−40q − 52 + 52q)(1−p) = 0
    20p + (12q − 52)(1−p) = 0
    """
    t40_pnl = -40.0 * q_wt_given_t40 - 52.0 * (1.0 - q_wt_given_t40)
    # 20p + t40_pnl (1-p) = 0 → 20p + t40_pnl − t40_pnl p = 0
    # p (20 − t40_pnl) = −t40_pnl
    return -t40_pnl / (20.0 - t40_pnl)


def week_blocks(rows: list[dict] | None = None) -> dict:
    rows = rows if rows is not None else P.window_rows()
    if len(rows) != WINDOW_N:
        raise IdentityHalt(f"HALT window n={len(rows)}")
    by_week: dict[tuple[int, int], list[dict]] = {}
    for r in rows:
        key = P.iso_week_key(P.game_date_of(r))
        by_week.setdefault(key, []).append(r)
    if len(by_week) != WINDOW_WEEKS:
        raise IdentityHalt(f"HALT weeks={len(by_week)}")
    keys = sorted(by_week)
    n = np.array([len(by_week[k]) for k in keys], dtype=np.int64)
    survive = np.array(
        [sum(1 for r in by_week[k] if r["W"] and not r["T40"]) for k in keys],
        dtype=np.int64,
    )
    wtouch = np.array(
        [sum(1 for r in by_week[k] if r["W"] and r["T40"]) for k in keys],
        dtype=np.int64,
    )
    lose = n - survive - wtouch
    if int(survive.sum()) != WINDOW_SURVIVE:
        raise IdentityHalt(f"HALT window survive {int(survive.sum())}")
    if int(wtouch.sum()) != WINDOW_WTOUCH or int(lose.sum()) != WINDOW_LOSE:
        raise IdentityHalt("HALT window T40 mix")
    week50 = next(k for k in keys if k == (2025, 50))
    i50 = keys.index(week50)
    if int(n[i50]) != WEEK50_N or int(survive[i50]) != WEEK50_SURVIVE:
        raise IdentityHalt("HALT week 50")
    p_week = survive / n.astype(np.float64)
    p_season = float(survive.sum() / n.sum())
    return {
        "keys": keys,
        "n": n,
        "survive": survive,
        "wtouch": wtouch,
        "lose": lose,
        "p_week": p_week,
        "p_season": p_season,
        "week50_p": float(survive[i50] / n[i50]),
    }


def _fill_losers(rng: np.random.Generator, n_lose: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n_lose = n_lose.astype(np.int64)
    n_l40 = rng.binomial(n_lose, LOSE_P40)
    n_l20 = rng.binomial(n_lose - n_l40, LOSE_P20_GIVEN_NOT40)
    n_l10 = n_lose - n_l40 - n_l20
    return n_l40, n_l20, n_l10


def _season_stats(
    n_survive: np.ndarray,
    n_wtouch: np.ndarray,
    n_lose: np.ndarray,
    n_l40: np.ndarray,
    n_l20: np.ndarray,
    n_l10: np.ndarray,
) -> dict:
    n = n_survive + n_wtouch + n_lose
    clean = n_survive * PNL_SURVIVE + (n_wtouch + n_lose) * PNL_T40_CLEAN
    slip = (
        n_survive * PNL_SURVIVE
        + n_wtouch * PNL_T40_CLEAN
        + n_l40 * PNL_L40
        + n_l20 * PNL_L20
        + n_l10 * PNL_L10
    )
    p_bar = n_survive / n.astype(np.float64)
    ev_clean = clean / n.astype(np.float64)
    ev_slip = slip / n.astype(np.float64)
    return {
        "n_mean": float(n.mean()),
        "p_bar_mean": float(p_bar.mean()),
        "p_bar_p05": float(np.quantile(p_bar, 0.05)),
        "p_bar_p50": float(np.median(p_bar)),
        "p_bar_p95": float(np.quantile(p_bar, 0.95)),
        "p_clean_gt0": float((clean > 0).mean()),
        "p_slip_gt0": float((slip > 0).mean()),
        "p_clean_ge0": float((clean >= 0).mean()),
        "p_slip_ge0": float((slip >= 0).mean()),
        "ev_clean_p50": float(np.median(ev_clean)),
        "ev_slip_p50": float(np.median(ev_slip)),
        "ev_slip_p05": float(np.quantile(ev_slip, 0.05)),
        "ev_slip_p95": float(np.quantile(ev_slip, 0.95)),
    }


def sim_naive_iid(
    p_bar: float,
    q_wt: float,
    n_trades: int = NAIVE_N,
    n_sim: int = N_SIM,
    seed: int = SEED,
) -> dict:
    """Known rate, iid trades, random 50/30/20 fills. Old-table DGP."""
    rng = np.random.default_rng(seed)
    p_s = p_bar
    p_wt = (1.0 - p_bar) * q_wt
    p_l = 1.0 - p_s - p_wt
    if p_l < -1e-12:
        raise IdentityHalt("HALT naive probs")
    counts = rng.multinomial(n_trades, [p_s, max(p_wt, 0.0), max(p_l, 0.0)], size=n_sim)
    n_l40, n_l20, n_l10 = _fill_losers(rng, counts[:, 2])
    stats = _season_stats(counts[:, 0], counts[:, 1], counts[:, 2], n_l40, n_l20, n_l10)
    stats["dgp"] = "naive_iid_known_p"
    stats["n_trades"] = n_trades
    stats["p_bar_assumed"] = p_bar
    stats["q_wt_assumed"] = q_wt
    return stats


def sim_realistic(
    *,
    p_mean: float | None,
    q_mean: float,
    unknown_p: bool,
    unknown_q: bool,
    weeks: dict,
    n_sim: int = N_SIM,
    seed: int = SEED,
    p_alpha: tuple[int, int] | None = None,
    q_alpha: tuple[int, int] | None = None,
) -> dict:
    """Week-residual remix. Persist draws p* and q* from the book alphas."""
    rng = np.random.default_rng(seed)
    n_w = weeks["n"]
    p_w_hist = weeks["p_week"]
    p_season = weeks["p_season"]
    n_weeks = len(n_w)
    idx = rng.integers(0, n_weeks, size=(n_sim, n_weeks))
    n_block = n_w[idx]
    resid = p_w_hist[idx] - p_season
    if unknown_p:
        a_p, b_p = p_alpha if p_alpha is not None else (BOOK_SURVIVE, BOOK_LOSE + BOOK_WTOUCH)
        p_star = rng.beta(a_p, b_p, size=n_sim)
    else:
        if p_mean is None:
            raise IdentityHalt("HALT p_mean required")
        p_star = np.full(n_sim, p_mean, dtype=np.float64)
    p_draw = np.clip(p_star[:, None] + resid, P_CLIP[0], P_CLIP[1])
    n_survive_w = rng.binomial(n_block, p_draw)
    n_t40_w = n_block - n_survive_w
    if unknown_q:
        a_q, b_q = q_alpha if q_alpha is not None else (BOOK_WTOUCH, BOOK_LOSE)
        q_star = rng.beta(a_q, b_q, size=n_sim)
    else:
        q_star = np.full(n_sim, q_mean, dtype=np.float64)
    n_wt_w = rng.binomial(n_t40_w, q_star[:, None])
    n_lose_w = n_t40_w - n_wt_w
    n_survive = n_survive_w.sum(axis=1)
    n_wtouch = n_wt_w.sum(axis=1)
    n_lose = n_lose_w.sum(axis=1)
    n_l40, n_l20, n_l10 = _fill_losers(rng, n_lose)
    stats = _season_stats(n_survive, n_wtouch, n_lose, n_l40, n_l20, n_l10)
    stats["dgp"] = "week_residual_remix"
    stats["unknown_p"] = unknown_p
    stats["unknown_q"] = unknown_q
    stats["p_mean_input"] = None if unknown_p else p_mean
    stats["q_mean_input"] = q_mean
    stats["p_star_mean"] = float(p_star.mean())
    stats["n_weeks"] = n_weeks
    return stats


def pct(x: float, digits: int = 1) -> float:
    return round(100.0 * x, digits)


def analyze(n_sim: int = N_SIM, seed: int = SEED) -> dict:
    if BOOK_SURVIVE + BOOK_WTOUCH + BOOK_LOSE != BOOK_N:
        raise IdentityHalt("HALT 604 book")
    if DEC_SURVIVE + DEC_WTOUCH + DEC_LOSE != DEC_N:
        raise IdentityHalt("HALT December book")
    weeks = week_blocks()
    persist_naive = sim_naive_iid(P_BAR_BOOK, Q_WT_BOOK, n_sim=n_sim, seed=seed)
    world_a_naive = sim_naive_iid(P_BAR_WORLD_A, Q_WT_WORLD_A, n_sim=n_sim, seed=seed + 1)
    dec_naive = sim_naive_iid(P_BAR_DEC, Q_WT_DEC, n_sim=n_sim, seed=seed + 2)
    persist_real = sim_realistic(
        p_mean=None,
        q_mean=Q_WT_BOOK,
        unknown_p=True,
        unknown_q=True,
        weeks=weeks,
        n_sim=n_sim,
        seed=seed + 10,
    )
    world_a_real = sim_realistic(
        p_mean=P_BAR_WORLD_A,
        q_mean=Q_WT_WORLD_A,
        unknown_p=False,
        unknown_q=False,
        weeks=weeks,
        n_sim=n_sim,
        seed=seed + 11,
    )
    dec_real = sim_realistic(
        p_mean=P_BAR_DEC,
        q_mean=Q_WT_DEC,
        unknown_p=False,
        unknown_q=False,
        weeks=weeks,
        n_sim=n_sim,
        seed=seed + 12,
    )
    return {
        "generated_at": utc_now(),
        "research_only": True,
        "live_first01_unchanged": True,
        "fee_cents": 0,
        "l2": "UNAVAILABLE",
        "n_sim": n_sim,
        "seed": seed,
        "identities": {
            "book_2q3q": {
                "n": BOOK_N,
                "survive": BOOK_SURVIVE,
                "wtouch": BOOK_WTOUCH,
                "lose": BOOK_LOSE,
                "p_bar": P_BAR_BOOK,
                "q_wt": Q_WT_BOOK,
            },
            "nov_apr": {
                "n": WINDOW_N,
                "survive": WINDOW_SURVIVE,
                "wtouch": WINDOW_WTOUCH,
                "lose": WINDOW_LOSE,
                "weeks": WINDOW_WEEKS,
                "p_bar": weeks["p_season"],
                "week50_p": weeks["week50_p"],
            },
            "december": {
                "n": DEC_N,
                "survive": DEC_SURVIVE,
                "wtouch": DEC_WTOUCH,
                "lose": DEC_LOSE,
                "p_bar": P_BAR_DEC,
                "q_wt": Q_WT_DEC,
            },
            "world_a": {
                "p_term": 0.75,
                "p_bar": P_BAR_WORLD_A,
                "q_wt": Q_WT_WORLD_A,
                "path_conditionals": "P(¬T40|W)=450/505, P(T40|L)=1",
            },
        },
        "hurdles": {
            "clean_be_p_bar": CLEAN_BE,
            "slip_be_p_bar_book_q": slip_breakeven_p(Q_WT_BOOK),
            "slip_be_p_bar_world_a_q": slip_breakeven_p(Q_WT_WORLD_A),
            "slip_be_p_bar_dec_q": slip_breakeven_p(Q_WT_DEC),
            "note": (
                "Clean 40 breaks even at 2/3. Slip breakeven moves with "
                "P(WT|T40) because winner-touches stay −40 and losers are −52."
            ),
        },
        "naive_iid": {
            "n": NAIVE_N,
            "persist_7450": persist_naive,
            "world_a_6683": world_a_naive,
            "december_6588": dec_naive,
        },
        "realistic": {
            "persist_unknown_p": persist_real,
            "world_a_known_mean": world_a_real,
            "december_known_mean": dec_real,
        },
        "table": [
            {
                "world": "74.50% last-year 2Q+3Q",
                "mean_p_bar": P_BAR_BOOK,
                "naive_p_clean": persist_naive["p_clean_gt0"],
                "naive_p_slip": persist_naive["p_slip_gt0"],
                "realistic_p_clean": persist_real["p_clean_gt0"],
                "realistic_p_slip": persist_real["p_slip_gt0"],
                "realistic_what_is_random": (
                    "p* ~ Beta(450,154), q* ~ Beta(55,99), 24-week residual "
                    "remix, random 50/30/20 fills"
                ),
            },
            {
                "world": "66.83% World A",
                "mean_p_bar": P_BAR_WORLD_A,
                "naive_p_clean": world_a_naive["p_clean_gt0"],
                "naive_p_slip": world_a_naive["p_slip_gt0"],
                "realistic_p_clean": world_a_real["p_clean_gt0"],
                "realistic_p_slip": world_a_real["p_slip_gt0"],
                "realistic_what_is_random": (
                    "mean locked at World A; week residuals + random fills. "
                    "Not a posterior — a hypothesized true mean."
                ),
            },
            {
                "world": "65.88% December",
                "mean_p_bar": P_BAR_DEC,
                "naive_p_clean": dec_naive["p_clean_gt0"],
                "naive_p_slip": dec_naive["p_slip_gt0"],
                "realistic_p_clean": dec_real["p_clean_gt0"],
                "realistic_p_slip": dec_real["p_slip_gt0"],
                "realistic_what_is_random": (
                    "mean locked at December 56/85; week residuals + random "
                    "fills. December is not treated as a 85-trade posterior."
                ),
            },
        ],
        "do_not": [
            "Do not average the three worlds into one P(profit).",
            "Do not treat 98% as how likely the strategy makes money.",
            "Do not treat these as after-fee probabilities.",
            "Do not change live FIRST01 from this table.",
        ],
    }


def write_summary(summary: dict) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "summary.json"
    path.write_text(json.dumps(summary, indent=2) + "\n")
    return path


def main() -> None:
    summary = analyze()
    path = write_summary(summary)
    print(json.dumps({"wrote": str(path), "table": summary["table"]}, indent=2))


if __name__ == "__main__":
    main()
