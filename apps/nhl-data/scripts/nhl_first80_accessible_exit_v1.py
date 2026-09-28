#!/usr/bin/env python3
"""NHL FIRST80 — gettable-at-80 universe and actual available exits.

Hockey scoring is sparse. A 1-minute bid close ≥ 80 often jumped through 80
on a goal; a later close ≤ 40 often jumped through 40. The 80→40 +20/−40
payoff treats both as executable. This measurement does not.

GETTABLE_AT_80 is the NBA HIGH_ACCESS rule ∩ HIGH maker-fill confidence.
Those filters were frozen on NBA/NCAAB. They are not fit to NHL P&L.

Actual exit = first subsequent tradable yes_bid after the path leaves 80,
or settlement 100/0 if it never leaves. The 40¢ stop is not assumed.

Research only. Does not change live FIRST01, Risk, or NBA/NCAAB artifacts.
Does not invent L2, queue, or a production fee model.

LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

NBA_SCRIPTS = Path("/Users/user/Desktop/Momento/apps/nba-data/scripts")
NCAAB_SCRIPTS = Path("/Users/user/Desktop/Momento/apps/ncaab-data/scripts")
sys.path.insert(0, str(NBA_SCRIPTS))
import nba_80_40_execution_audit as A  # noqa: E402

ROOT = Path("/Users/user/Desktop/Momento/Backtesting Suite/Data/NHL/2025-2026/warehouse")
NORM = ROOT / "normalized" / "nhl"
CANDS = ROOT / "derived" / "nhl" / "first80_execution_audit" / "candidates.json"
OUT = ROOT / "derived" / "nhl" / "first80_accessible_exit_v1"
REPORTS = Path("/Users/user/Desktop/Momento/research/nhl_first80_accessible_exit_v1")

ENTRY_CENTS = 80.0
HIT80 = 8000


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


EQ = _load(
    "first80_entry_quality_audit_v1",
    NCAAB_SCRIPTS / "first80_entry_quality_audit_v1.py",
)

# Frozen NBA rule. Not retuned on NHL.
HIGH_ACCESS = dict(EQ.HIGH_ACCESS)


def e4_to_c(v):
    return None if v is None else v / 100.0


def load_ticker_quotes(path: Path) -> list[dict]:
    return EQ.load_ticker_quotes(path)


def subsequent_tradable(quotes: list[dict], t0: int, scan_end: int | None) -> list[dict]:
    out = []
    had_q = True
    for q in quotes:
        if q["ts"] <= t0:
            continue
        if scan_end is not None and q["ts"] > scan_end:
            continue
        if not A.quality(q["bid_c"], q["ask_c"], q["vol"], had_q):
            continue
        had_q = True
        out.append(q)
    return out


def scan_end_for(rec: dict) -> int | None:
    gd = A.parse_game_date(rec.get("game_date"))
    gw_end = None
    if gd:
        gw_end = int((gd + timedelta(hours=52)).timestamp())
    close_ts = rec.get("close_ts")
    end = int(close_ts) if close_ts is not None else None
    if end is None:
        return gw_end
    if gw_end is not None:
        return min(end, gw_end)
    return end


def assumed_8040_pnl(rec: dict) -> float:
    if rec.get("stop_close_triggered"):
        return -40.0
    if rec.get("expiration_result_yes"):
        return 20.0
    return 0.0


def measure_exits(rec: dict, quotes: list[dict]) -> dict:
    """Actual available exits. Does not assume a 40¢ fill."""
    t0 = int(rec["first_80_timestamp"])
    path = subsequent_tradable(quotes, t0, scan_end_for(rec))
    settled = 100.0 if rec.get("expiration_result_yes") else 0.0

    first_leave = None
    first_40 = None
    entry_c = e4_to_c(rec.get("entry_bid_close_e4"))
    if entry_c is None:
        for q in quotes:
            if q["ts"] == t0:
                entry_c = e4_to_c(q["bid_c"])
                break
    prev_c = entry_c
    min_close = None
    min_low = None
    leave_prev = None
    t40_prev = None
    for q in path:
        c = e4_to_c(q["bid_c"])
        lo = e4_to_c(q["bid_l"])
        if c is not None:
            min_close = c if min_close is None else min(min_close, c)
        if lo is not None:
            min_low = lo if min_low is None else min(min_low, lo)
        if first_leave is None and c is not None and c < ENTRY_CENTS:
            first_leave = q
            leave_prev = prev_c
        if first_40 is None and c is not None and c <= 40.0:
            first_40 = q
            t40_prev = prev_c
        prev_c = c

    def bar_exit(q, prev) -> dict:
        close_c = e4_to_c(q["bid_c"])
        low_c = e4_to_c(q["bid_l"])
        return {
            "ts": q["ts"],
            "close": close_c,
            "low": low_c if low_c is not None else close_c,
            "prev_close": prev,
            "jump_close": None if prev is None or close_c is None else prev - close_c,
            "jumped_through_40": bool(
                prev is not None and prev > 40.0 and close_c is not None and close_c < 40.0
            ),
        }

    leave = bar_exit(first_leave, leave_prev) if first_leave else None
    t40 = bar_exit(first_40, t40_prev) if first_40 else None

    leave_mod = leave["close"] if leave else settled
    leave_con = leave["low"] if leave else settled
    t40_mod = t40["close"] if t40 else settled
    t40_con = t40["low"] if t40 else settled

    return {
        "n_subsequent_tradable": len(path),
        "left_80": leave is not None,
        "hit_40_close": t40 is not None,
        "settlement_cents": settled,
        "min_subsequent_bid_close": min_close,
        "min_subsequent_bid_low": min_low,
        "leave80": leave,
        "t40": t40,
        "actual_exit_leave80_close": leave_mod,
        "actual_exit_leave80_low": leave_con,
        "actual_exit_t40bar_close": t40_mod,
        "actual_exit_t40bar_low": t40_con,
        "pnl_leave80_close": None if leave_mod is None else leave_mod - ENTRY_CENTS,
        "pnl_leave80_low": None if leave_con is None else leave_con - ENTRY_CENTS,
        "pnl_t40bar_close": None if t40_mod is None else t40_mod - ENTRY_CENTS,
        "pnl_t40bar_low": None if t40_con is None else t40_con - ENTRY_CENTS,
        "pnl_8040_assumed": assumed_8040_pnl(rec),
        "t40_actual_minus_assumed_40": None if t40 is None or t40["close"] is None else t40["close"] - 40.0,
    }


def universe_flags(rec: dict) -> dict:
    """A priori membership. HIGH_ACCESS is the frozen NBA rule, not NHL-fit."""
    f = rec.get("entry_features") or {}
    jump = f.get("jump_1m_cents")
    close = f.get("p_entry_close_cents")
    persist = f.get("persist_78_85_min") or 0
    up = f.get("up_steps_5m") or 0
    high_fill = rec.get("maker_fill_confidence") == "HIGH"
    last_print = bool(rec.get("last_print_through_80"))
    high_access = f.get("accessibility_proxy") == "HIGH_ACCESSIBILITY"
    no_jump10 = jump is not None and jump < HIGH_ACCESS["max_jump_cents"]
    close_in_band = close is not None and 80.0 <= close < HIGH_ACCESS["max_close_cents"]
    restable = high_fill and no_jump10 and close_in_band
    gettable = high_fill and high_access
    return {
        "high_fill": high_fill,
        "last_print_through_80": last_print,
        "high_access": high_access,
        "no_jump10": no_jump10,
        "close_in_band": close_in_band,
        "persist_ge2": persist >= HIGH_ACCESS["min_persist_78_85"],
        "up_steps_ge2": up >= HIGH_ACCESS["min_up_steps_5m"],
        "GETTABLE_AT_80": gettable,
        "RESTABLE_80": restable,
        "HIGH_FILL": high_fill,
        "NO_JUMP10": no_jump10,
        "ALL_FIRST80": True,
    }


def taker_fee_cents(price_cents: float) -> float:
    e4 = int(round(price_cents * 100))
    e4 = max(0, min(10_000, e4))
    return A.quadratic_fee_e6(A.TAKER_COEF, 1, e4) / 10_000.0


def net_pnl(gross: float | None, exited: bool, exit_px: float | None) -> float | None:
    if gross is None:
        return None
    if not exited or exit_px is None:
        return gross
    return gross - taker_fee_cents(exit_px)


def _stats(xs: list[float]) -> dict:
    if not xs:
        return {"n": 0, "mean": None, "median": None, "p25": None, "p75": None, "min": None, "max": None}
    a = np.asarray(xs, dtype=float)
    return {
        "n": int(a.size),
        "mean": round(float(a.mean()), 4),
        "median": round(float(np.median(a)), 4),
        "p25": round(float(np.percentile(a, 25)), 4),
        "p75": round(float(np.percentile(a, 75)), 4),
        "min": round(float(a.min()), 4),
        "max": round(float(a.max()), 4),
    }


def wilson_rate(k: int, n: int) -> dict:
    p, lo, hi = A.wilson(k, n)
    return {"n": n, "k": k, "pct": p, "ci95": [lo, hi]}


def summarize(trades: list[dict], n_universe: int, label: str) -> dict:
    n = len(trades)
    left = [t for t in trades if t["exits"]["left_80"]]
    hit40 = [t for t in trades if t["exits"]["hit_40_close"]]
    jump40 = [t for t in hit40 if (t["exits"].get("t40") or {}).get("jumped_through_40")]

    def col(key):
        return [t["exits"][key] for t in trades if t["exits"].get(key) is not None]

    ev_8040 = [t["exits"]["pnl_8040_assumed"] for t in trades]
    ev_leave = col("pnl_leave80_close")
    ev_leave_lo = col("pnl_leave80_low")
    ev_t40 = col("pnl_t40bar_close")
    ev_t40_lo = col("pnl_t40bar_low")

    evn_leave = [
        net_pnl(t["exits"]["pnl_leave80_close"], t["exits"]["left_80"], t["exits"]["actual_exit_leave80_close"])
        for t in trades
        if t["exits"]["pnl_leave80_close"] is not None
    ]
    evn_t40 = [
        net_pnl(t["exits"]["pnl_t40bar_close"], t["exits"]["hit_40_close"], t["exits"]["actual_exit_t40bar_close"])
        for t in trades
        if t["exits"]["pnl_t40bar_close"] is not None
    ]
    evn_8040 = [
        net_pnl(t["exits"]["pnl_8040_assumed"], bool(t.get("stop_close_triggered")), 40.0)
        for t in trades
    ]

    leave_exits = [t["exits"]["actual_exit_leave80_close"] for t in left if t["exits"]["actual_exit_leave80_close"] is not None]
    leave_lows = [t["exits"]["actual_exit_leave80_low"] for t in left if t["exits"]["actual_exit_leave80_low"] is not None]
    t40_exits = [t["exits"]["actual_exit_t40bar_close"] for t in hit40 if t["exits"]["actual_exit_t40bar_close"] is not None]
    t40_lows = [t["exits"]["actual_exit_t40bar_low"] for t in hit40 if t["exits"]["actual_exit_t40bar_low"] is not None]
    t40_gaps = [
        t["exits"]["t40"]["jump_close"]
        for t in hit40
        if t["exits"].get("t40") and t["exits"]["t40"].get("jump_close") is not None
    ]
    vs40 = [t["exits"]["t40_actual_minus_assumed_40"] for t in hit40 if t["exits"]["t40_actual_minus_assumed_40"] is not None]

    wins_leave = sum(1 for x in ev_leave if x is not None and x > 0)
    return {
        "label": label,
        "n": n,
        "pct_of_n_universe": A.rate(n, n_universe),
        "pct_of_first80": None,
        "high_fill": sum(1 for t in trades if t["flags"]["high_fill"]),
        "left_80": wilson_rate(len(left), n) if n else wilson_rate(0, 0),
        "hit_40_close": wilson_rate(len(hit40), n) if n else wilson_rate(0, 0),
        "jumped_through_40": wilson_rate(len(jump40), n) if n else wilson_rate(0, 0),
        "assumed_8040": {
            "gross_ev": _stats(ev_8040)["mean"],
            "evn": _stats(evn_8040)["mean"],
            "win_rate": wilson_rate(sum(1 for t in trades if t["exits"]["pnl_8040_assumed"] > 0), n) if n else wilson_rate(0, 0),
        },
        "actual_exit_when_leaves_80": {
            "n": len(leave_exits),
            "close": _stats(leave_exits),
            "low": _stats(leave_lows),
            "note": "First subsequent tradable yes_bid after close drops below 80. Not 40.",
        },
        "actual_exit_on_40_trigger_bar": {
            "n": len(t40_exits),
            "close": _stats(t40_exits),
            "low": _stats(t40_lows),
            "jump_into_bar": _stats(t40_gaps),
            "actual_minus_assumed_40": _stats(vs40),
            "note": "Bid close/low on the first bar that closes ≤40. The 40¢ stop is not the fill.",
        },
        "all_trade_exits_leave80_or_settlement": {
            "close": _stats(col("actual_exit_leave80_close")),
            "low": _stats(col("actual_exit_leave80_low")),
            "note": "Leave-80 close if the path left 80, else settlement 100/0.",
        },
        "ev_actual_leave80_close": {
            "gross_ev": _stats(ev_leave)["mean"],
            "evn": _stats(evn_leave)["mean"],
            "win_rate": wilson_rate(wins_leave, n) if n else wilson_rate(0, 0),
            "pnl": _stats(ev_leave),
        },
        "ev_actual_leave80_low": {
            "gross_ev": _stats(ev_leave_lo)["mean"],
            "pnl": _stats(ev_leave_lo),
        },
        "ev_actual_t40bar_close": {
            "gross_ev": _stats(ev_t40)["mean"],
            "evn": _stats(evn_t40)["mean"],
            "pnl": _stats(ev_t40),
        },
        "ev_actual_t40bar_low": {
            "gross_ev": _stats(ev_t40_lo)["mean"],
            "pnl": _stats(ev_t40_lo),
        },
        "entry_jump": _stats(
            [t["entry_features"]["jump_1m_cents"] for t in trades if (t.get("entry_features") or {}).get("jump_1m_cents") is not None]
        ),
        "entry_close": _stats(
            [t["entry_features"]["p_entry_close_cents"] for t in trades if (t.get("entry_features") or {}).get("p_entry_close_cents") is not None]
        ),
    }


def attach_one(rec: dict, quotes: list[dict]) -> dict:
    rec = dict(rec)
    rec["survived"] = (not rec.get("stop_close_triggered")) and bool(rec.get("expiration_result_yes"))
    rec["entry_features"] = EQ.features_for(rec, quotes)
    rec["exits"] = measure_exits(rec, quotes)
    rec["flags"] = universe_flags(rec)
    return rec


def load_first80(path: Path | None = None) -> list[dict]:
    cands = json.loads((path or CANDS).read_text())
    return [
        dict(c)
        for c in cands
        if c.get("status") == "FIRST_80" and c.get("expiration_result_yes") is not None
    ]


def attach_all(trades: list[dict]) -> list[dict]:
    by_t = {t["ticker"]: t for t in trades if t.get("ticker")}
    files = [p for p in (NORM / "candles_1m").rglob("*.parquet") if p.stem in by_t]
    print(f"candle files {len(files)}/{len(by_t)}", flush=True)
    out = []
    seen = set()
    for n_file, path in enumerate(files, 1):
        if n_file % 400 == 0 or n_file == 1:
            print(f"scan {n_file}/{len(files)}", flush=True)
        rec = attach_one(by_t[path.stem], load_ticker_quotes(path))
        out.append(rec)
        seen.add(path.stem)
    missing = [t for t in trades if t.get("ticker") not in seen]
    for rec in missing:
        rec = dict(rec)
        rec["entry_features"] = {"window_available": False}
        rec["exits"] = {
            "left_80": False,
            "hit_40_close": bool(rec.get("stop_close_triggered")),
            "pnl_8040_assumed": assumed_8040_pnl(rec),
            "actual_exit_leave80_close": None,
            "pnl_leave80_close": None,
            "pnl_t40bar_close": None,
            "t40_actual_minus_assumed_40": None,
            "t40": None,
        }
        rec["flags"] = universe_flags(rec)
        rec["missing_candles"] = True
        out.append(rec)
    return out


def write_report(summary: dict) -> None:
    u = summary["universes"]
    g = u["GETTABLE_AT_80"]
    a = u["ALL_FIRST80"]
    r = u["RESTABLE_80"]
    h = u["HIGH_FILL"]
    lines = [
        "# NHL FIRST80 — gettable-at-80 and actual available exits",
        "",
        "Research only. Does not change live trading. Does not invent L2.",
        "",
        "Hockey goals reprice in jumps. The 80→40 +1R/−2R number treats a",
        "bid-close cross as a maker fill at 80 and a later ≤40 close as a 40¢ exit.",
        "This page splits **gettable-at-80** from jump-throughs and reports the",
        "**actual printed exit**, not 40.",
        "",
        "```",
        "LIVE EXECUTION = FALSE",
        "CANDLE PATH ≠ ACTUAL FILL",
        "GETTABLE_AT_80 ≠ PROVEN MAKER FILL",
        "```",
        "",
        "GETTABLE_AT_80 = HIGH maker-fill confidence ∩ NBA HIGH_ACCESS",
        f"(jump < {HIGH_ACCESS['max_jump_cents']}¢, close in [80, {HIGH_ACCESS['max_close_cents']}),",
        f"persist ≥ {HIGH_ACCESS['min_persist_78_85']}m in 78–85, ≥ {HIGH_ACCESS['min_up_steps_5m']} up-steps in prior 5m).",
        "Rule was frozen on NBA/NCAAB. Not fit to NHL P&L.",
        "",
        f"n universe (game events) = **{summary['n_universe']}**.",
        "",
        "## 1. Universes",
        "",
        "| Universe | N | % of n universe | Assumed 80→40 EVN | Actual-exit EVN (leave-80 close or settlement) |",
        "|---|---:|---:|---:|---:|",
    ]
    for key, row in (
        ("ALL_FIRST80", a),
        ("HIGH_FILL", h),
        ("NO_JUMP10", u["NO_JUMP10"]),
        ("RESTABLE_80", r),
        ("GETTABLE_AT_80", g),
    ):
        lines.append(
            f"| {key} | {row['n']:,} | {row['pct_of_n_universe']}% | "
            f"{row['assumed_8040']['evn']}¢ | {row['ev_actual_leave80_close']['evn']}¢ |"
        )
    ge = g["actual_exit_when_leaves_80"]["close"]
    gl = g["actual_exit_when_leaves_80"]["low"]
    t40 = g["actual_exit_on_40_trigger_bar"]["close"]
    t40l = g["actual_exit_on_40_trigger_bar"]["low"]
    vs = g["actual_exit_on_40_trigger_bar"]["actual_minus_assumed_40"]
    all_ex = g["all_trade_exits_leave80_or_settlement"]["close"]
    lines.extend(
        [
            "",
            "## 2. GETTABLE_AT_80 — can we actually rest 80?",
            "",
            f"- n = **{g['n']:,}** / {summary['n_universe']:,} games = **{g['pct_of_n_universe']}%** of n universe",
            f"- / {a['n']:,} FIRST-80 = **{g.get('pct_of_first80')}%** of FIRST-80",
            f"- Entry jump mean/median: {g['entry_jump']['mean']} / {g['entry_jump']['median']} ¢",
            f"- Entry close mean/median: {g['entry_close']['mean']} / {g['entry_close']['median']} ¢",
            "",
            "If GETTABLE is a small slice of FIRST-80, most of the raw 80→40 EV",
            "is jump-through path, not a restable 80¢ maker book.",
            "",
            "## 3. Actual exits available (GETTABLE_AT_80) — not 40",
            "",
            "When the path first **leaves 80** (subsequent tradable bid close < 80):",
            "",
            f"- n left 80: **{g['left_80']['k']:,}** ({g['left_80']['pct']}%)",
            f"- mean / median exit **close**: **{ge['mean']} / {ge['median']}** ¢",
            f"- mean / median exit **low**: **{gl['mean']} / {gl['median']}** ¢",
            "",
            "When a later bar **closes ≤ 40** (the old stop trigger), the printed bid is:",
            "",
            f"- n hit 40-close: **{g['hit_40_close']['k']:,}** ({g['hit_40_close']['pct']}%)",
            f"- jumped through 40 (prev close > 40 and this close < 40): **{g['jumped_through_40']['k']:,}** ({g['jumped_through_40']['pct']}%)",
            f"- mean / median actual 40-bar close: **{t40['mean']} / {t40['median']}** ¢  (assumed 40)",
            f"- mean / median actual 40-bar low: **{t40l['mean']} / {t40l['median']}** ¢",
            f"- actual close minus 40: mean / median **{vs['mean']} / {vs['median']}** ¢",
            "",
            "All GETTABLE trades (leave-80 close, else settlement 100/0):",
            "",
            f"- mean / median exit: **{all_ex['mean']} / {all_ex['median']}** ¢",
            "",
            "## 4. EV on GETTABLE using actual exits",
            "",
            "| Model | Gross EV ¢ | EVN ¢ |",
            "|---|---:|---:|",
            f"| Assumed 80→40 (+20/−40) | {g['assumed_8040']['gross_ev']} | {g['assumed_8040']['evn']} |",
            f"| Actual leave-80 close or settlement | {g['ev_actual_leave80_close']['gross_ev']} | {g['ev_actual_leave80_close']['evn']} |",
            f"| Actual leave-80 low or settlement | {g['ev_actual_leave80_low']['gross_ev']} | — |",
            f"| Actual 40-bar close or settlement | {g['ev_actual_t40bar_close']['gross_ev']} | {g['ev_actual_t40bar_close']['evn']} |",
            f"| Actual 40-bar low or settlement | {g['ev_actual_t40bar_low']['gross_ev']} | — |",
            "",
            "Leave-80 EV exits at the first printed bid under 80 (a goal against).",
            "That is harsher than waiting for 40 and is the hockey-honest liquidation",
            "proxy: the book often is not still 79 after the goal.",
            "",
            "40-bar actual EV keeps the old stop *timing* but uses the printed close/low",
            "instead of 40. If that EV is much worse than assumed 80→40, the original",
            "NHL +7.83¢ was a 40¢-fill fiction.",
            "",
            "## 5. What this is not",
            "",
            "- Not a proven maker fill at 80. HIGH_ACCESS + HIGH fill is a candle proxy.",
            "- Not L2, queue, or IOC fill quality.",
            "- Not live FIRST01 / 80/81/83/89.",
            "- Not a production NHL strategy.",
            "",
            "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
            "",
        ]
    )
    text = "\n".join(lines) + "\n"
    for dest in (OUT, REPORTS):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "REPORT.md").write_text(text)


def main() -> int:
    if not CANDS.exists():
        print("missing NHL first80 candidates; run nhl_80_40_execution_audit.py first", flush=True)
        return 1
    raw_cands = json.loads(CANDS.read_text())
    n_universe = len(raw_cands)
    trades = load_first80()
    print(f"n_universe={n_universe} first80={len(trades)}", flush=True)
    trades = attach_all(trades)
    print("scan done", flush=True)

    universes = {}
    for key in ("ALL_FIRST80", "HIGH_FILL", "NO_JUMP10", "RESTABLE_80", "GETTABLE_AT_80"):
        sub = [t for t in trades if t["flags"].get(key)]
        row = summarize(sub, n_universe, key)
        row["pct_of_first80"] = A.rate(len(sub), len(trades))
        universes[key] = row

    summary = {
        "sport": "nhl",
        "series": "KXNHLGAME",
        "season": "2025-2026",
        "n_universe": n_universe,
        "first80": len(trades),
        "high_access_rule": HIGH_ACCESS,
        "live_execution_changed": False,
        "price_interpretation": {
            "gettable_at_80": "HIGH fill confidence AND frozen NBA HIGH_ACCESS. Candle proxy, not a fill.",
            "actual_exit_leave80": "first later tradable yes_bid_close < 80, else settlement 100/0",
            "actual_exit_t40bar": "yes_bid_close/low on first later bar with close<=40, not 40 itself",
            "assumed_8040": "previous NHL report; +20 never-40 / -40 if close<=40",
        },
        "universes": universes,
        "missing_candles": sum(1 for t in trades if t.get("missing_candles")),
    }

    def slim(t):
        f = t.get("entry_features") or {}
        e = t.get("exits") or {}
        return {
            "ticker": t.get("ticker"),
            "game_date": t.get("game_date"),
            "dataset_split": t.get("dataset_split"),
            "maker_fill_confidence": t.get("maker_fill_confidence"),
            "jump_1m_cents": f.get("jump_1m_cents"),
            "p_entry_close_cents": f.get("p_entry_close_cents"),
            "persist_78_85_min": f.get("persist_78_85_min"),
            "accessibility_proxy": f.get("accessibility_proxy"),
            "GETTABLE_AT_80": t["flags"]["GETTABLE_AT_80"],
            "RESTABLE_80": t["flags"]["RESTABLE_80"],
            "left_80": e.get("left_80"),
            "actual_exit_leave80_close": e.get("actual_exit_leave80_close"),
            "actual_exit_t40bar_close": e.get("actual_exit_t40bar_close"),
            "pnl_leave80_close": e.get("pnl_leave80_close"),
            "pnl_t40bar_close": e.get("pnl_t40bar_close"),
            "pnl_8040_assumed": e.get("pnl_8040_assumed"),
            "t40_actual_minus_assumed_40": e.get("t40_actual_minus_assumed_40"),
            "expiration_result_yes": t.get("expiration_result_yes"),
        }

    for dest in (OUT, REPORTS):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        (dest / "ledger.json").write_text(json.dumps([slim(t) for t in trades]) + "\n")
    write_report(summary)

    g = universes["GETTABLE_AT_80"]
    print(
        json.dumps(
            {
                "n_universe": n_universe,
                "first80": len(trades),
                "GETTABLE_AT_80": g["n"],
                "pct_of_n_universe": g["pct_of_n_universe"],
                "pct_of_first80": g["pct_of_first80"],
                "assumed_8040_evn": g["assumed_8040"]["evn"],
                "actual_leave80_evn": g["ev_actual_leave80_close"]["evn"],
                "actual_leave80_exit_mean": g["actual_exit_when_leaves_80"]["close"]["mean"],
                "actual_leave80_exit_median": g["actual_exit_when_leaves_80"]["close"]["median"],
                "actual_t40bar_exit_mean": g["actual_exit_on_40_trigger_bar"]["close"]["mean"],
                "actual_t40bar_exit_median": g["actual_exit_on_40_trigger_bar"]["close"]["median"],
                "actual_t40bar_minus_40_mean": g["actual_exit_on_40_trigger_bar"]["actual_minus_assumed_40"]["mean"],
                "all_exit_mean": g["all_trade_exits_leave80_or_settlement"]["close"]["mean"],
                "all_exit_median": g["all_trade_exits_leave80_or_settlement"]["close"]["median"],
                "RESTABLE_80": universes["RESTABLE_80"]["n"],
                "HIGH_FILL": universes["HIGH_FILL"]["n"],
                "out": str(OUT),
                "live_execution_changed": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
