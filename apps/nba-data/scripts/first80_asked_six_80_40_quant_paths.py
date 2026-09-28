#!/usr/bin/env python3
"""Asked-six FIRST80 80/40 path / bankroll distribution (research only).

Universe is the frozen 1,182-row ledger, not 3,000 games.
Outcome is win_80_40 (buy 80 / close-path stop 40), not terminal W.

```
RESEARCH ONLY
CANDLE PATH ≠ ACTUAL FILL
LIVE EXECUTION = FALSE
DO NOT USE FULL BOOK TO BOTH PROVE EDGE AND FIT RISK
```

Integer cents. Stake = f% of week-start bankroll. Contracts = stake // 80.
Weekly P&L = qty * (20*K − 40*(10−K)). Same economics as
R = f*(0.25K − 0.50*(10−K)).
"""

from __future__ import annotations

import csv
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first80_asked_six_chatgpt_export as E  # noqa: E402

REPO = Path("/Users/user/Desktop/Momento")
LEDGER = E.OUT / "first80_asked_six.csv"
OUT = REPO / "research" / "first80_asked_six_80_40_quant_paths"
WH_OUT = E.WH_OUT.parent / "first80_asked_six_80_40_quant_paths"

EXPECTED_N = 1182
EXPECTED_WIN = 883
EXPECTED_STOP = 299
B0_CENTS = 2_000_000
ENTRY_CENTS = 80
WIN_PNL = 20
STOP_PNL = -40
TRADES_PER_WEEK = 10
WEEKS = 22
FRACTION_HEADLINE = 5
SIZES = (2, 3, 4, 5, 6, 7, 8, 10)
TRUE_P = (0.667, 0.68, 0.70, 0.72, 0.747, 0.76)
BLOCK_LENS = (5, 10, 20)
N_WEEK = 200_000
N_SEASON = 100_000
N_GRID = 40_000
SEED = 20260910
BREAKEVEN = 2.0 / 3.0


class IdentityHalt(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def wilson(k: int, n: int, z: float = 1.96):
    if n <= 0:
        return None, None, None
    p = k / n
    z2 = z * z
    den = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / den
    rad = z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n) / den
    return (
        round(p * 100, 4),
        round(max(0.0, center - rad) * 100, 4),
        round(min(1.0, center + rad) * 100, 4),
    )


def rate(k, n):
    if not n:
        return None
    return round(100.0 * k / n, 4)


