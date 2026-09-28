#!/usr/bin/env python3
"""Asked-six 80/40 liquidation / slippage calibration (research only).

The frozen ledger labels every STOP_40 at exactly 40¢. That is a close-path
signal, not a fill. market_trades are UNAVAILABLE. This module does not invent
fills. It:

1. Measures candle-path behavior in the five minutes after the first T40
   close (NOT a fill; NOT the rest-of-game min, which is often 0 on losers).
2. Applies declared liquidation mixes to the 299 historical stops.
3. Re-runs the 2–8% week-start bankroll grid under those mixes.

```
RESEARCH ONLY
CANDLE PATH ≠ ACTUAL FILL
LIVE EXECUTION = FALSE
DO NOT CHANGE LIVE FIRST01
NO MIX IS A PROVEN KALSHI FILL
```

Integer cents. Wins remain +20. Stops draw an exit from the mix.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first80_asked_six_chatgpt_export as E  # noqa: E402
import first80_asked_six_80_40_quant_paths as Q  # noqa: E402

REPO = Path("/Users/user/Desktop/Momento")
LEDGER = E.OUT / "first80_asked_six.csv"
OUT = REPO / "research" / "first80_asked_six_80_40_liquidation"
WH_OUT = E.WH_OUT.parent / "first80_asked_six_80_40_liquidation"

EXPECTED_N = 1182
EXPECTED_WIN = 883
EXPECTED_STOP = 299
ENTRY_CENTS = 80
WIN_PNL = 20
B0_CENTS = 2_000_000
TRADES_PER_WEEK = 10
WEEKS_5M = 22
WEEKS_1Y = 52
SIZES = (2, 3, 4, 5, 6, 7, 8)
TRUE_P = (0.70, 0.72, 0.747)
N_SEASON = 40_000
N_YEAR = 20_000
N_TRUEP = 20_000
SEED = 20260911
POST_T40_SEC = 300
HIT40_E4 = E.HIT40_E4
MAX_SPREAD_E4 = 1000  # 10¢, same as FIRST80 quality filter

# Frozen viability (set before looking at results).
# A size is viable at a given mix and true p only if ALL hold on the
# 22-week IN_SAMPLE-risk simulation:
#   median end > start
#   P(lose money) ≤ 10%
#   P(DD > 20%) ≤ 10%
#   P5 end ≥ $16,000 (≤20% loss at the 5th percentile)
VIABLE_P_LOSE_MAX = 0.10
VIABLE_P_DD20_MAX = 0.10
VIABLE_P5_MIN_CENTS = 1_600_000


class IdentityHalt(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def halt_identity(n: int, wins: int, stops: int) -> None:
    if (n, wins, stops) != (EXPECTED_N, EXPECTED_WIN, EXPECTED_STOP):
        raise IdentityHalt(f"HALT identity {n}/{wins}/{stops}")


def observed_p() -> float:
    return EXPECTED_WIN / EXPECTED_N


def breakeven_avg_loss_cents(p: float) -> float:
    """L such that p*20 − (1-p)*L = 0. Win is +20."""
    if p <= 0 or p >= 1:
        raise ValueError(p)
    return 20.0 * p / (1.0 - p)


def ev_cents(p: float, avg_loss_cents: float) -> float:
    """p*(+20) − (1-p)*L. L is a positive loss magnitude."""
    return p * 20.0 - (1.0 - p) * avg_loss_cents


def mix_avg_exit_cents(weights: dict[int, int]) -> float:
    if sum(weights.values()) != 100:
        raise IdentityHalt(f"HALT mix weights {weights}")
    return sum(px * w for px, w in weights.items()) / 100.0


def mix_avg_loss_cents(weights: dict[int, int]) -> float:
    return ENTRY_CENTS - mix_avg_exit_cents(weights)


def mix_pnl_cents(exit_cents: int) -> int:
    if exit_cents < 0 or exit_cents > ENTRY_CENTS:
        raise ValueError(exit_cents)
    return int(exit_cents) - ENTRY_CENTS


# Declared mixes. Keys are exit prices in cents. Values are percents.
# User mixes use 0 as the blow-through tail. Legacy research overlay
# uses 10 instead of 0.
MIXES: dict[str, dict[int, int]] = {
    "OPTIMISTIC_40": {40: 100},
    "M90_10_40_20": {40: 90, 20: 10},
    "M75_20_5_40_20_0": {40: 75, 20: 20, 0: 5},
    "M50_30_20_40_20_0": {40: 50, 20: 30, 0: 20},
    "LEGACY_50_30_20_40_20_10": {40: 50, 20: 30, 10: 20},
    "WORST_ALL_0": {0: 100},
}


def sample_exits(weights: dict[int, int], n: int, rng: np.random.Generator) -> np.ndarray:
    prices = np.array(sorted(weights.keys()), dtype=np.int64)
    probs = np.array([weights[int(p)] for p in prices], dtype=np.float64) / 100.0
    return rng.choice(prices, size=n, p=probs)


def load_stops_and_wins() -> tuple[list[dict], list[dict], dict[str, list[bool]]]:
    rows = list(csv.DictReader(LEDGER.open()))
    wins = [r for r in rows if Q.as_bool(r["win_80_40"])]
    stops = [r for r in rows if Q.as_bool(r["stopped_40"])]
    halt_identity(len(rows), len(wins), len(stops))
    bits: dict[str, list[bool]] = {}
    for name, pop in (
        ("FULL", rows),
        ("IN_SAMPLE", [r for r in rows if r["dataset_split"] == "IN_SAMPLE"]),
        ("VALIDATION", [r for r in rows if r["dataset_split"] == "VALIDATION"]),
        ("OOS", [r for r in rows if r["dataset_split"] == "OOS"]),
    ):
        bits[name] = [Q.as_bool(r["win_80_40"]) for r in pop]
    if sum(bits["FULL"]) != EXPECTED_WIN:
        raise IdentityHalt("HALT full wins")
    return wins, stops, bits


def sport_mod(sport: str):
    if sport == "NBA":
        return E.NBA_Q
    if sport == "WNBA":
        return E.WNBA_Q
    if sport == "NCAAB":
        return E.NCAAB_Q
    raise IdentityHalt(sport)


def e4_to_cents(v) -> int | None:
    if v is None:
        return None
    return int(v) // 100


def nearest_close_cents(quotes: list[dict], target_ts: int, lo: int, hi: int):
    best = None
    best_d = None
    for q in quotes:
        ts = int(q["ts"])
        if ts < lo or ts > hi:
            continue
        d = abs(ts - target_ts)
        if best_d is None or d < best_d:
            best_d = d
            best = q
    if best is None or best.get("bid_c") is None:
        return None
    return e4_to_cents(best["bid_c"])


def tradable_quotes(quotes: list[dict]) -> list[dict]:
    """Same quality walk as FIRST80. Quotes are e4. had_q starts True."""
    had_q = True
    out = []
    for q in quotes:
        ok = E.quality_ok(q, had_q)
        if ok:
            had_q = True
        if not ok or q.get("bid_c") is None:
            continue
        out.append(q)
    return out


def tradable_after_entry(quotes: list[dict], entry_ts: int) -> list[dict]:
    return [q for q in tradable_quotes(quotes) if int(q["ts"]) > int(entry_ts)]


def post_t40_window(
    quotes: list[dict],
    entry_ts: int,
    t40_ts: int | None = None,
) -> dict:
    """Frozen T40 bar, then the next 5 minutes of tradable closes.

    Quotes are e4 (8000 = 80¢). Outputs are cents. Window is after the T40
    bar, not the rest of the game. Rest-of-game min is usually 0 on
    eventual losers and is not a stop fill.
    """
    all_tr = tradable_quotes(quotes)
    tradable = [q for q in all_tr if int(q["ts"]) > int(entry_ts)]
    t40 = None
    if t40_ts is not None:
        for q in tradable:
            if int(q["ts"]) == int(t40_ts):
                t40 = q
                break
        if t40 is None:
            later = [q for q in tradable if int(q["ts"]) >= int(t40_ts)]
            if later:
                t40 = later[0]
    if t40 is None:
        for q in tradable:
            if int(q["bid_c"]) <= HIT40_E4:
                t40 = q
                break
    if t40 is None:
        return {"found": False}
    t0 = int(t40["ts"])
    before = [q for q in all_tr if int(q["ts"]) < t0]
    prior = before[-1] if before else None
    after = [
        q
        for q in tradable
        if t0 < int(q["ts"]) <= t0 + POST_T40_SEC
    ]
    closes = [e4_to_cents(q["bid_c"]) for q in after]
    lows = [e4_to_cents(q["bid_l"]) for q in after if q.get("bid_l") is not None]
    t40_close = e4_to_cents(t40["bid_c"])
    prior_close = e4_to_cents(prior["bid_c"]) if prior is not None else None
    return {
        "found": True,
        "t40_ts": t0,
        "t40_close": t40_close,
        "t40_low": e4_to_cents(t40.get("bid_l")),
        "prior_close": prior_close,
        "prior_ts": int(prior["ts"]) if prior is not None else None,
        "drop_from_prior": (
            None if prior_close is None or t40_close is None
            else int(prior_close) - int(t40_close)
        ),
        "n_bars_5m": len(after),
        "min_close_5m": min(closes) if closes else None,
        "min_low_5m": min(lows) if lows else None,
        "close_1m": nearest_close_cents(tradable, t0 + 60, t0 + 1, t0 + 90),
        "close_2m": nearest_close_cents(tradable, t0 + 120, t0 + 60, t0 + 180),
        "close_5m": nearest_close_cents(tradable, t0 + 300, t0 + 180, t0 + 360),
    }


def scan_post_t40(stops: list[dict]) -> list[dict]:
    caches: dict[str, dict[str, Path]] = {}
    out = []
    for row in stops:
        sport = row["sport"]
        if sport not in caches:
            caches[sport] = E.index_candles(sport_mod(sport).CANDLES_DIR)
        path = caches[sport].get(row["ticker"])
        rec = {
            "event_id": row["event_id"],
            "ticker": row["ticker"],
            "sport": sport,
            "dataset_split": row["dataset_split"],
            "entry_ts": int(float(row["timestamp"])),
            "ledger_t40_ts": (
                int(float(row["exit_timestamp"]))
                if row.get("exit_timestamp") not in (None, "")
                else None
            ),
            "found": False,
        }
        if path is None:
            rec["missing_reason"] = "no_candle_path"
            out.append(rec)
            continue
        quotes = E.load_ticker_quotes(path)
        rec.update(post_t40_window(quotes, rec["entry_ts"], rec["ledger_t40_ts"]))
        if not rec.get("found"):
            rec["missing_reason"] = "t40_not_on_tradable_path"
        out.append(rec)
    return out


def summarize_window(recs: list[dict]) -> dict:
    found = [r for r in recs if r.get("found")]
    t40 = [int(r["t40_close"]) for r in found]
    m5 = [int(r["min_close_5m"]) for r in found if r.get("min_close_5m") is not None]
    c1 = [int(r["close_1m"]) for r in found if r.get("close_1m") is not None]
    c2 = [int(r["close_2m"]) for r in found if r.get("close_2m") is not None]
    c5 = [int(r["close_5m"]) for r in found if r.get("close_5m") is not None]

    def bucket(xs: list[int]) -> dict:
        return {
            "n": len(xs),
            "mean": round(float(np.mean(xs)), 4) if xs else None,
            "median": int(np.median(xs)) if xs else None,
            "le40": int(sum(x <= 40 for x in xs)),
            "le30": int(sum(x <= 30 for x in xs)),
            "le20": int(sum(x <= 20 for x in xs)),
            "le10": int(sum(x <= 10 for x in xs)),
            "eq0": int(sum(x <= 0 for x in xs)),
            "lt40": int(sum(x < 40 for x in xs)),
        }

    return {
        "n_stops": len(recs),
        "n_found": len(found),
        "n_missing": len(recs) - len(found),
        "label": "CANDLE_5M_AFTER_T40_NOT_FILL",
        "t40_close": bucket(t40),
        "t40_already_below_40": int(sum(x < 40 for x in t40)),
        "t40_already_le30": int(sum(x <= 30 for x in t40)),
        "t40_already_le20": int(sum(x <= 20 for x in t40)),
        "t40_already_le10": int(sum(x <= 10 for x in t40)),
        "min_close_5m": bucket(m5),
        "close_1m": bucket(c1),
        "close_2m": bucket(c2),
        "close_5m": bucket(c5),
        "note": (
            "Five minutes after the first close-path ≤40. Not a fill. "
            "Not rest-of-game min (that is usually 0 on eventual losers)."
        ),
    }


def empirical_5m_weights(recs: list[dict]) -> dict[int, int] | None:
    """Map 5-minute min close to {40,20,0} percents. MODELED, not a fill.

    ≤10 → 0, ≤25 → 20, else 40. Used only as a candle-path stress mix.
    """
    xs = [
        int(r["min_close_5m"])
        for r in recs
        if r.get("found") and r.get("min_close_5m") is not None
    ]
    if len(xs) < 50:
        return None
    n0 = sum(x <= 10 for x in xs)
    n20 = sum(10 < x <= 25 for x in xs)
    n40 = len(xs) - n0 - n20
    # Scale to 100 while keeping integer percents.
    raw = np.array([n40, n20, n0], dtype=np.float64)
    pct = np.floor(raw * 100.0 / raw.sum()).astype(int)
    pct[0] += 100 - int(pct.sum())
    return {40: int(pct[0]), 20: int(pct[1]), 0: int(pct[2])}


def apply_weeks(
    start: int,
    f_pct: int,
    week_pnls: np.ndarray,
) -> dict:
    n = week_pnls.shape[0]
    wks = week_pnls.shape[1]
    b = np.full(n, int(start), dtype=np.int64)
    peak = b.copy()
    max_dd = np.zeros(n, dtype=np.float64)
    for t in range(wks):
        b = b + week_pnls[:, t]
        b = np.maximum(b, 0)
        peak = np.maximum(peak, b)
        dd = np.where(peak > 0, (peak - b) / peak.astype(np.float64), 0.0)
        max_dd = np.maximum(max_dd, dd)
    end = b.astype(np.float64)
    ret = end / float(start) - 1.0
    years = wks / 52.0
    cagr = np.where(end > 0, (end / float(start)) ** (1.0 / years) - 1.0, -1.0)
    return {
        "n_paths": n,
        "weeks": wks,
        "end_p50": int(np.median(b)),
        "end_mean": int(np.mean(b)),
        "end_p05": int(np.quantile(b, 0.05)),
        "end_p95": int(np.quantile(b, 0.95)),
        "cagr_p50": round(float(np.median(cagr)) * 100, 4),
        "cagr_mean": round(float(np.mean(cagr)) * 100, 4),
        "p_ge_50pct_return": round(float((ret >= 0.50).mean()) * 100, 4),
        "p_lose_money": round(float((b < start).mean()) * 100, 4),
        "p_dd_gt_20": round(float((max_dd > 0.20).mean()) * 100, 4),
        "p_dd_gt_30": round(float((max_dd > 0.30).mean()) * 100, 4),
        "p_dd_gt_40": round(float((max_dd > 0.40).mean()) * 100, 4),
        "p_dd_gt_50": round(float((max_dd > 0.50).mean()) * 100, 4),
        "dd_p50": round(float(np.median(max_dd)) * 100, 4),
        "dd_p95": round(float(np.quantile(max_dd, 0.95)) * 100, 4),
        "dd_p99": round(float(np.quantile(max_dd, 0.99)) * 100, 4),
        "label": "MODELED LIQUIDATION — NOT A FILL",
    }


def viable(row: dict, start: int = B0_CENTS) -> bool:
    return (
        row["end_p50"] > start
        and row["p_lose_money"] / 100.0 <= VIABLE_P_LOSE_MAX
        and row["p_dd_gt_20"] / 100.0 <= VIABLE_P_DD20_MAX
        and row["end_p05"] >= VIABLE_P5_MIN_CENTS
    )


def simulate_week_pnls(
    win_bits: np.ndarray,
    f_pct: int,
    n_paths: int,
    weeks: int,
    rng: np.random.Generator,
    stop_exits: np.ndarray,
    start: int = B0_CENTS,
) -> tuple[np.ndarray, np.ndarray]:
    """Each week: 10 trades, same SOD qty. Wins +20. Stops use sampled exits."""
    n_trades = n_paths * weeks * TRADES_PER_WEEK
    wins = rng.choice(win_bits, size=n_trades, replace=True)
    exits = rng.choice(stop_exits, size=n_trades, replace=True)
    pnl = np.where(wins, WIN_PNL, exits.astype(np.int64) - ENTRY_CENTS)
    pnl = pnl.reshape(n_paths, weeks, TRADES_PER_WEEK)
    # SOD qty is path-dependent. Walk week by week.
    b = np.full(n_paths, int(start), dtype=np.int64)
    week_pnls = np.zeros((n_paths, weeks), dtype=np.int64)
    lose_streak = np.zeros(n_paths, dtype=np.int64)
    best_lose = np.zeros(n_paths, dtype=np.int64)
    for t in range(weeks):
        qty = (b * int(f_pct) // 100) // ENTRY_CENTS
        qty = np.maximum(qty, 0)
        wp = (qty * pnl[:, t, :].sum(axis=1)).astype(np.int64)
        week_pnls[:, t] = wp
        # Longest losing streak is trade-level, not week-level.
        bits = (~wins.reshape(n_paths, weeks, TRADES_PER_WEEK)[:, t, :]).astype(
            np.int8
        )
        for j in range(TRADES_PER_WEEK):
            lose_streak = np.where(bits[:, j] == 1, lose_streak + 1, 0)
            best_lose = np.maximum(best_lose, lose_streak)
        b = np.maximum(b + wp, 0)
    return week_pnls, best_lose


def mix_payload(name: str, weights: dict[int, int], p: float) -> dict:
    avg_exit = mix_avg_exit_cents(weights)
    avg_loss = mix_avg_loss_cents(weights)
    return {
        "name": name,
        "kind": "declared_weights",
        "weights": {str(k): v for k, v in sorted(weights.items(), reverse=True)},
        "avg_exit_cents": round(avg_exit, 4),
        "avg_loss_cents": round(avg_loss, 4),
        "ev_cents_at_p": round(ev_cents(p, avg_loss), 4),
        "label": "MODELED MIX — NOT A FILL",
    }


def bag_payload(name: str, exits: np.ndarray, p: float, note: str) -> dict:
    xs = np.clip(exits.astype(np.int64), 0, ENTRY_CENTS)
    avg_exit = float(xs.mean()) if xs.size else float("nan")
    avg_loss = ENTRY_CENTS - avg_exit
    return {
        "name": name,
        "kind": "empirical_bag",
        "n": int(xs.size),
        "avg_exit_cents": round(avg_exit, 4),
        "avg_loss_cents": round(avg_loss, 4),
        "median_exit_cents": int(np.median(xs)) if xs.size else None,
        "p_le20": round(float((xs <= 20).mean()) * 100, 4) if xs.size else None,
        "p_eq0": round(float((xs <= 0).mean()) * 100, 4) if xs.size else None,
        "ev_cents_at_p": round(ev_cents(p, avg_loss), 4),
        "note": note,
        "label": "CANDLE-PATH BAG — NOT A FILL",
    }


def stable_key(name: str) -> int:
    return sum((i + 1) * ord(c) for i, c in enumerate(name)) % 10_000


def expand_weight_bag(weights: dict[int, int]) -> np.ndarray:
    if sum(weights.values()) != 100:
        raise IdentityHalt(f"HALT mix weights {weights}")
    return np.concatenate(
        [
            np.full(int(w), int(px), dtype=np.int64)
            for px, w in sorted(weights.items())
        ]
    )


def fmt_money(cents: int) -> str:
    return f"${cents / 100:,.0f}"


def write_report(doc: dict) -> str:
    ev = doc["expectancy"]
    win = doc["window"]
    lines = [
        "# Asked-six 80/40 liquidation calibration",
        "",
        "```",
        "RESEARCH ONLY",
        "CANDLE PATH ≠ ACTUAL FILL",
        "LIVE EXECUTION = FALSE",
        "DO NOT CHANGE LIVE FIRST01",
        "NO MIX IS A PROVEN KALSHI FILL",
        "The clean −40¢ 3–5% grid is NOT a living-size recommendation",
        "until a liquidation mix is chosen — and no mix here is proven.",
        "```",
        "",
        f"Generated: `{doc['generated_at']}`",
        "",
        "## Identity",
        "",
        f"- n = **{EXPECTED_N}**",
        f"- win_80_40 = **{EXPECTED_WIN}** (74.70%)",
        f"- STOP_40 = **{EXPECTED_STOP}** (25.30%)",
        f"- LOSS_HOLD in the ledger = **0** (every loser is labeled 40¢)",
        f"- Every STOP_40 `exit_price_cents` = **40**. That is the signal, not a fill.",
        "",
        "## Why 40¢ is not established",
        "",
        "The ledger `column_layer_map` says the market path is candle-based, "
        "`market_trades` are UNAVAILABLE, and `market_last_price` is candle last, "
        "not a fill. A close-path print ≤40 does not prove a 40¢ bid was liftable "
        "in size, nor that a fast move stopped at 40.",
        "",
        "## Expectancy at the observed 74.70%",
        "",
        "Win remains +20¢. Average stop loss L is the variable.",
        "",
        f"- Breakeven L at 74.70% = **{ev['breakeven_L_at_observed_p']:.2f}¢** "
        f"(exit ≈ **{80 - ev['breakeven_L_at_observed_p']:.2f}¢**).",
        "- If the real average liquidation on the 299 stops is worse than ~59¢ "
        "of loss, the historical win rate no longer produces positive EV.",
        "- That is **before** fees, spread, latency, partial fills.",
        "",
        "| Average loss | Breakeven WR | EV at 74.70% |",
        "|---:|---:|---:|",
    ]
    for row in ev["loss_table"]:
        lines.append(
            f"| −{row['avg_loss_cents']}¢ | {row['breakeven_wr_pct']:.2f}% | "
            f"{row['ev_at_observed_p']:+.2f}¢ |"
        )
    lines += [
        "",
        "## Candle 5 minutes after first T40 — still not a fill",
        "",
        "Do **not** use `post_entry_min_yes_bid`. On losers that later settle 0, "
        "the rest-of-game min is often 0. That is hold-to-expiry, not stop slippage.",
        "",
        "This scan looks at the first tradable close ≤40 after entry, then the "
        f"next {POST_T40_SEC} seconds of tradable closes.",
        "",
        f"- Stops scanned: {win['n_stops']}",
        f"- T40 found: {win['n_found']} (missing {win['n_missing']})",
        f"- T40 close already <40 (gapped through the 40 print): "
        f"**{win['t40_already_below_40']} / {win['n_found']}**",
        f"- T40 close already ≤30: {win['t40_already_le30']}",
        f"- T40 close already ≤20: {win['t40_already_le20']}",
        f"- T40 close already ≤10: {win['t40_already_le10']}",
        "",
        "| Window | n | mean | median | ≤30 | ≤20 | ≤10 | =0 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key, label in (
        ("t40_close", "T40 close"),
        ("close_1m", "+1m close"),
        ("close_2m", "+2m close"),
        ("close_5m", "+5m close"),
        ("min_close_5m", "min close in +5m"),
    ):
        b = win[key]
        lines.append(
            f"| {label} | {b['n']} | {b['mean']} | {b['median']} | "
            f"{b['le30']} | {b['le20']} | {b['le10']} | {b['eq0']} |"
        )
    if doc.get("empirical_5m_mix"):
        e = doc["empirical_5m_mix"]
        lines += [
            "",
            "### Empirical 5m min-close mapped to {40,20,0}",
            "",
            f"- Mix: {e['weights']} — **MODELED FROM CANDLE, NOT A FILL**",
            f"- Average modeled exit: {e['avg_exit_cents']}¢",
            f"- Average modeled loss: {e['avg_loss_cents']}¢",
            f"- EV at 74.70%: {e['ev_cents_at_p']:+.2f}¢",
        ]
    lines += [
        "",
        "## Declared mixes",
        "",
        "These are scenarios, not estimated Kalshi fill rates.",
        "",
        "| Mix | Definition | Avg exit | Avg loss | EV @ 74.70% |",
        "|---|---|---:|---:|---:|",
    ]
    for m in doc["mixes"]:
        if m.get("kind") == "empirical_bag":
            w = (
                f"empirical n={m['n']}; median {m['median_exit_cents']}¢; "
                f"P(≤20)={m['p_le20']}%; P(0)={m['p_eq0']}%"
            )
        else:
            w = ", ".join(f"{v}%@{k}¢" for k, v in m["weights"].items())
        lines.append(
            f"| `{m['name']}` | {w} | {m['avg_exit_cents']:.1f}¢ | "
            f"−{m['avg_loss_cents']:.1f}¢ | {m['ev_cents_at_p']:+.2f}¢ |"
        )
    lines += [
        "",
        "## Bankroll grid (IN_SAMPLE risk model, 22 weeks ≈ 5 months)",
        "",
        f"Start {fmt_money(B0_CENTS)}. Stake = f% of **week-start** bankroll. "
        f"{TRADES_PER_WEEK} trades/week. Same SOD size. Integer contracts = stake // 80. "
        "Wins +20¢/contract. Each stop draws an exit from the mix.",
        "",
        "Risk-model population is **IN_SAMPLE only**. FULL book is contaminated "
        "if used both to prove edge and fit risk.",
        "",
        "Catastrophic drawdown is reported at −30%, −40%, and −50%.",
        "",
    ]
    for m in doc["mixes"]:
        grid = doc["grids"][m["name"]]["weeks_22"]
        lines += [
            f"### {m['name']} — 22 weeks",
            "",
            "| f | median end | P5 | CAGR p50 | P(≥50% ret) | P(lose) | "
            "P(DD>20) | DD p95 | DD p99 | P(DD>50) | lose-streak p95 | viable |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|",
        ]
        for f in SIZES:
            r = grid[str(f)]
            lines.append(
                f"| {f}% | {fmt_money(r['end_p50'])} | {fmt_money(r['end_p05'])} | "
                f"{r['cagr_p50']:.1f}% | {r['p_ge_50pct_return']:.1f}% | "
                f"{r['p_lose_money']:.2f}% | {r['p_dd_gt_20']:.1f}% | "
                f"{r['dd_p95']:.1f}% | {r['dd_p99']:.1f}% | {r['p_dd_gt_50']:.2f}% | "
                f"{r['lose_streak_p95']} | {'YES' if r['viable'] else 'no'} |"
            )
        lines.append("")
    lines += [
        "## One year (52 weeks) at 5%",
        "",
        "Same IN_SAMPLE empirical win bits. Not a season forecast. "
        "52×10 modeled trades.",
        "",
        "| Mix | median end | P5 | CAGR p50 | P(lose) | P(DD>20) | DD p95 | P(DD>50) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for m in doc["mixes"]:
        r = doc["grids"][m["name"]]["weeks_52_f5"]
        lines.append(
            f"| `{m['name']}` | {fmt_money(r['end_p50'])} | {fmt_money(r['end_p05'])} | "
            f"{r['cagr_p50']:.1f}% | {r['p_lose_money']:.2f}% | {r['p_dd_gt_20']:.1f}% | "
            f"{r['dd_p95']:.1f}% | {r['p_dd_gt_50']:.2f}% |"
        )
    lines += [
        "",
        "## If true win rate is 72% or 70%",
        "",
        "IID Bernoulli at the stated p. Stops still draw from the mix. "
        "22 weeks. Frozen viability: median end > $20k, P(lose)≤10%, "
        "P(DD>20%)≤10%, P5 end ≥ $16k.",
        "",
        "| Mix | true p | max viable f | 5% median | 5% P(lose) | 5% P(DD>20) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for m in doc["mixes"]:
        for p in TRUE_P:
            key = f"{p:.3f}"
            block = doc["true_p"][m["name"]][key]
            lines.append(
                f"| `{m['name']}` | {p*100:.1f}% | {block['max_viable_f'] or 'none'} | "
                f"{fmt_money(block['f5']['end_p50'])} | {block['f5']['p_lose_money']:.2f}% | "
                f"{block['f5']['p_dd_gt_20']:.1f}% |"
            )
    lines += [
        "",
        "## Position-sizing implication",
        "",
        "The previous 3–5% recommendation assumed every stop fills at 40¢. "
        "That is the optimistic column. It is **not** the final living size.",
        "",
        "At 74.70% WR:",
        "",
        f"- Optimistic −40¢ EV = **{ev_cents(observed_p(), 40):+.2f}¢/trade**",
        f"- −60¢ EV = **{ev_cents(observed_p(), 60):+.2f}¢/trade**",
        f"- −80¢ EV = **{ev_cents(observed_p(), 80):+.2f}¢/trade**",
        "",
        "A 50/30/20 mix at 40/20/0 has average loss **54¢** and is still "
        "slightly positive at 74.70%, but the 22-week left tail and the 72%/70% "
        "true-p grid are the sizing constraint, not the point EV.",
        "",
        "## What this does not do",
        "",
        "- Does not change live FIRST01 / 80/81/83/89.",
        "- Does not authorize a production liquidation model.",
        "- Does not start W9.",
        "- Does not treat any mix as an estimated Kalshi fill rate.",
        "- Does not hunt a subset of the 299 stops to rescue EV.",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    wins, stops, bits = load_stops_and_wins()
    p_obs = observed_p()
    be_l = breakeven_avg_loss_cents(p_obs)
    loss_table = []
    for l in (40, 50, 60, 70, 80):
        loss_table.append(
            {
                "avg_loss_cents": l,
                "breakeven_wr_pct": round(l / (20.0 + l) * 100.0, 4),
                "ev_at_observed_p": round(ev_cents(p_obs, l), 4),
            }
        )
    print("scanning 299 STOP_40 tickers for +5m after T40…", flush=True)
    recs = scan_post_t40(stops)
    window = summarize_window(recs)
    run_mixes: list[dict] = [mix_payload(n, w, p_obs) for n, w in MIXES.items()]
    bags: dict[str, np.ndarray] = {
        name: expand_weight_bag(weights) for name, weights in MIXES.items()
    }
    t40_closes = np.array(
        [int(r["t40_close"]) for r in recs if r.get("found")],
        dtype=np.int64,
    )
    min_5m = np.array(
        [
            int(r["min_close_5m"])
            for r in recs
            if r.get("found") and r.get("min_close_5m") is not None
        ],
        dtype=np.int64,
    )
    emp_payload = None
    if t40_closes.size:
        t40_payload = bag_payload(
            "T40_CLOSE_AS_EXIT",
            t40_closes,
            p_obs,
            "First tradable close ≤40 after entry. If this is already 22, "
            "the 40¢ print never existed on the close path. NOT a fill.",
        )
        run_mixes.append(t40_payload)
        bags["T40_CLOSE_AS_EXIT"] = np.clip(t40_closes, 0, ENTRY_CENTS)
    if min_5m.size:
        cont = bag_payload(
            "CONTINUOUS_5M_MIN_CLOSE",
            min_5m,
            p_obs,
            "Empirical min tradable close in the 5 minutes after T40. "
            "Continuous candle-path stress. NOT a fill. NOT rest-of-game min.",
        )
        run_mixes.append(cont)
        bags["CONTINUOUS_5M_MIN_CLOSE"] = np.clip(min_5m, 0, ENTRY_CENTS)
    emp_w = empirical_5m_weights(recs)
    if emp_w is not None:
        emp_payload = mix_payload("CANDLE_5M_MIN_MAPPED", emp_w, p_obs)
        run_mixes.append(emp_payload)
        bags["CANDLE_5M_MIN_MAPPED"] = expand_weight_bag(emp_w)

    in_bits = np.array(bits["IN_SAMPLE"], dtype=bool)
    grids = {}
    true_p_out = {}
    for name, bag in bags.items():
        rng = np.random.default_rng(SEED + stable_key(name))
        g22 = {}
        for f in SIZES:
            rng_f = np.random.default_rng(int(rng.integers(1, 2**31 - 1)))
            week_pnls, streaks = simulate_week_pnls(
                in_bits, f, N_SEASON, WEEKS_5M, rng_f, bag
            )
            stats = apply_weeks(B0_CENTS, f, week_pnls)
            stats["lose_streak_p50"] = int(np.median(streaks))
            stats["lose_streak_p95"] = int(np.quantile(streaks, 0.95))
            stats["lose_streak_p99"] = int(np.quantile(streaks, 0.99))
            stats["lose_streak_max"] = int(streaks.max())
            stats["viable"] = viable(stats)
            g22[str(f)] = stats
            print(
                f"{name} f={f}% 22w median={stats['end_p50']} "
                f"P(lose)={stats['p_lose_money']} viable={stats['viable']}",
                flush=True,
            )
        rng_y = np.random.default_rng(int(rng.integers(1, 2**31 - 1)))
        week_y, streaks_y = simulate_week_pnls(
            in_bits, 5, N_YEAR, WEEKS_1Y, rng_y, bag
        )
        y5 = apply_weeks(B0_CENTS, 5, week_y)
        y5["lose_streak_p95"] = int(np.quantile(streaks_y, 0.95))
        y5["viable"] = viable(y5)
        tp = {}
        for p in TRUE_P:
            # Bernoulli wins; exits still from the mix bag.
            p_block = {}
            max_v = None
            for f in SIZES:
                rng_p = np.random.default_rng(
                    SEED + 10_000 + int(p * 1000) + f + stable_key(name)
                )
                k = int(round(p * 1000))
                synth = np.array([True] * k + [False] * (1000 - k), dtype=bool)
                wp, _ = simulate_week_pnls(
                    synth, f, N_TRUEP, WEEKS_5M, rng_p, bag
                )
                st = apply_weeks(B0_CENTS, f, wp)
                st["viable"] = viable(st)
                p_block[str(f)] = st
                if st["viable"]:
                    max_v = f
            tp[f"{p:.3f}"] = {
                "max_viable_f": max_v,
                "f5": p_block["5"],
                "grid": {k: {"end_p50": v["end_p50"], "end_p05": v["end_p05"],
                             "p_lose_money": v["p_lose_money"],
                             "p_dd_gt_20": v["p_dd_gt_20"],
                             "viable": v["viable"]}
                         for k, v in p_block.items()},
            }
        grids[name] = {"weeks_22": g22, "weeks_52_f5": y5}
        true_p_out[name] = tp

    doc = {
        "generated_at": utc_now(),
        "identity": {
            "n": EXPECTED_N,
            "win_80_40": EXPECTED_WIN,
            "stopped_40": EXPECTED_STOP,
            "p": round(p_obs, 6),
        },
        "constraints": [
            "RESEARCH ONLY",
            "CANDLE PATH ≠ ACTUAL FILL",
            "LIVE EXECUTION = FALSE",
            "NO MIX IS A PROVEN KALSHI FILL",
            "DO NOT CHANGE LIVE FIRST01",
        ],
        "expectancy": {
            "breakeven_L_at_observed_p": round(be_l, 4),
            "breakeven_exit_at_observed_p": round(80.0 - be_l, 4),
            "loss_table": loss_table,
        },
        "window": window,
        "empirical_5m_mix": emp_payload,
        "mixes": run_mixes,
        "grids": grids,
        "true_p": true_p_out,
        "seed": SEED,
        "n_season": N_SEASON,
        "n_year": N_YEAR,
        "risk_population": "IN_SAMPLE",
        "viability": {
            "p_lose_max": VIABLE_P_LOSE_MAX,
            "p_dd20_max": VIABLE_P_DD20_MAX,
            "p5_min_cents": VIABLE_P5_MIN_CENTS,
        },
        "window_recs": recs,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    WH_OUT.mkdir(parents=True, exist_ok=True)
    slim = {k: v for k, v in doc.items() if k != "window_recs"}
    (OUT / "summary.json").write_text(json.dumps(slim, indent=2) + "\n")
    (OUT / "post_t40_5m.json").write_text(json.dumps(recs, indent=2) + "\n")
    (OUT / "REPORT.md").write_text(write_report(doc))
    for fn in ("summary.json", "REPORT.md", "post_t40_5m.json"):
        (WH_OUT / fn).write_text((OUT / fn).read_text())
    print(f"wrote {OUT / 'REPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