def qty_from_bankroll(b_cents: int, f_pct: int) -> int:
    if b_cents <= 0 or f_pct <= 0:
        return 0
    return (b_cents * f_pct // 100) // ENTRY_CENTS


def week_pnl_cents(k_wins: int, b_cents: int, f_pct: int) -> int:
    """10 trades, same SOD size. Integer contracts. Not a fill."""
    k = int(k_wins)
    if k < 0 or k > TRADES_PER_WEEK:
        raise ValueError(k)
    qty = qty_from_bankroll(int(b_cents), int(f_pct))
    return qty * (WIN_PNL * k + STOP_PNL * (TRADES_PER_WEEK - k))


def week_return_frac(k_wins: int, f_pct: int) -> float:
    """ChatGPT R_week = f*(0.25K − 0.50*(10−K)). Reporting only."""
    k = int(k_wins)
    f = int(f_pct) / 100.0
    return f * (0.25 * k - 0.50 * (TRADES_PER_WEEK - k))


def longest_run(bits: np.ndarray, val: int) -> int:
    best = cur = 0
    for x in bits:
        if int(x) == val:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def as_bool(v) -> bool:
    return str(v).strip() in {"True", "true", "1"}


def as_float(v):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load_ledger(path: Path | None = None) -> list[dict]:
    rows = E.load_existing_csv(path or LEDGER)
    if len(rows) != EXPECTED_N:
        raise IdentityHalt(f"HALT n={len(rows)} expected {EXPECTED_N}")
    wins = sum(1 for r in rows if as_bool(r.get("win_80_40")))
    stops = sum(1 for r in rows if as_bool(r.get("stopped_40")))
    if wins != EXPECTED_WIN or stops != EXPECTED_STOP:
        raise IdentityHalt(f"HALT 80/40 {wins}/{stops}")
    return rows


def outcomes_of(rows: list[dict]) -> np.ndarray:
    return np.array([1 if as_bool(r.get("win_80_40")) else 0 for r in rows], dtype=np.int8)


def bought_pregame(r: dict):
    side = r.get("side")
    if side == "home":
        return as_float(r.get("pregame_home_win_prob"))
    if side == "away":
        return as_float(r.get("pregame_away_win_prob"))
    return None


def entry_bucket(p) -> str:
    if p is None:
        return "UNKNOWN"
    if p < 0.805:
        return "P80"
    if p < 0.83:
        return "P81_82"
    if p < 0.86:
        return "P83_85"
    return "P86P"


def fav_bucket(p) -> str:
    if p is None:
        return "UNKNOWN"
    if p > 0.5:
        return "PREGAME_FAVORITE"
    if p < 0.5:
        return "PREGAME_UNDERDOG"
    return "PREGAME_PICKEM"


def pctile(xs: np.ndarray, q: float) -> float:
    return float(np.quantile(xs, q))


def dist_summary(ending_cents: np.ndarray, max_dd_frac: np.ndarray, min_cents: np.ndarray) -> dict:
    b0 = float(B0_CENTS)
    ret = ending_cents.astype(np.float64) / b0 - 1.0
    return {
        "n": int(len(ending_cents)),
        "mean_end_cents": int(round(float(ending_cents.mean()))),
        "median_end_cents": int(np.median(ending_cents)),
        "p05_end_cents": int(np.quantile(ending_cents, 0.05)),
        "p10_end_cents": int(np.quantile(ending_cents, 0.10)),
        "p25_end_cents": int(np.quantile(ending_cents, 0.25)),
        "p50_end_cents": int(np.quantile(ending_cents, 0.50)),
        "p75_end_cents": int(np.quantile(ending_cents, 0.75)),
        "p90_end_cents": int(np.quantile(ending_cents, 0.90)),
        "p95_end_cents": int(np.quantile(ending_cents, 0.95)),
        "mean_return": round(float(ret.mean()) * 100, 4),
        "median_return": round(float(np.median(ret)) * 100, 4),
        "p05_return": round(float(np.quantile(ret, 0.05)) * 100, 4),
        "p95_return": round(float(np.quantile(ret, 0.95)) * 100, 4),
        "sd_return": round(float(ret.std(ddof=1)) * 100, 4),
        "prob_lose": round(float((ending_cents < B0_CENTS).mean()) * 100, 4),
        "prob_loss_5": round(float((ret <= -0.05).mean()) * 100, 4),
        "prob_loss_10": round(float((ret <= -0.10).mean()) * 100, 4),
        "prob_loss_20": round(float((ret <= -0.20).mean()) * 100, 4),
        "prob_loss_30": round(float((ret <= -0.30).mean()) * 100, 4),
        "prob_gain_10": round(float((ret >= 0.10).mean()) * 100, 4),
        "median_max_dd": round(float(np.median(max_dd_frac)) * 100, 4),
        "p95_max_dd": round(float(np.quantile(max_dd_frac, 0.95)) * 100, 4),
        "worst_max_dd": round(float(max_dd_frac.max()) * 100, 4),
        "median_min_bankroll_cents": int(np.median(min_cents)),
        "p05_min_bankroll_cents": int(np.quantile(min_cents, 0.05)),
        "prob_below_start": round(float((ending_cents < B0_CENTS).mean()) * 100, 4),
        "prob_ruin": round(float((ending_cents < ENTRY_CENTS).mean()) * 100, 4),
        "label": "INTEGER CENTS — CANDLE PATH — NOT A FILL — ZERO FEE",
    }


def apply_weeks(k_wins: np.ndarray, f_pct: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """k_wins shape (n_sim, n_weeks). Same SOD size inside a week, then compound."""
    n, w = k_wins.shape
    end = np.empty(n, dtype=np.int64)
    dd = np.empty(n, dtype=np.float64)
    mn = np.empty(n, dtype=np.int64)
    for i in range(n):
        b = B0_CENTS
        peak = b
        min_b = b
        max_dd = 0
        for j in range(w):
            pnl = week_pnl_cents(int(k_wins[i, j]), b, f_pct)
            b = b + pnl
            if b < 0:
                b = 0
            if b > peak:
                peak = b
            gap = peak - b
            if gap > max_dd:
                max_dd = gap
            if b < min_b:
                min_b = b
            if b < ENTRY_CENTS:
                break
        end[i] = b
        mn[i] = min_b
        dd[i] = 0.0 if peak <= 0 else max_dd / peak
    return end, dd, mn


def iid_weeks(rng: np.random.Generator, wins: np.ndarray, n_sim: int, n_weeks: int) -> np.ndarray:
    draws = rng.choice(wins, size=(n_sim, n_weeks, TRADES_PER_WEEK), replace=True)
    return draws.sum(axis=2)


def permute_weeks(rng: np.random.Generator, wins: np.ndarray, n_sim: int, n_weeks: int) -> np.ndarray:
    need = n_weeks * TRADES_PER_WEEK
    out = np.empty((n_sim, n_weeks), dtype=np.int16)
    n = len(wins)
    for i in range(n_sim):
        seq = rng.permutation(wins)
        if n >= need:
            chunk = seq[:need]
        else:
            reps = int(np.ceil(need / n))
            chunk = np.tile(seq, reps)[:need]
        out[i] = chunk.reshape(n_weeks, TRADES_PER_WEEK).sum(axis=1)
    return out


def block_weeks(
    rng: np.random.Generator, wins: np.ndarray, n_sim: int, n_weeks: int, block: int
) -> np.ndarray:
    n = len(wins)
    if n < block:
        raise IdentityHalt(f"HALT block {block} > n {n}")
    starts = n - block + 1
    out = np.empty((n_sim, n_weeks), dtype=np.int16)
    for i in range(n_sim):
        seq = []
        while len(seq) < n_weeks * TRADES_PER_WEEK:
            s = int(rng.integers(0, starts))
            seq.extend(wins[s : s + block].tolist())
        chunk = np.array(seq[: n_weeks * TRADES_PER_WEEK], dtype=np.int8)
        out[i] = chunk.reshape(n_weeks, TRADES_PER_WEEK).sum(axis=1)
    return out


def bernoulli_weeks(rng: np.random.Generator, p: float, n_sim: int, n_weeks: int) -> np.ndarray:
    return rng.binomial(TRADES_PER_WEEK, p, size=(n_sim, n_weeks))


def week_path_stats(k: np.ndarray, sequences: np.ndarray | None, f_pct: int) -> dict:
    """k: (n,) wins in 10. sequences optional (n, 10) for streaks."""
    b0 = B0_CENTS
    pnl = np.array([week_pnl_cents(int(x), b0, f_pct) for x in k], dtype=np.int64)
    end = b0 + pnl
    ret = pnl.astype(np.float64) / b0
    out = {
        "n": int(len(k)),
        "mean_k": round(float(k.mean()), 4),
        "median_k": float(np.median(k)),
        "mean_return": round(float(ret.mean()) * 100, 4),
        "median_return": round(float(np.median(ret)) * 100, 4),
        "p05_return": round(float(np.quantile(ret, 0.05)) * 100, 4),
        "p95_return": round(float(np.quantile(ret, 0.95)) * 100, 4),
        "sd_return": round(float(ret.std(ddof=1)) * 100, 4),
        "prob_lose": round(float((pnl < 0).mean()) * 100, 4),
        "prob_loss_5": round(float((ret <= -0.05).mean()) * 100, 4),
        "prob_loss_10": round(float((ret <= -0.10).mean()) * 100, 4),
        "prob_gain_10": round(float((ret >= 0.10).mean()) * 100, 4),
        "chatgpt_R_at_5_7wins": week_return_frac(7, 5),
        "chatgpt_R_at_5_5wins": week_return_frac(5, 5),
    }
    if sequences is not None:
        lose3 = lose4 = lose5 = lose6 = win_long = lose_long = 0
        worst10 = 10
        for row in sequences:
            worst10 = min(worst10, int(row.sum()))
            lose_long = max(lose_long, longest_run(row, 0))
            win_long = max(win_long, longest_run(row, 1))
            lr = longest_run(row, 0)
            lose3 += int(lr >= 3)
            lose4 += int(lr >= 4)
            lose5 += int(lr >= 5)
            lose6 += int(lr >= 6)
        n = len(sequences)
        out.update(
            {
                "prob_lose_streak_3": round(100.0 * lose3 / n, 4),
                "prob_lose_streak_4": round(100.0 * lose4 / n, 4),
                "prob_lose_streak_5": round(100.0 * lose5 / n, 4),
                "prob_lose_streak_6": round(100.0 * lose6 / n, 4),
                "worst_10_trade_wins": worst10,
                "max_lose_streak_seen": lose_long,
                "max_win_streak_seen": win_long,
            }
        )
    return out


def stability(rows: list[dict]) -> dict:
    def pack(sub, label):
        n = len(sub)
        k = sum(1 for r in sub if as_bool(r.get("win_80_40")))
        p, lo, hi = wilson(k, n)
        return {"label": label, "n": n, "wins": k, "pct": p, "wilson_lo": lo, "wilson_hi": hi}

    groups = defaultdict(list)
    for i, r in enumerate(rows):
        groups[("split", r.get("dataset_split") or "UNSPLIT")].append(r)
        groups[("sport", r.get("sport") or "?")].append(r)
        groups[("slice", f"{r.get('sport')}:{r.get('slice')}")].append(r)
        groups[("month", r.get("calendar_month") or "?")].append(r)
        groups[("side", r.get("side") or "?")].append(r)
        groups[("phase", r.get("season_phase") or "?")].append(r)
        groups[("entry_bid", entry_bucket(as_float(r.get("entry_implied_prob"))))].append(r)
        groups[("pregame", fav_bucket(bought_pregame(r)))].append(r)
        groups[("block500", f"BLOCK500_{i // 500}")].append(r)

    out = {}
    for (kind, _), _ in groups.items():
        out.setdefault(kind, [])
    for (kind, name), sub in sorted(groups.items()):
        out[kind].append(pack(sub, name))
    for kind in out:
        out[kind].sort(key=lambda r: r["label"])
    return out


def dollars(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def run(rows: list[dict]) -> dict:
    wins_full = outcomes_of(rows)
    by_split = {
        name: outcomes_of([r for r in rows if r.get("dataset_split") == name])
        for name in ("IN_SAMPLE", "VALIDATION", "OOS")
    }
    for name, arr in by_split.items():
        if arr.size == 0:
            raise IdentityHalt(f"HALT empty {name}")

    edge = {}
    for name, arr in (("FULL", wins_full), *by_split.items()):
        k = int(arr.sum())
        n = int(arr.size)
        p, lo, hi = wilson(k, n)
        edge[name] = {
            "n": n,
            "wins": k,
            "pct": p,
            "wilson_lo": lo,
            "wilson_hi": hi,
            "breakeven": round(BREAKEVEN * 100, 4),
            "edge_vs_breakeven_pp": None if p is None else round(p - BREAKEVEN * 100, 4),
        }

    rng = np.random.default_rng(SEED)
    risk_wins = by_split["IN_SAMPLE"]
    p_is = float(risk_wins.mean())

    # 10-trade IID paths from IN_SAMPLE (risk model population)
    seq_week = rng.choice(risk_wins, size=(N_WEEK, TRADES_PER_WEEK), replace=True)
    k_week = seq_week.sum(axis=1)
    week_iid = week_path_stats(k_week, seq_week, FRACTION_HEADLINE)

    # Season 22 weeks
    seasons = {}
    k_iid = iid_weeks(rng, risk_wins, N_SEASON, WEEKS)
    seasons["iid_in_sample"] = dist_summary(*apply_weeks(k_iid, FRACTION_HEADLINE))
    seasons["iid_in_sample"]["population"] = "IN_SAMPLE"
    seasons["iid_in_sample"]["method"] = "IID_BOOTSTRAP"

    k_perm = permute_weeks(rng, risk_wins, N_SEASON, WEEKS)
    seasons["permutation_in_sample"] = dist_summary(*apply_weeks(k_perm, FRACTION_HEADLINE))
    seasons["permutation_in_sample"]["method"] = "PERMUTATION"

    for bl in BLOCK_LENS:
        k_b = block_weeks(rng, risk_wins, N_SEASON, WEEKS, bl)
        seasons[f"block_{bl}_in_sample"] = dist_summary(*apply_weeks(k_b, FRACTION_HEADLINE))
        seasons[f"block_{bl}_in_sample"]["method"] = f"BLOCK_BOOTSTRAP_{bl}"

    # Confirmation: VAL / OOS / FULL IID (labeled)
    for name, arr, tag in (
        ("VALIDATION", by_split["VALIDATION"], "iid_validation"),
        ("OOS", by_split["OOS"], "iid_oos"),
        ("FULL", wins_full, "iid_full_descriptive_contaminated"),
    ):
        k = iid_weeks(rng, arr, N_GRID, WEEKS)
        seasons[tag] = dist_summary(*apply_weeks(k, FRACTION_HEADLINE))
        seasons[tag]["population"] = name
        seasons[tag]["method"] = "IID_BOOTSTRAP"

    true_p = {}
    for p in TRUE_P:
        k = bernoulli_weeks(rng, p, N_GRID, WEEKS)
        rec = dist_summary(*apply_weeks(k, FRACTION_HEADLINE))
        rec["assumed_p"] = p
        rec["method"] = "BERNOULLI_TRUE_P"
        true_p[str(p)] = rec

    sizing = {}
    for f in SIZES:
        k = iid_weeks(rng, risk_wins, N_GRID, WEEKS)
        rec = dist_summary(*apply_weeks(k, f))
        rec["fraction_pct"] = f
        rec["method"] = "IID_IN_SAMPLE"
        sizing[str(f)] = rec

    # Realized chronological path at 5%
    hist_k = []
    bits = wins_full.tolist()
    for i in range(0, len(bits) - TRADES_PER_WEEK + 1, TRADES_PER_WEEK):
        hist_k.append(sum(bits[i : i + TRADES_PER_WEEK]))
    rem = len(bits) % TRADES_PER_WEEK
    hist_weeks = np.array(hist_k, dtype=np.int16).reshape(1, -1)
    # walk all complete 10-trade blocks in time order as one path (not 22 weeks)
    b = B0_CENTS
    peak = b
    min_b = b
    max_dd = 0
    for kv in hist_k:
        pnl = week_pnl_cents(int(kv), b, FRACTION_HEADLINE)
        b += pnl
        if b < 0:
            b = 0
        if b > peak:
            peak = b
        max_dd = max(max_dd, peak - b)
        min_b = min(min_b, b)
    realized = {
        "n_complete_10_blocks": len(hist_k),
        "remainder_trades": rem,
        "end_cents": b,
        "min_cents": min_b,
        "max_dd_frac": 0.0 if peak <= 0 else max_dd / peak,
        "note": "Time-ordered 10-trade blocks through the 1,182-row book. Not 22 independent weeks.",
    }

    return {
        "written_utc": utc_now(),
        "research_only": True,
        "live_execution": False,
        "candle_path_not_fill": True,
        "universe_n": EXPECTED_N,
        "not_3000_games": True,
        "outcome": "win_80_40",
        "not_terminal_W": True,
        "seed": SEED,
        "b0_cents": B0_CENTS,
        "fraction_headline_pct": FRACTION_HEADLINE,
        "trades_per_week": TRADES_PER_WEEK,
        "weeks": WEEKS,
        "n_week_paths": N_WEEK,
        "n_season_paths": N_SEASON,
        "n_grid_paths": N_GRID,
        "edge": edge,
        "stability": stability(rows),
        "week_iid_in_sample": week_iid,
        "season": seasons,
        "true_p": true_p,
        "sizing": sizing,
        "realized_chronological": realized,
        "p_in_sample": p_is,
        "status": {
            "strategy_authorized": False,
            "live_execution": False,
            "risk_model_population": "IN_SAMPLE",
            "full_book_iid": "DESCRIPTIVE_CONTAMINATED",
        },
    }


def _f(cents):
    if cents is None:
        return ""
    return f"${cents / 100:,.0f}"


def write_report(doc: dict) -> str:
    e = doc["edge"]
    w = doc["week_iid_in_sample"]
    s = doc["season"]["iid_in_sample"]
    lines = [
        "# Asked-six 80/40 path distribution",
        "",
        "```",
        "RESEARCH ONLY",
        "CANDLE PATH ≠ ACTUAL FILL",
        "NOT 3,000 GAMES — N = 1,182",
        "HEADLINE WIN = win_80_40 = 74.70%  (NOT terminal W = 83.84%)",
        "RISK MODEL FIT ON IN_SAMPLE ONLY",
        "LIVE EXECUTION = FALSE",
        "```",
        "",
        "Buy 80 / close-path stop 40. +20¢ / −40¢. Zero fee. Integer contracts.",
        "Stake = 5% of **week-start** bankroll. 10 trades / week. 22 weeks.",
        "Start $20,000. Seed 20260910.",
        "",
        "## Edge (do not use FULL to both prove and size)",
        "",
        "| Split | N | 80/40 wins | Rate | Wilson 95% | vs 66.67% |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name in ("IN_SAMPLE", "VALIDATION", "OOS", "FULL"):
        r = e[name]
        lines.append(
            f"| {name} | {r['n']} | {r['wins']} | {r['pct']}% | "
            f"{r['wilson_lo']}–{r['wilson_hi']} | {r['edge_vs_breakeven_pp']} pp |"
        )
    lines.extend(
        [
            "",
            "IN_SAMPLE is the locked risk-model population. FULL is descriptive.",
            "",
            "## 10-trade week (IID IN_SAMPLE, 200,000 paths, 5%)",
            "",
            f"Median return **{w['median_return']}%**. 5th **{w['p05_return']}%**. "
            f"95th **{w['p95_return']}%**.",
            f"P(lose week) {w['prob_lose']}%. P(≤−5%) {w['prob_loss_5']}%. "
            f"P(≤−10%) {w['prob_loss_10']}%. P(≥+10%) {w['prob_gain_10']}%.",
            f"Check: 7/3 → {week_return_frac(7, 5)*100:.2f}% ; 5/5 → {week_return_frac(5, 5)*100:.2f}%.",
            "",
        ]
    )
    if "prob_lose_streak_3" in w:
        lines.extend(
            [
                f"P(≥3-loss streak in the week) {w['prob_lose_streak_3']}%. "
                f"≥4 {w['prob_lose_streak_4']}%. ≥5 {w['prob_lose_streak_5']}%. "
                f"≥6 {w['prob_lose_streak_6']}%.",
                "",
            ]
        )
    lines.extend(
        [
            "## 22-week bankroll at 5% (IN_SAMPLE risk model)",
            "",
            "| Method | P5 | P50 | P95 | P(lose) | P(≤−20%) | Median DD |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for key, label in (
        ("iid_in_sample", "IID IN_SAMPLE"),
        ("permutation_in_sample", "Permutation"),
        ("block_10_in_sample", "Block 10"),
        ("iid_validation", "IID VALIDATION"),
        ("iid_oos", "IID OOS"),
        ("iid_full_descriptive_contaminated", "IID FULL (contaminated)"),
    ):
        r = doc["season"][key]
        lines.append(
            f"| {label} | {_f(r['p05_end_cents'])} | {_f(r['p50_end_cents'])} | "
            f"{_f(r['p95_end_cents'])} | {r['prob_lose']}% | {r['prob_loss_20']}% | "
            f"{r['median_max_dd']}% |"
        )
    lines.extend(
        [
            "",
            "## True-p model risk (Bernoulli, 5%, 22 weeks)",
            "",
            "| Assumed p | P50 end | P5 end | P(lose) | P(≤−20%) |",
            "|---:|---:|---:|---:|---:|",
        ]
    )
    for p in TRUE_P:
        r = doc["true_p"][str(p)]
        lines.append(
            f"| {p:.1%} | {_f(r['p50_end_cents'])} | {_f(r['p05_end_cents'])} | "
            f"{r['prob_lose']}% | {r['prob_loss_20']}% |"
        )
    lines.extend(
        [
            "",
            "## Position size (IID IN_SAMPLE, 22 weeks)",
            "",
            "| f | P50 end | P5 end | Median DD | P(≤−20%) | P(ruin) |",
            "|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for f in SIZES:
        r = doc["sizing"][str(f)]
        lines.append(
            f"| {f}% | {_f(r['p50_end_cents'])} | {_f(r['p05_end_cents'])} | "
            f"{r['median_max_dd']}% | {r['prob_loss_20']}% | {r['prob_ruin']}% |"
        )
    rh = doc["realized_chronological"]
    lines.extend(
        [
            "",
            "## Realized chronological book (not a sim)",
            "",
            f"{rh['n_complete_10_blocks']} complete 10-trade blocks, "
            f"{rh['remainder_trades']} leftover trades. "
            f"End {_f(rh['end_cents'])}. Min {_f(rh['min_cents'])}. "
            f"Max DD {rh['max_dd_frac']*100:.2f}%.",
            "",
            "## What this is not",
            "",
            "- Not a live authorization.",
            "- Not a fill. 40 exits are assumed.",
            "- Not 3,000 games.",
            "- Not terminal 83.84% as the strategy win rate.",
            "- FULL IID is contaminated if you also used FULL to quote the edge.",
            "",
            "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def write_outputs(doc: dict) -> None:
    report = write_report(doc)
    payload = json.dumps(doc, indent=2) + "\n"
    for dest in (OUT, WH_OUT):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "REPORT.md").write_text(report)
        (dest / "summary.json").write_text(payload)


def main() -> int:
    rows = load_ledger()
    doc = run(rows)
    write_outputs(doc)
    print(json.dumps({
        "n": doc["universe_n"],
        "in_sample_pct": doc["edge"]["IN_SAMPLE"]["pct"],
        "week_median": doc["week_iid_in_sample"]["median_return"],
        "season_p50": doc["season"]["iid_in_sample"]["p50_end_cents"],
        "season_p05": doc["season"]["iid_in_sample"]["p05_end_cents"],
        "out": str(OUT),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
