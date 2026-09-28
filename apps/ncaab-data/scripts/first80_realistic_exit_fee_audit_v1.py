#!/usr/bin/env python3
"""FIRST80_REALISTIC_EXIT_FEE_AUDIT_V1

Read-only measurement of FIRST-80 deterioration exit-price proxies,
jump-through, parameterized fees, and maker-hedge fill *scenarios*.

Does not modify FIRST01, Risk, Execution, Game Path, hedge V1–V4,
frozen candidates, or existing fee_models.py.

LIVE EXECUTION CHANGED: FALSE
CANDLE PATH ≠ ACTUAL FILL
STOP TRIGGER ≠ REALIZED EXIT
GROSS EV ≠ NET EV
"""

from __future__ import annotations

import importlib.util
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

NBA_SCRIPTS = Path("/Users/user/Desktop/Momento/apps/nba-data/scripts")
HERE = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


sys.path.insert(0, str(NBA_SCRIPTS))
import nba_80_40_execution_audit as A  # noqa: E402

V1 = _load("first80_hedge_v1_engine", HERE / "first80_opponent_40_hedge_v1.py")

PROGRAM = "FIRST80_REALISTIC_EXIT_FEE_AUDIT_V1"
ENTRY_CENTS = 80
WIN_CENTS = 20
STOP_IDEAL_CENTS = -40
MISS_CENTS = -80
R_CENTS = 20
SETTLEMENT_FEE_CENTS = 0.0
TAKER_COEF = 0.07
MAKER_COEF = 0.0175
FEE_MULTIPLIER = 1.0

THRESHOLDS = (75, 70, 65, 60, 55, 50, 45, 40, 35, 30, 25, 20, 15, 10, 5)
EXIT_GRID = (40, 35, 30, 25, 20, 15, 10, 5)
FILL_GRID = (0.25, 0.40, 0.50, 0.60, 0.75, 0.90, 1.00)
SPLITS = ("TRAIN", "VALIDATION", "OOS", "FULL")

EXIT_REGIONS = (
    ("40-37", 37, 40),
    ("36-32", 32, 36),
    ("31-27", 27, 31),
    ("26-22", 22, 26),
    ("21-17", 17, 21),
    ("16-12", 12, 16),
    ("11-7", 7, 11),
    ("6-0", 0, 6),
)

GATES = {
    "nba": {"n": 1230, "survivors": 910, "stops": 320, "leaks": 0, "surv_pct": 73.9837},
    "ncaab": {"n": 4099, "survivors": 2998, "stops": 1099, "leaks": 2, "surv_pct": 73.1398},
}

DOCS = Path("/Users/user/Desktop/Momento/docs/research/FIRST80_REALISTIC_EXIT_FEE_AUDIT_V1.md")
DASH_PUBLIC = Path(
    "/Users/user/Desktop/Momento/frontend/first80-realistic-exit-fee-audit-v1/public/data"
)
PHASES = (
    (">180m_to_close", 180, None),
    ("120-180m", 120, 180),
    ("60-120m", 60, 120),
    ("30-60m", 30, 60),
    ("15-30m", 15, 30),
    ("5-15m", 5, 15),
    ("0-5m", 0, 5),
)


def e4_to_cents(v) -> float | None:
    return None if v is None else v / 100.0


def cents_to_e4(c: int) -> int:
    return int(c) * 100


def split_of(s: str | None) -> str:
    if s == "IN_SAMPLE":
        return "TRAIN"
    if s in ("TRAIN", "VALIDATION", "OOS"):
        return s
    return s or "UNSPLIT"


def out_dir(sport: str) -> Path:
    cfg = V1.SPORTS[sport]
    p = cfg["root"] / "derived" / cfg["norm"] / "first80_realistic_exit_fee_audit_v1"
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def write_parquet(path: Path, rows: list[dict]) -> None:
    if not rows:
        pq.write_table(pa.table({"_empty": pa.array([], type=pa.int8())}), path)
        return
    clean = []
    for r in rows:
        c = {}
        for k, v in r.items():
            if isinstance(v, (dict, list, tuple)):
                c[k] = json.dumps(v, default=str)
            elif isinstance(v, bool):
                c[k] = v
            elif isinstance(v, (np.bool_,)):
                c[k] = bool(v)
            elif isinstance(v, (np.integer,)):
                c[k] = int(v)
            elif isinstance(v, (np.floating,)):
                c[k] = float(v)
            else:
                c[k] = v
        clean.append(c)
    keys = {k for r in clean for k in r}
    for k in keys:
        types = {type(r.get(k)) for r in clean if r.get(k) is not None}
        if len(types) > 1:
            for r in clean:
                if r.get(k) is not None:
                    r[k] = str(r[k])
    pq.write_table(pa.Table.from_pylist(clean), path)


def ceil_e6(x: float) -> int:
    return int(math.ceil(x * 1_000_000.0 - 1e-12))


def quadratic_fee_cents(coef: float, contracts: int, price_cents: float, m: float = FEE_MULTIPLIER) -> float:
    """Research estimate of Kalshi quadratic fee. Not a production KalshiFeeModel."""
    if contracts <= 0 or price_cents <= 0:
        return 0.0
    p = price_cents / 100.0
    if p >= 1.0:
        return 0.0
    raw = m * coef * contracts * p * (1.0 - p)
    return ceil_e6(raw) / 10_000.0


def entry_fee_cents(scenario: str) -> float:
    if scenario == "CURRENT":
        return 0.0
    if scenario == "MODERATE":
        return quadratic_fee_cents(MAKER_COEF, 1, ENTRY_CENTS)
    if scenario == "CONSERVATIVE":
        return quadratic_fee_cents(TAKER_COEF, 1, ENTRY_CENTS)
    raise ValueError(scenario)


def taker_exit_fee_cents(exit_cents: float) -> float:
    return quadratic_fee_cents(TAKER_COEF, 1, exit_cents)


def maker_hedge_fee_cents(h_cents: int, scenario: str) -> float:
    if scenario == "CURRENT":
        return 0.0
    if scenario == "MODERATE":
        return quadratic_fee_cents(MAKER_COEF, 1, h_cents)
    if scenario == "CONSERVATIVE":
        return quadratic_fee_cents(MAKER_COEF, 1, h_cents)
    raise ValueError(scenario)


def load_frozen(sport: str) -> list[dict]:
    cfg = V1.SPORTS[sport]
    cands = json.loads(cfg["cands"].read_text())
    trades = [
        dict(c)
        for c in cands
        if c.get("status") == "FIRST_80" and c.get("expiration_result_yes") is not None
    ]
    for t in trades:
        t["sport"] = sport
        t["dataset_split"] = split_of(t.get("dataset_split"))
        t["survived"] = (not t.get("stop_close_triggered")) and bool(t["expiration_result_yes"])
        t["leak"] = (not t.get("stop_close_triggered")) and (not bool(t["expiration_result_yes"]))
        t["stopped"] = bool(t.get("stop_close_triggered"))
    return trades


def reproduce_path(sport: str, trades: list[dict]) -> dict:
    g = GATES[sport]
    n = len(trades)
    surv = sum(1 for t in trades if t["survived"])
    stops = sum(1 for t in trades if t["stopped"])
    leaks = sum(1 for t in trades if t["leak"])
    pct = round(100.0 * surv / n, 4) if n else None
    ok = (
        n == g["n"]
        and surv == g["survivors"]
        and stops == g["stops"]
        and leaks == g["leaks"]
        and pct == g["surv_pct"]
    )
    return {
        "sport": sport,
        "ok": ok,
        "observed": {"n": n, "survivors": surv, "stops": stops, "leaks": leaks, "surv_pct": pct},
        "expected": g,
        "label": "CANDLE PATH — NOT ACTUAL FILL",
    }


def load_ticker_quotes(path: Path) -> list[dict]:
    cols = [
        "end_period_ts",
        "yes_bid_open_e4",
        "yes_bid_high_e4",
        "yes_bid_low_e4",
        "yes_bid_close_e4",
        "yes_ask_close_e4",
        "price_close_e4",
        "volume_hundredths",
        "is_valid",
    ]
    table = pq.read_table(path, columns=cols)
    get = {c: table.column(c) for c in cols}
    rows = []
    for i in range(table.num_rows):
        if not get["is_valid"][i].as_py():
            continue
        rows.append(
            {
                "ts": int(get["end_period_ts"][i].as_py()),
                "bid_o": A._opt_int(get["yes_bid_open_e4"][i].as_py()),
                "bid_h": A._opt_int(get["yes_bid_high_e4"][i].as_py()),
                "bid_l": A._opt_int(get["yes_bid_low_e4"][i].as_py()),
                "bid_c": A._opt_int(get["yes_bid_close_e4"][i].as_py()),
                "ask_c": A._opt_int(get["yes_ask_close_e4"][i].as_py()),
                "px_c": A._opt_int(get["price_close_e4"][i].as_py()),
                "vol": A._opt_int(get["volume_hundredths"][i].as_py()),
            }
        )
    rows.sort(key=lambda r: r["ts"])
    return rows


def subsequent_tradable(
    quotes: list[dict],
    t0: int,
    scan_end: int | None,
    scan_start: int | None = None,
) -> list[dict]:
    """Same post-entry window as frozen 80/40: (t0, min(close_ts, game_window_end)]."""
    out = []
    had_q = True
    for q in quotes:
        if q["ts"] <= t0:
            continue
        if scan_start is not None and q["ts"] < scan_start:
            continue
        if scan_end is not None and q["ts"] > scan_end:
            continue
        if not A.quality(q["bid_c"], q["ask_c"], q["vol"], had_q):
            continue
        had_q = True
        out.append(q)
    return out


def attach_scan_window(rec: dict, game: dict | None) -> None:
    """Reproduce frozen audit window: game_date+16h .. min(close, game_date+52h)."""
    gw_start = gw_end = None
    if game:
        gd = A.parse_game_date(game.get("game_date") or rec.get("game_date"))
        if gd:
            gw_start = int((gd + timedelta(hours=16)).timestamp())
            gw_end = int((gd + timedelta(hours=52)).timestamp())
    close_ts = rec.get("close_ts")
    close_i = int(close_ts) if close_ts is not None else None
    end = close_i
    if end is None:
        end = gw_end
    elif gw_end is not None:
        end = min(end, gw_end)
    rec["scan_window_start"] = gw_start
    rec["scan_window_end"] = end


def jump_class(gap_cents: float | None) -> str:
    if gap_cents is None:
        return "UNKNOWN"
    if gap_cents <= 2:
        return "ORDERLY_TOUCH"
    if gap_cents <= 5:
        return "SMALL_GAP"
    if gap_cents <= 10:
        return "MODERATE_GAP"
    if gap_cents <= 20:
        return "LARGE_GAP"
    return "EXTREME_JUMP_THROUGH"


def reach_class(prev_close: float | None, close_c: float | None, low_c: float | None, thr: int) -> str:
    if close_c is None and (low_c is None or low_c > thr):
        return "NEVER_REACHED"
    if close_c is None or close_c > thr:
        if low_c is not None and low_c <= thr:
            return "TOUCHED"
        return "NEVER_REACHED"
    if prev_close is not None and prev_close > thr and close_c < thr:
        return "JUMPED_THROUGH"
    return "CLOSED_AT_OR_BELOW"


def region_of(price: float | None) -> str | None:
    if price is None:
        return None
    for name, lo, hi in EXIT_REGIONS:
        if lo <= price <= hi:
            return name
    if price > 40:
        return "ABOVE_40"
    return "6-0"


def phase_of(minutes: float | None) -> str:
    if minutes is None:
        return "UNKNOWN"
    for name, lo, hi in PHASES:
        if minutes >= lo and (hi is None or minutes < hi):
            return name
    return "UNKNOWN"


def analyze_a1_path(rec: dict, quotes: list[dict]) -> dict:
    t0 = int(rec["first_80_timestamp"])
    close_i = rec.get("scan_window_end")
    if close_i is None and rec.get("close_ts") is not None:
        close_i = int(rec["close_ts"])
    path = subsequent_tradable(quotes, t0, close_i, rec.get("scan_window_start"))
    entry_q = None
    for q in quotes:
        if q["ts"] == t0:
            entry_q = q
            break

    out: dict = {
        "path_scan": "OK",
        "n_subsequent_tradable": len(path),
        "entry_close_cents": e4_to_cents(rec.get("entry_bid_close_e4")),
        "entry_high_cents": e4_to_cents(rec.get("entry_bid_high_e4")),
        "entry_low_cents": e4_to_cents(rec.get("entry_bid_low_e4")),
        "minutes_to_close_at_entry": None
        if close_i is None
        else round((close_i - t0) / 60.0, 4),
    }
    if entry_q and out["entry_close_cents"] is None:
        out["entry_close_cents"] = e4_to_cents(entry_q["bid_c"])
        out["entry_high_cents"] = e4_to_cents(entry_q["bid_h"])
        out["entry_low_cents"] = e4_to_cents(entry_q["bid_l"])

    first_close: dict[int, dict] = {}
    first_low: dict[int, dict] = {}
    prev = None
    for q in path:
        close_c = e4_to_cents(q["bid_c"])
        low_c = e4_to_cents(q["bid_l"])
        prev_c = e4_to_cents(prev["bid_c"]) if prev is not None else None
        for thr in THRESHOLDS:
            if thr not in first_low and low_c is not None and low_c <= thr:
                first_low[thr] = {"q": q, "prev_close": prev_c}
            if thr not in first_close and close_c is not None and close_c <= thr:
                first_close[thr] = {"q": q, "prev_close": prev_c}
        prev = q

    for thr in THRESHOLDS:
        fc = first_close.get(thr)
        fl = first_low.get(thr)
        close_c = e4_to_cents(fc["q"]["bid_c"]) if fc else None
        low_c = e4_to_cents(fl["q"]["bid_l"]) if fl else None
        prev_c = fc["prev_close"] if fc else (fl["prev_close"] if fl else None)
        cls = reach_class(prev_c, close_c, low_c, thr)
        out[f"first_{thr}_close_ts"] = None if fc is None else fc["q"]["ts"]
        out[f"first_{thr}_low_ts"] = None if fl is None else fl["q"]["ts"]
        out[f"first_{thr}_reach_class"] = cls
        if fc:
            q = fc["q"]
            out[f"first_{thr}_close_cents"] = e4_to_cents(q["bid_c"])
            out[f"first_{thr}_low_cents"] = e4_to_cents(q["bid_l"])
            out[f"first_{thr}_high_cents"] = e4_to_cents(q["bid_h"])
            out[f"first_{thr}_ask_cents"] = e4_to_cents(q["ask_c"])
            out[f"first_{thr}_prev_close_cents"] = fc["prev_close"]
            gap_close = None if fc["prev_close"] is None or close_c is None else fc["prev_close"] - close_c
            gap_low = None if fc["prev_close"] is None or e4_to_cents(q["bid_l"]) is None else fc["prev_close"] - e4_to_cents(q["bid_l"])
            out[f"first_{thr}_jump_close"] = gap_close
            out[f"first_{thr}_jump_low"] = gap_low
            out[f"first_{thr}_jump_class"] = jump_class(gap_close)
            out[f"first_{thr}_minutes_to_close"] = (
                None if close_i is None else round((close_i - q["ts"]) / 60.0, 4)
            )

    # Model A/B/C at the frozen 40 close-stop (and independently rescanned 40)
    fc40 = first_close.get(40)
    out["rescanned_stop_close"] = fc40 is not None
    out["rescanned_first_40_close_ts"] = None if fc40 is None else fc40["q"]["ts"]
    if fc40:
        q = fc40["q"]
        close_c = e4_to_cents(q["bid_c"])
        low_c = e4_to_cents(q["bid_l"])
        out["trigger_candle_close"] = close_c
        out["trigger_candle_low"] = low_c
        out["trigger_candle_high"] = e4_to_cents(q["bid_h"])
        out["previous_candle_close"] = fc40["prev_close"]
        out["jump_through_amount"] = out.get("first_40_jump_close")
        out["idealized_exit_price"] = 40.0
        out["moderate_exit_proxy"] = close_c
        out["conservative_exit_proxy"] = low_c if low_c is not None else close_c
        out["exit_region_moderate"] = region_of(close_c)
        out["exit_region_conservative"] = region_of(out["conservative_exit_proxy"])
    else:
        out["trigger_candle_close"] = None
        out["trigger_candle_low"] = None
        out["trigger_candle_high"] = None
        out["previous_candle_close"] = None
        out["jump_through_amount"] = None
        out["idealized_exit_price"] = None
        out["moderate_exit_proxy"] = None
        out["conservative_exit_proxy"] = None
        out["exit_region_moderate"] = "NO_EXIT_HOLD_TO_SETTLEMENT"
        out["exit_region_conservative"] = "NO_EXIT_HOLD_TO_SETTLEMENT"

    # Jump-from-above-40 diagnostics on the 40 trigger candle
    if fc40:
        prev_c = fc40["prev_close"]
        close_c = e4_to_cents(fc40["q"]["bid_c"])
        out["from_above_40_to_below_35"] = bool(prev_c is not None and prev_c > 40 and close_c is not None and close_c < 35)
        out["from_above_40_to_below_30"] = bool(prev_c is not None and prev_c > 40 and close_c is not None and close_c < 30)
        out["from_above_40_to_below_20"] = bool(prev_c is not None and prev_c > 40 and close_c is not None and close_c < 20)
        out["touch_40_close_above"] = out.get("first_40_reach_class") == "TOUCHED"
        out["close_directly_at_or_below_40"] = out.get("first_40_reach_class") == "CLOSED_AT_OR_BELOW"
        out["jumped_through_40"] = out.get("first_40_reach_class") == "JUMPED_THROUGH"
    else:
        out["from_above_40_to_below_35"] = False
        out["from_above_40_to_below_30"] = False
        out["from_above_40_to_below_20"] = False
        out["touch_40_close_above"] = out.get("first_40_reach_class") == "TOUCHED"
        out["close_directly_at_or_below_40"] = False
        out["jumped_through_40"] = False
    return out


def analyze_a2_path(rec: dict, quotes: list[dict]) -> dict:
    t0 = int(rec["first_80_timestamp"])
    close_i = rec.get("scan_window_end")
    if close_i is None and rec.get("close_ts") is not None:
        close_i = int(rec["close_ts"])
    a1_stop_ts = rec.get("rescanned_first_40_close_ts") or rec.get("first_40_close_ts")
    path = subsequent_tradable(quotes, t0, close_i, rec.get("scan_window_start"))
    max_res = None
    max_before_stop = None
    first_h: dict[int, int] = {}
    first_h_before_stop: dict[int, int] = {}
    already_ge: dict[int, int] = {}
    prev = None
    for q in path:
        c = e4_to_cents(q["bid_c"])
        if c is None:
            continue
        if max_res is None or c > max_res:
            max_res = c
        before_stop = a1_stop_ts is None or q["ts"] <= int(a1_stop_ts)
        if before_stop and (max_before_stop is None or c > max_before_stop):
            max_before_stop = c
        prev_c = e4_to_cents(prev["bid_c"]) if prev is not None else None
        for h in EXIT_GRID:
            up_cross = prev_c is not None and prev_c < h <= c
            if h not in already_ge and prev_c is None and c >= h:
                already_ge[h] = q["ts"]
            if up_cross:
                if h not in first_h:
                    first_h[h] = q["ts"]
                if before_stop and h not in first_h_before_stop:
                    first_h_before_stop[h] = q["ts"]
        prev = q
    out = {
        "a2_path_scan": "OK",
        "a2_max_price": max_res,
        "a2_max_before_a1_stop": max_before_stop,
        "a2_n_subsequent_tradable": len(path),
        "a2_opportunity_definition": "UP_CROSS_AFTER_T0 — A2 close crosses H from below. NOT a fill. Already-at-or-above on first print is NOT a maker-H fill.",
    }
    for h in EXIT_GRID:
        out[f"hedge_{h}_opportunity"] = h in first_h_before_stop
        out[f"hedge_{h}_opportunity_any"] = h in first_h
        out[f"hedge_{h}_already_ge_first_print"] = h in already_ge
        out[f"hedge_{h}_ts"] = first_h_before_stop.get(h)
    return out


def attach_paths(sport: str, trades: list[dict], games: dict) -> dict:
    cfg = V1.SPORTS[sport]
    candles = cfg["root"] / "normalized" / cfg["norm"] / "candles_1m"
    by_t = {t["ticker"]: t for t in trades if t.get("ticker")}
    opp_to_recs: dict[str, list[dict]] = defaultdict(list)
    missing_game = 0
    missing_opp = 0
    for rec in trades:
        rec["opponent_ticker"] = None
        rec["opponent_available"] = False
        g = games.get(rec.get("event_id"))
        attach_scan_window(rec, g)
        if not g:
            rec["opponent_status"] = "GAME_MISSING"
            missing_game += 1
            continue
        opp = V1.opponent_of(g, rec["ticker"])
        if not opp:
            rec["opponent_status"] = "OPPONENT_UNAVAILABLE"
            missing_opp += 1
            continue
        rec["opponent_ticker"] = opp
        rec["opponent_available"] = True
        rec["opponent_status"] = "OK"
        opp_to_recs[opp].append(rec)

    needed = set(by_t) | set(opp_to_recs)
    files = [p for p in candles.rglob("*.parquet") if p.stem in needed]
    scanned_a1 = set()
    scanned_a2 = set()
    print(f"  candle files {len(files)} / needed {len(needed)}", flush=True)
    for n_file, path in enumerate(files, 1):
        if n_file % 400 == 0 or n_file == 1 or n_file == len(files):
            print(f"  scan {n_file}/{len(files)}", flush=True)
        quotes = load_ticker_quotes(path)
        stem = path.stem
        if stem in by_t:
            rec = by_t[stem]
            rec.update(analyze_a1_path(rec, quotes))
            scanned_a1.add(stem)
        if stem in opp_to_recs:
            for rec in opp_to_recs[stem]:
                rec.update(analyze_a2_path(rec, quotes))
            scanned_a2.add(stem)

    missing_a1 = [t["ticker"] for t in trades if t["ticker"] not in scanned_a1]
    for t in trades:
        if t["ticker"] not in scanned_a1:
            t["path_scan"] = "MISSING_CANDLES"
        if t.get("opponent_available") and t.get("a2_path_scan") != "OK":
            t["a2_path_scan"] = "MISSING_CANDLES"
            t["a2_max_price"] = None
            for h in EXIT_GRID:
                t[f"hedge_{h}_opportunity"] = False
                t[f"hedge_{h}_opportunity_any"] = False
        if not t.get("opponent_available"):
            t["a2_max_price"] = None
            for h in EXIT_GRID:
                t[f"hedge_{h}_opportunity"] = False
                t[f"hedge_{h}_opportunity_any"] = False
    return {
        "files": len(files),
        "needed": len(needed),
        "scanned_a1": len(scanned_a1),
        "scanned_a2": len(scanned_a2),
        "missing_a1": missing_a1,
        "missing_game": missing_game,
        "missing_opp": missing_opp,
    }


def reproduce_stop_model(sport: str, trades: list[dict]) -> dict:
    n = len(trades)
    missing = [t["ticker"] for t in trades if t.get("path_scan") != "OK"]
    mismatch = []
    for t in trades:
        if t.get("path_scan") != "OK":
            continue
        frozen = bool(t.get("stop_close_triggered"))
        rescanned = bool(t.get("rescanned_stop_close"))
        if frozen != rescanned:
            mismatch.append(t["ticker"])
    ok = len(missing) == 0 and len(mismatch) == 0
    return {
        "sport": sport,
        "ok": ok,
        "n": n,
        "missing_candles": len(missing),
        "stop_flag_mismatches": len(mismatch),
        "mismatch_tickers": mismatch[:20],
        "definition": "first subsequent tradable yes_bid_close ≤ 40¢ (frozen Model A)",
        "label": "CANDLE PATH — NOT ACTUAL FILL",
    }


def pctile(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    return float(np.percentile(np.array(xs, dtype=float), p))


def risk_stats(pnls: list[float]) -> dict:
    if not pnls:
        return {"n": 0}
    a = np.array(pnls, dtype=float)
    n = int(a.size)
    mean = float(a.mean())
    median = float(np.median(a))
    std = float(a.std(ddof=1)) if n > 1 else 0.0
    downs = a[a < 0]
    dd = float(np.sqrt(np.mean(np.square(downs)))) if downs.size else 0.0
    wins = a[a > 0]
    losses = a[a < 0]
    zeros = a[a == 0]
    sum_w = float(wins.sum()) if wins.size else 0.0
    sum_l = float(abs(losses.sum())) if losses.size else 0.0
    worst_n = max(1, int(math.ceil(0.05 * n)))
    es = float(np.sort(a)[:worst_n].mean())
    return {
        "n": n,
        "mean": round(mean, 4),
        "median": round(median, 4),
        "std": round(std, 4),
        "downside_deviation": round(dd, 4),
        "sharpe_style": None if std == 0 else round(mean / std, 4),
        "sortino_style": None if dd == 0 else round(mean / dd, 4),
        "max_single_trade_loss": round(float(a.min()), 4),
        "loss_frequency": round(100.0 * losses.size / n, 4),
        "average_loss": None if losses.size == 0 else round(float(losses.mean()), 4),
        "average_win": None if wins.size == 0 else round(float(wins.mean()), 4),
        "profit_factor": None if sum_l == 0 else round(sum_w / sum_l, 4),
        "expected_shortfall_5pct": round(es, 4),
        "n_win": int(wins.size),
        "n_loss": int(losses.size),
        "n_flat": int(zeros.size),
        "note": "Per-trade P&L moments. Not annualized. Discrete payoff distribution.",
    }


def hold_gross(t: dict) -> float:
    return WIN_CENTS if t["expiration_result_yes"] else MISS_CENTS


def model_a_gross(t: dict) -> float:
    if t.get("rescanned_stop_close") or t.get("stopped"):
        return STOP_IDEAL_CENTS
    if t["expiration_result_yes"]:
        return WIN_CENTS
    return 0.0


def exit_gross(exit_px: float) -> float:
    return exit_px - ENTRY_CENTS


def net_from_parts(gross: float, entry_fee: float, extra_fee: float) -> float:
    return gross - entry_fee - extra_fee - SETTLEMENT_FEE_CENTS


def triggered_at(t: dict, thr: int) -> bool:
    return t.get(f"first_{thr}_close_ts") is not None


def exit_px_for(t: dict, thr: int, mode: str) -> float | None:
    if not triggered_at(t, thr):
        return None
    if mode == "ideal":
        return float(thr)
    if mode == "moderate":
        return t.get(f"first_{thr}_close_cents")
    if mode == "conservative":
        low = t.get(f"first_{thr}_low_cents")
        close = t.get(f"first_{thr}_close_cents")
        return low if low is not None else close
    raise ValueError(mode)


def trade_taker_pnl(t: dict, thr: int, mode: str, fee_scenario: str) -> tuple[float, float, float, float]:
    """Return (gross, entry_fee, exit_fee, net). Hold if not triggered."""
    ef = entry_fee_cents(fee_scenario)
    px = exit_px_for(t, thr, mode)
    if px is None:
        g = hold_gross(t)
        if t.get("leak"):
            g = 0.0 if mode == "ideal" and thr == 40 else hold_gross(t)
        # Frozen Model A treats leaks as 0. For other triggers, unsettled-no-stop is hold.
        if mode == "ideal" and thr == 40 and t.get("leak"):
            g = 0.0
        return g, ef, 0.0, net_from_parts(g, ef, 0.0)
    xf = taker_exit_fee_cents(px)
    g = exit_gross(px)
    return g, ef, xf, net_from_parts(g, ef, xf)


def summarize_pnls(trades: list[dict], pnls: list[float], fees: list[float], labels: dict) -> dict:
    ev = float(np.mean(pnls)) if pnls else None
    fee = float(np.mean(fees)) if fees else None
    return {
        **labels,
        "n": len(trades),
        "gross_or_net_mean": None if ev is None else round(ev, 4),
        "mean_fees": None if fee is None else round(fee, 4),
        "ev_r": None if ev is None else round(ev / R_CENTS, 4),
        "risk": risk_stats(pnls),
    }


def strategy_taker(trades: list[dict], thr: int, mode: str, fee_scenario: str) -> dict:
    grosses, nets, fees, durs, exits = [], [], [], [], []
    n_trig = 0
    for t in trades:
        g, ef, xf, net = trade_taker_pnl(t, thr, mode, fee_scenario)
        grosses.append(g)
        nets.append(net)
        fees.append(ef + xf)
        if triggered_at(t, thr):
            n_trig += 1
            px = exit_px_for(t, thr, mode)
            if px is not None:
                exits.append(px)
            ts = t.get(f"first_{thr}_close_ts")
            if ts and t.get("first_80_timestamp"):
                durs.append((int(ts) - int(t["first_80_timestamp"])) / 60.0)
        elif t.get("close_ts") and t.get("first_80_timestamp"):
            durs.append((int(t["close_ts"]) - int(t["first_80_timestamp"])) / 60.0)
    ev_g = float(np.mean(grosses)) if grosses else None
    ev_n = float(np.mean(nets)) if nets else None
    return {
        "trigger": thr,
        "mode": mode,
        "fee_scenario": fee_scenario,
        "n": len(trades),
        "triggered": n_trig,
        "trigger_pct": None if not trades else round(100.0 * n_trig / len(trades), 4),
        "mean_exit_proxy": None if not exits else round(float(np.mean(exits)), 4),
        "median_exit_proxy": None if not exits else round(float(np.median(exits)), 4),
        "gross_ev": None if ev_g is None else round(ev_g, 4),
        "mean_fees": round(float(np.mean(fees)), 4) if fees else None,
        "net_ev": None if ev_n is None else round(ev_n, 4),
        "max_realized_loss_proxy": None if not nets else round(float(min(nets)), 4),
        "mean_duration_min": None if not durs else round(float(np.mean(durs)), 4),
        "risk": risk_stats(nets),
        "label": "CANDLE_EXECUTION_PROXY" if mode != "ideal" else "IDEALIZED_TRIGGER_PRICE",
        "status": "MEASURED" if mode != "ideal" else "BENCHMARK",
    }


def frontier_table(trades: list[dict]) -> list[dict]:
    rows = []
    for thr in EXIT_GRID:
        ideal = strategy_taker(trades, thr, "ideal", "CURRENT")
        mod = strategy_taker(trades, thr, "moderate", "CURRENT")
        con = strategy_taker(trades, thr, "conservative", "CONSERVATIVE")
        rows.append(
            {
                "trigger": thr,
                "trigger_pct": mod["trigger_pct"],
                "triggered": mod["triggered"],
                "mean_exit_moderate": mod["mean_exit_proxy"],
                "median_exit_moderate": mod["median_exit_proxy"],
                "mean_exit_conservative": con["mean_exit_proxy"],
                "gross_ev_ideal": ideal["gross_ev"],
                "gross_ev_moderate": mod["gross_ev"],
                "fees_moderate": mod["mean_fees"],
                "fees_conservative": con["mean_fees"],
                "net_ev_moderate": mod["net_ev"],
                "net_ev_conservative": con["net_ev"],
                "max_loss_moderate": mod["max_realized_loss_proxy"],
                "mean_duration_min": mod["mean_duration_min"],
                "sharpe_style_moderate": (mod.get("risk") or {}).get("sharpe_style"),
            }
        )
    return rows


def select_trigger(val_rows: list[dict]) -> dict:
    ranked = sorted(
        val_rows,
        key=lambda r: (
            r["net_ev_moderate"] is None,
            -(r["net_ev_moderate"] or -999),
            -r["trigger"],
        ),
    )
    pick = ranked[0]
    return {
        "selected_on": "VALIDATION",
        "metric": "net_ev_moderate (CURRENT fees, Model B close proxy)",
        "trigger": pick["trigger"],
        "val_net_ev_moderate": pick["net_ev_moderate"],
        "oos_selection": False,
    }


def fee_grid_table() -> list[dict]:
    rows = []
    for px in EXIT_GRID:
        xf = taker_exit_fee_cents(px)
        for scen, name in (("CURRENT", "current"), ("MODERATE", "moderate"), ("CONSERVATIVE", "conservative")):
            ef = entry_fee_cents(scen)
            g = exit_gross(px)
            rows.append(
                {
                    "exit_price": px,
                    "fee_scenario": scen,
                    "taker_fee": round(xf, 4),
                    "entry_fee": round(ef, 4),
                    "settlement_fee": SETTLEMENT_FEE_CENTS,
                    "gross_exit_pnl": g,
                    "net_exit_pnl": round(net_from_parts(g, ef, xf), 4),
                }
            )
    win_rows = []
    for scen in ("CURRENT", "MODERATE", "CONSERVATIVE"):
        ef = entry_fee_cents(scen)
        win_rows.append(
            {
                "outcome": "SETTLEMENT_YES",
                "fee_scenario": scen,
                "entry_fee": round(ef, 4),
                "settlement_fee": SETTLEMENT_FEE_CENTS,
                "gross_pnl": WIN_CENTS,
                "net_pnl": round(WIN_CENTS - ef - SETTLEMENT_FEE_CENTS, 4),
            }
        )
    return rows, win_rows


def exit_distribution(trades: list[dict], field: str) -> dict:
    n = len(trades)
    triggered = [t for t in trades if t.get("rescanned_stop_close")]
    nt = len(triggered)
    buckets = []
    for name, lo, hi in EXIT_REGIONS:
        k = sum(1 for t in triggered if t.get(field) is not None and lo <= t[field] <= hi)
        buckets.append(
            {
                "region": name,
                "count": k,
                "pct_all": None if n == 0 else round(100.0 * k / n, 4),
                "pct_triggered": None if nt == 0 else round(100.0 * k / nt, 4),
            }
        )
    hold_n = n - nt
    buckets.append(
        {
            "region": "No deterioration exit",
            "count": hold_n,
            "pct_all": None if n == 0 else round(100.0 * hold_n / n, 4),
            "pct_triggered": None,
        }
    )
    thresh = []
    for thr in EXIT_GRID:
        k = sum(1 for t in trades if triggered_at(t, thr))
        thresh.append(
            {
                "exit_price": thr,
                "trigger_count": k,
                "trigger_probability": None if n == 0 else round(100.0 * k / n, 4),
            }
        )
    return {
        "n": n,
        "triggered": nt,
        "proxy_field": field,
        "label": "REALIZED EXIT PRICE PROXY DISTRIBUTION" if "proxy" in field or field.endswith("close") else field,
        "regions": buckets,
        "threshold_trigger_distribution": thresh,
    }


def jump_stats(trades: list[dict]) -> dict:
    triggered = [t for t in trades if t.get("rescanned_stop_close")]
    gaps = [t["jump_through_amount"] for t in triggered if t.get("jump_through_amount") is not None]
    lows = [t["first_40_jump_low"] for t in triggered if t.get("first_40_jump_low") is not None]
    by_cls = defaultdict(int)
    for t in triggered:
        by_cls[t.get("first_40_jump_class") or "UNKNOWN"] += 1
    n = len(triggered)

    def rate(key):
        k = sum(1 for t in triggered if t.get(key))
        return {"k": k, "pct": None if n == 0 else round(100.0 * k / n, 4)}

    by_phase = []
    for name, _, _ in PHASES:
        sub = [t for t in triggered if phase_of(t.get("first_40_minutes_to_close")) == name]
        gs = [t["jump_through_amount"] for t in sub if t.get("jump_through_amount") is not None]
        by_phase.append(
            {
                "phase": name,
                "n": len(sub),
                "median_jump": None if not gs else round(float(np.median(gs)), 4),
                "p90_jump": None if not gs else round(pctile(gs, 90), 4),
            }
        )
    by_term = []
    for label, pred in (
        ("eventual_yes", lambda t: bool(t["expiration_result_yes"])),
        ("eventual_no", lambda t: not bool(t["expiration_result_yes"])),
    ):
        sub = [t for t in triggered if pred(t)]
        gs = [t["jump_through_amount"] for t in sub if t.get("jump_through_amount") is not None]
        by_term.append(
            {
                "terminal": label,
                "n": len(sub),
                "median_jump": None if not gs else round(float(np.median(gs)), 4),
                "p90_jump": None if not gs else round(pctile(gs, 90), 4),
                "mean_exit_moderate": None
                if not sub
                else round(
                    float(np.mean([t["moderate_exit_proxy"] for t in sub if t.get("moderate_exit_proxy") is not None])),
                    4,
                ),
            }
        )
    wick_only = sum(1 for t in trades if t.get("first_40_reach_class") == "TOUCHED")
    return {
        "n_triggered": n,
        "n_all": len(trades),
        "wick_only_touch_40_close_above": {
            "k": wick_only,
            "pct_all": None if not trades else round(100.0 * wick_only / len(trades), 4),
        },
        "orderly_or_class_counts": dict(by_cls),
        "touch_40_close_above": rate("touch_40_close_above"),
        "close_directly_at_or_below_40": rate("close_directly_at_or_below_40"),
        "jumped_through_40": rate("jumped_through_40"),
        "from_above_40_to_below_35": rate("from_above_40_to_below_35"),
        "from_above_40_to_below_30": rate("from_above_40_to_below_30"),
        "from_above_40_to_below_20": rate("from_above_40_to_below_20"),
        "jump_close": {
            "n": len(gaps),
            "median": None if not gaps else round(float(np.median(gaps)), 4),
            "p75": None if not gaps else round(pctile(gaps, 75), 4),
            "p90": None if not gaps else round(pctile(gaps, 90), 4),
            "p95": None if not gaps else round(pctile(gaps, 95), 4),
            "worst": None if not gaps else round(float(max(gaps)), 4),
            "mean": None if not gaps else round(float(np.mean(gaps)), 4),
        },
        "jump_low": {
            "n": len(lows),
            "median": None if not lows else round(float(np.median(lows)), 4),
            "p90": None if not lows else round(pctile(lows, 90), 4),
            "worst": None if not lows else round(float(max(lows)), 4),
        },
        "by_minutes_to_close": by_phase,
        "by_terminal_outcome": by_term,
        "label": "CANDLE GAP — NOT L2 JUMP",
    }


def hedge_opportunity_table(trades: list[dict]) -> dict:
    n = len(trades)
    avail = [t for t in trades if t.get("opponent_available")]
    rows = []
    for h in EXIT_GRID:
        k_any = sum(1 for t in trades if t.get(f"hedge_{h}_opportunity_any"))
        k_before = sum(1 for t in trades if t.get(f"hedge_{h}_opportunity"))
        win = sum(1 for t in trades if t.get(f"hedge_{h}_opportunity") and t["expiration_result_yes"])
        lose = sum(1 for t in trades if t.get(f"hedge_{h}_opportunity") and not t["expiration_result_yes"])
        rows.append(
            {
                "H": h,
                "a2_reaches_before_resolution": k_any,
                "pct_resolution": None if n == 0 else round(100.0 * k_any / n, 4),
                "a2_reaches_before_a1_stop": k_before,
                "pct_before_stop": None if n == 0 else round(100.0 * k_before / n, 4),
                "reaches_and_a1_wins": win,
                "p_reaches_and_a1_wins": None if n == 0 else round(100.0 * win / n, 4),
                "reaches_and_a1_loses": lose,
                "p_reaches_and_a1_loses": None if n == 0 else round(100.0 * lose / n, 4),
                "false_hedge_share_of_opps": None if k_before == 0 else round(100.0 * win / k_before, 4),
            }
        )
    max_rows = []
    for h in EXIT_GRID:
        k = sum(1 for t in trades if (t.get("a2_max_price") or -1) >= h)
        max_rows.append({"max_a2_ge": h, "count": k, "pct": None if n == 0 else round(100.0 * k / n, 4)})
    return {
        "n": n,
        "opponent_available": len(avail),
        "missing_opponent": n - len(avail),
        "by_H": rows,
        "max_a2_before_resolution": max_rows,
        "label": "HEDGE OPPORTUNITY — NOT ACTUAL MAKER FILL",
    }


def unhedged_net(t: dict, fee_scenario: str) -> float:
    _g, _ef, _xf, net = trade_taker_pnl(t, 40, "ideal", fee_scenario)
    return net


def lock_gross(h: int) -> float:
    return float(100 - ENTRY_CENTS - h)


def lock_net(h: int, fee_scenario: str) -> float:
    return lock_gross(h) - entry_fee_cents(fee_scenario) - maker_hedge_fee_cents(h, fee_scenario) - SETTLEMENT_FEE_CENTS


def hedge_ev(trades: list[dict], h: int, p_fill: float, fee_scenario: str) -> dict:
    """Deterministic mixture: opportunity → p*lock + (1-p)*unhedged; else unhedged.

    FILL SCENARIO. Not a measured fill rate.
    """
    pnls = []
    fees = []
    n_opp = 0
    for t in trades:
        u = unhedged_net(t, fee_scenario)
        ef = entry_fee_cents(fee_scenario)
        if t.get(f"hedge_{h}_opportunity"):
            n_opp += 1
            ln = lock_net(h, fee_scenario)
            ev = p_fill * ln + (1.0 - p_fill) * u
            fee = ef + p_fill * maker_hedge_fee_cents(h, fee_scenario)
            if not t.get("rescanned_stop_close") and not t.get("stopped"):
                # unhedged path may have 0 exit fee; mixture uses expected hedge fee only
                pass
            else:
                # unhedged pays taker stop fee with probability 1-p
                fee = ef + p_fill * maker_hedge_fee_cents(h, fee_scenario) + (1.0 - p_fill) * taker_exit_fee_cents(40)
        else:
            ev = u
            _g, ef2, xf, _n = trade_taker_pnl(t, 40, "ideal", fee_scenario)
            fee = ef2 + xf
        pnls.append(ev)
        fees.append(fee)
    return {
        "H": h,
        "p_fill": p_fill,
        "fee_scenario": fee_scenario,
        "n": len(trades),
        "opportunities": n_opp,
        "opportunity_pct": None if not trades else round(100.0 * n_opp / len(trades), 4),
        "lock_gross": lock_gross(h),
        "lock_net": round(lock_net(h, fee_scenario), 4),
        "entry_fee": entry_fee_cents(fee_scenario),
        "hedge_fee": maker_hedge_fee_cents(h, fee_scenario),
        "settlement_fee": SETTLEMENT_FEE_CENTS,
        "net_ev": round(float(np.mean(pnls)), 4) if pnls else None,
        "mean_fees": round(float(np.mean(fees)), 4) if fees else None,
        "risk": risk_stats(pnls),
        "label": "MAKER FILL SCENARIO — NOT ACTUAL FILL",
        "capital_initial": ENTRY_CENTS,
        "capital_reserved_if_filled": ENTRY_CENTS + h,
    }


def hedge_fee_table() -> list[dict]:
    rows = []
    for h in EXIT_GRID:
        for scen in ("CURRENT", "MODERATE", "CONSERVATIVE"):
            rows.append(
                {
                    "hedge_price": h,
                    "fee_scenario": scen,
                    "entry_fee": entry_fee_cents(scen),
                    "hedge_fee": maker_hedge_fee_cents(h, scen),
                    "settlement_fee": SETTLEMENT_FEE_CENTS,
                    "lock_gross": lock_gross(h),
                    "lock_net": round(lock_net(h, scen), 4),
                    "paired_cost": ENTRY_CENTS + h,
                }
            )
    return rows


def capital_row(name: str, ev: float | None, initial: float, reserved: float) -> dict:
    return {
        "strategy": name,
        "ev_per_contract": ev,
        "initial_notional": initial,
        "maximum_capital_commitment": reserved,
        "ev_per_dollar_deployed": None if ev is None else round(ev / initial, 6),
        "ev_per_reserved_capital": None if ev is None else round(ev / reserved, 6),
        "note": "INITIAL NOTIONAL ≠ MAXIMUM CAPITAL COMMITMENT",
    }


def subset(trades: list[dict], split: str) -> list[dict]:
    if split == "FULL":
        return trades
    return [t for t in trades if t.get("dataset_split") == split]


def hold_strategy(trades: list[dict], fee_scenario: str) -> dict:
    pnls = []
    fees = []
    for t in trades:
        ef = entry_fee_cents(fee_scenario)
        g = hold_gross(t)
        pnls.append(net_from_parts(g, ef, 0.0))
        fees.append(ef)
    return {
        "strategy": "HOLD",
        "fee_scenario": fee_scenario,
        "n": len(trades),
        "gross_ev": round(float(np.mean([hold_gross(t) for t in trades])), 4) if trades else None,
        "mean_fees": round(float(np.mean(fees)), 4) if fees else None,
        "net_ev": round(float(np.mean(pnls)), 4) if pnls else None,
        "risk": risk_stats(pnls),
        "label": "HOLD TO SETTLEMENT",
    }


def master_row(name: str, gross, entry_fees, extra_fees, net, mod=None, con=None) -> dict:
    return {
        "strategy": name,
        "gross_ev": gross,
        "entry_fees": entry_fees,
        "exit_or_hedge_fees": extra_fees,
        "net_ev": net,
        "moderate_net_ev": mod,
        "conservative_net_ev": con,
    }


def build_ledgers(trades: list[dict]) -> list[dict]:
    rows = []
    for t in trades:
        g, ef, xf, net = trade_taker_pnl(t, 40, "moderate", "CURRENT")
        cg, cef, cxf, cnet = trade_taker_pnl(t, 40, "conservative", "CONSERVATIVE")
        ig, ief, ixf, inet = trade_taker_pnl(t, 40, "ideal", "CURRENT")
        row = {
            "sport": t["sport"],
            "ticker": t.get("ticker"),
            "event_id": t.get("event_id"),
            "dataset_split": t.get("dataset_split"),
            "entry_timestamp": t.get("first_80_timestamp"),
            "entry_price": ENTRY_CENTS,
            "entry_close": t.get("entry_close_cents"),
            "entry_high": t.get("entry_high_cents"),
            "entry_low": t.get("entry_low_cents"),
            "terminal_outcome": "YES" if t["expiration_result_yes"] else "NO",
            "survived": t["survived"],
            "stopped_frozen": t["stopped"],
            "rescanned_stop_close": t.get("rescanned_stop_close"),
            "first_40_timestamp": t.get("first_40_close_ts"),
            "first_35_timestamp": t.get("first_35_close_ts"),
            "first_30_timestamp": t.get("first_30_close_ts"),
            "first_25_timestamp": t.get("first_25_close_ts"),
            "first_20_timestamp": t.get("first_20_close_ts"),
            "first_15_timestamp": t.get("first_15_close_ts"),
            "first_10_timestamp": t.get("first_10_close_ts"),
            "first_5_timestamp": t.get("first_5_close_ts"),
            "trigger_candle_close": t.get("trigger_candle_close"),
            "trigger_candle_low": t.get("trigger_candle_low"),
            "previous_candle_close": t.get("previous_candle_close"),
            "jump_through_amount": t.get("jump_through_amount"),
            "idealized_exit_price": t.get("idealized_exit_price"),
            "moderate_exit_proxy": t.get("moderate_exit_proxy"),
            "conservative_exit_proxy": t.get("conservative_exit_proxy"),
            "entry_fee": ef,
            "taker_exit_fee": xf,
            "gross_pnl": g,
            "net_pnl": net,
            "conservative_net_pnl": cnet,
            "ideal_net_pnl": inet,
            "a2_hedge_opportunity": bool(t.get("hedge_40_opportunity")),
            "a2_max_price": t.get("a2_max_price"),
            "hedge_fill_probability_scenario": "ASSUMED_NOT_MEASURED",
            "hedge_fee": 0.0,
            "hedge_gross_pnl": lock_gross(40) if t.get("hedge_40_opportunity") else None,
            "hedge_net_pnl": lock_net(40, "CURRENT") if t.get("hedge_40_opportunity") else None,
            "path_scan": t.get("path_scan"),
            "opponent_status": t.get("opponent_status"),
        }
        for h in EXIT_GRID:
            row[f"hedge_{h}_opportunity"] = bool(t.get(f"hedge_{h}_opportunity"))
        for thr in THRESHOLDS:
            row[f"first_{thr}_reach_class"] = t.get(f"first_{thr}_reach_class")
            row[f"first_{thr}_timestamp"] = t.get(f"first_{thr}_close_ts")
        rows.append(row)
    return rows


def analyze_sport(sport: str) -> dict:
    print(f"=== {sport} ===", flush=True)
    cfg = V1.SPORTS[sport]
    trades = load_frozen(sport)
    path_gate = reproduce_path(sport, trades)
    print(f"  path gate {'PASS' if path_gate['ok'] else 'FAIL'} {path_gate['observed']}", flush=True)
    if not path_gate["ok"]:
        return {
            "sport": sport,
            "halted": True,
            "reason": "BASELINE_PATH_GATE_FAIL",
            "path_gate": path_gate,
        }

    games = V1.load_games(cfg)
    scan_meta = attach_paths(sport, trades, games)
    stop_gate = reproduce_stop_model(sport, trades)
    print(f"  stop gate {'PASS' if stop_gate['ok'] else 'FAIL'} {stop_gate}", flush=True)
    if not stop_gate["ok"]:
        return {
            "sport": sport,
            "halted": True,
            "reason": "BASELINE_STOP_MODEL_GATE_FAIL",
            "path_gate": path_gate,
            "stop_gate": stop_gate,
            "scan": scan_meta,
        }

    by_split = {s: subset(trades, s) for s in SPLITS}
    fee_rows, win_fee_rows = fee_grid_table()

    t1 = {s: strategy_taker(by_split[s], 40, "ideal", "CURRENT") for s in SPLITS}
    t2 = {s: strategy_taker(by_split[s], 40, "moderate", "CURRENT") for s in SPLITS}
    t3 = {s: strategy_taker(by_split[s], 40, "conservative", "CONSERVATIVE") for s in SPLITS}
    hold = {s: hold_strategy(by_split[s], "CURRENT") for s in SPLITS}

    frontiers = {s: frontier_table(by_split[s]) for s in SPLITS}
    selection = select_trigger(frontiers["VALIDATION"])
    selected = selection["trigger"]
    oos_selected = next(r for r in frontiers["OOS"] if r["trigger"] == selected)
    val_selected = next(r for r in frontiers["VALIDATION"] if r["trigger"] == selected)

    dist_mod = exit_distribution(trades, "moderate_exit_proxy")
    dist_con = exit_distribution(trades, "conservative_exit_proxy")
    jumps = jump_stats(trades)
    hopp = hedge_opportunity_table(trades)
    hfees = hedge_fee_table()

    hedge_grid = {}
    for s in SPLITS:
        hedge_grid[s] = {}
        for h in EXIT_GRID:
            hedge_grid[s][h] = {
                "H1_optimistic": hedge_ev(by_split[s], h, 1.0, "CURRENT"),
                "H2_moderate_p50": hedge_ev(by_split[s], h, 0.50, "CURRENT"),
                "H3_conservative_p25": hedge_ev(by_split[s], h, 0.25, "CONSERVATIVE"),
                "sensitivity": {f"{p:.2f}": hedge_ev(by_split[s], h, p, "CURRENT") for p in FILL_GRID},
            }

    # Best validated hedge: max VAL H2 net EV
    val_h2 = [(h, hedge_grid["VALIDATION"][h]["H2_moderate_p50"]["net_ev"]) for h in EXIT_GRID]
    best_h = max(val_h2, key=lambda x: (x[1] is not None, x[1], -x[0]))[0]
    best_val = hedge_grid["VALIDATION"][best_h]["H2_moderate_p50"]
    best_oos = hedge_grid["OOS"][best_h]["H2_moderate_p50"]

    master = [
        master_row(
            "Hold",
            hold["FULL"]["gross_ev"],
            hold["FULL"]["mean_fees"],
            0.0,
            hold["FULL"]["net_ev"],
            hold["FULL"]["net_ev"],
            hold_strategy(trades, "CONSERVATIVE")["net_ev"],
        ),
        master_row(
            "80→40 ideal",
            t1["FULL"]["gross_ev"],
            entry_fee_cents("CURRENT"),
            t1["FULL"]["mean_fees"],
            t1["FULL"]["net_ev"],
            strategy_taker(trades, 40, "ideal", "CURRENT")["net_ev"],
            strategy_taker(trades, 40, "ideal", "CONSERVATIVE")["net_ev"],
        ),
        master_row(
            "Dynamic taker exit (40 trigger)",
            t2["FULL"]["gross_ev"],
            entry_fee_cents("CURRENT"),
            t2["FULL"]["mean_fees"],
            t2["FULL"]["net_ev"],
            t2["FULL"]["net_ev"],
            t3["FULL"]["net_ev"],
        ),
    ]
    for h in EXIT_GRID:
        h1 = hedge_grid["FULL"][h]["H1_optimistic"]
        h2 = hedge_grid["FULL"][h]["H2_moderate_p50"]
        h3 = hedge_grid["FULL"][h]["H3_conservative_p25"]
        master.append(
            master_row(
                f"Maker hedge H={h}",
                h1["lock_gross"],
                h1["entry_fee"],
                h1["hedge_fee"],
                h1["net_ev"],
                h2["net_ev"],
                h3["net_ev"],
            )
        )
    master.append(
        master_row(
            f"Best validated hedge H={best_h} (VAL select, p=0.50)",
            hedge_grid["FULL"][best_h]["H1_optimistic"]["lock_gross"],
            hedge_grid["FULL"][best_h]["H2_moderate_p50"]["entry_fee"],
            hedge_grid["FULL"][best_h]["H2_moderate_p50"]["hedge_fee"],
            hedge_grid["FULL"][best_h]["H2_moderate_p50"]["net_ev"],
            best_val["net_ev"],
            hedge_grid["VALIDATION"][best_h]["H3_conservative_p25"]["net_ev"],
        )
    )

    cap = [
        capital_row("Hold", hold["FULL"]["net_ev"], ENTRY_CENTS, ENTRY_CENTS),
        capital_row("80→40 ideal", t1["FULL"]["net_ev"], ENTRY_CENTS, ENTRY_CENTS),
        capital_row("Dynamic taker 40 moderate", t2["FULL"]["net_ev"], ENTRY_CENTS, ENTRY_CENTS),
        capital_row("Dynamic taker 40 conservative", t3["FULL"]["net_ev"], ENTRY_CENTS, ENTRY_CENTS),
    ]
    for h in EXIT_GRID:
        cap.append(
            capital_row(
                f"Hedge H={h} reserved",
                hedge_grid["FULL"][h]["H2_moderate_p50"]["net_ev"],
                ENTRY_CENTS,
                ENTRY_CENTS + h,
            )
        )
        cap.append(
            capital_row(
                f"Hedge H={h} sequential (initial only until fill)",
                hedge_grid["FULL"][h]["H2_moderate_p50"]["net_ev"],
                ENTRY_CENTS,
                ENTRY_CENTS,
            )
        )

    oos_note = None
    if len(by_split["OOS"]) < 100:
        oos_note = "INSUFFICIENT_SAMPLE"

    summary = {
        "program": PROGRAM,
        "sport": sport,
        "halted": False,
        "live_execution_changed": False,
        "fee_model_status": "ESTIMATED",
        "observed_production_model": "UNAVAILABLE",
        "settlement_fee": SETTLEMENT_FEE_CENTS,
        "path_gate": path_gate,
        "stop_gate": stop_gate,
        "scan": scan_meta,
        "splits": {s: len(by_split[s]) for s in SPLITS},
        "oos_note": oos_note,
        "exit_distribution_moderate": dist_mod,
        "exit_distribution_conservative": dist_con,
        "jumps": jumps,
        "fee_grid": fee_rows,
        "settlement_fee_rows": win_fee_rows,
        "t1_ideal": t1,
        "t2_moderate": t2,
        "t3_conservative": t3,
        "hold": hold,
        "frontier": frontiers,
        "trigger_selection": selection,
        "selected_trigger_val": val_selected,
        "selected_trigger_oos": oos_selected,
        "hedge_opportunity": hopp,
        "hedge_fee_table": hfees,
        "hedge_grid": hedge_grid,
        "best_validated_hedge": {
            "H": best_h,
            "selected_on": "VALIDATION",
            "metric": "H2 p_fill=0.50 CURRENT fees net EV",
            "val": best_val,
            "oos": best_oos,
        },
        "master": master,
        "capital": cap,
        "assumptions": {
            "moderate": {
                "exit": "per-trade trigger-candle yes_bid_close (CANDLE_EXECUTION_PROXY)",
                "entry_fee": "CURRENT = $0 maker (fee_type=quadratic)",
                "exit_fee": "taker quadratic M=1 at proxy price",
                "hedge_fill": "p=0.50 ASSUMED_NOT_MEASURED",
            },
            "conservative": {
                "exit": "per-trade trigger-candle yes_bid_low (adverse wick proxy)",
                "entry_fee": "CONSERVATIVE = taker @80",
                "exit_fee": "taker quadratic at wick proxy",
                "hedge_fill": "p=0.25 ASSUMED_NOT_MEASURED + maker-on hedge fee",
            },
        },
    }

    dest = out_dir(sport)
    ledgers = build_ledgers(trades)
    write_parquet(dest / "ledger.parquet", ledgers)
    write_json(dest / "summary.json", summary)
    write_json(
        dest / "reproduction_checks.json",
        {
            "BASELINE_PATH_GATE": "PASS" if path_gate["ok"] else "FAIL",
            "BASELINE_STOP_MODEL_GATE": "PASS" if stop_gate["ok"] else "FAIL",
            "path_gate": path_gate,
            "stop_gate": stop_gate,
        },
    )
    write_json(
        dest / "metadata.json",
        {
            "program": PROGRAM,
            "sport": sport,
            "live_execution_changed": False,
            "candle_path_ne_fill": True,
            "stop_trigger_ne_realized_exit": True,
            "gross_ev_ne_net_ev": True,
        },
    )
    print(f"  wrote {dest}", flush=True)
    return summary


def _fmt(x, d=4):
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.{d}f}"
    return str(x)


def _md_table(headers: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for r in rows:
        lines.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(lines)


def verdict_letter(results: dict[str, dict]) -> str:
    """Overall letter. Not live-ready. A=edge survives moderate+conservative; B=survives moderate only / hedge fantasy risk; C=moderate ~0; D=halt or both nets negative."""
    if any((r or {}).get("halted") for r in results.values()):
        return "D"
    nets = []
    cons = []
    ideals = []
    for r in results.values():
        t2 = (r.get("t2_moderate") or {}).get("FULL") or {}
        t3 = (r.get("t3_conservative") or {}).get("FULL") or {}
        t1 = (r.get("t1_ideal") or {}).get("FULL") or {}
        if t2.get("net_ev") is None or t3.get("net_ev") is None:
            return "D"
        nets.append(t2["net_ev"])
        cons.append(t3["net_ev"])
        ideals.append(t1.get("net_ev"))
    t2n = min(nets)
    t3n = min(cons)
    t1n = min([x for x in ideals if x is not None], default=None)
    if t2n < 0 and t3n < 0:
        return "D"
    if t2n < 0:
        return "C"
    if t3n < 0:
        return "B"
    if t1n is not None and t2n < 0.5 * t1n:
        return "B"
    return "B"  # execution evidence remains UNOBSERVED; do not issue A


def render_report(results: dict[str, dict]) -> str:
    v = verdict_letter(results)
    lines = [
        f"# {PROGRAM}",
        "",
        "```text",
        f"VERDICT: {v}",
        "",
        "LIVE EXECUTION CHANGED: FALSE",
        "",
        "CANDLE PATH ≠ ACTUAL FILL",
        "STOP TRIGGER ≠ REALIZED EXIT",
        "GROSS EV ≠ NET EV",
        "```",
        "",
        "Read-only measurement experiment. Does not arm trading. Does not modify FIRST01, Risk, Execution, Game Path, or hedge V1–V4.",
        "",
        "```text",
        "FEE MODEL STATUS: ESTIMATED",
        "OBSERVED_PRODUCTION_MODEL: UNAVAILABLE",
        "SETTLEMENT_FEE = 0",
        "```",
        "",
        "## 0. Reproduction gates",
        "",
    ]
    for sport, r in results.items():
        pg = r.get("path_gate") or {}
        sg = r.get("stop_gate") or {}
        lines.append(f"### {sport.upper()}")
        lines.append("")
        lines.append(f"- `BASELINE_{sport.upper()}_PATH_GATE` = **{'PASS' if pg.get('ok') else 'FAIL'}**")
        lines.append(f"- `BASELINE_{sport.upper()}_STOP_MODEL_GATE` = **{'PASS' if sg.get('ok') else 'FAIL'}**")
        if r.get("halted"):
            lines.append(f"- HALTED: `{r.get('reason')}`")
            lines.append("")
            continue
        o = pg.get("observed") or {}
        lines.append(f"- Frozen universe: {o.get('survivors')} / {o.get('n')} = {o.get('surv_pct')}% path survival")
        lines.append(f"- Stops: {o.get('stops')} · leaks: {o.get('leaks')}")
        lines.append(f"- Stop rescan mismatches: {sg.get('stop_flag_mismatches')} · missing candles: {sg.get('missing_candles')}")
        lines.append("")
    if any(r.get("halted") for r in results.values()):
        lines.append("Analysis halted. No new EV claims.")
        return "\n".join(lines) + "\n"

    lines += [
        "## 1. Fee architecture (parameterized)",
        "",
        "Copied locally. Existing `fee_models.py` was not modified.",
        "",
        "```text",
        "fee = ceil_6dp(M × coef × C × P × (1 − P))",
        "M = 1  (KXNBAGAME / KXNCAAMBGAME demo API, 2026-09-03)",
        "SETTLEMENT_FEE = 0",
        "```",
        "",
        "| Scenario | Entry @80 | Exit (taker @ proxy) | Hedge (maker @ H) |",
        "| --- | --- | --- | --- |",
        f"| CURRENT | $0 (quadratic, no maker fees) | taker 0.07 | $0 |",
        f"| MODERATE | maker 0.0175 = {entry_fee_cents('MODERATE'):.4f}¢ | taker 0.07 | maker 0.0175 |",
        f"| CONSERVATIVE | taker 0.07 = {entry_fee_cents('CONSERVATIVE'):.4f}¢ | taker 0.07 | maker 0.0175 |",
        "",
        "### Taker exit fee grid (1 contract, M=1)",
        "",
    ]
    fee_headers = ["Exit", "Taker fee", "Gross P&L (vs 80)", "Net CURRENT", "Net MODERATE", "Net CONSERVATIVE"]
    fee_map = defaultdict(dict)
    any_sport = next(iter(results.values()))
    for row in any_sport["fee_grid"]:
        fee_map[row["exit_price"]][row["fee_scenario"]] = row
    fee_rows = []
    for px in EXIT_GRID:
        c = fee_map[px]["CURRENT"]
        m = fee_map[px]["MODERATE"]
        k = fee_map[px]["CONSERVATIVE"]
        fee_rows.append(
            [f"{px}¢", f"{c['taker_fee']:.4f}¢", f"{c['gross_exit_pnl']:.1f}¢", f"{c['net_exit_pnl']:.4f}¢", f"{m['net_exit_pnl']:.4f}¢", f"{k['net_exit_pnl']:.4f}¢"]
        )
    lines.append(_md_table(fee_headers, fee_rows))
    lines += [
        "",
        "Win-to-settlement: `PNL_NET_WIN = 20¢ − ENTRY_FEE − SETTLEMENT_FEE(0)`.",
        "",
    ]

    for sport, r in results.items():
        lines += [f"## 2. {sport.upper()} — empirical exit distribution", ""]
        lines.append("### Threshold trigger distribution (close ≤ T)")
        lines.append("")
        td = r["exit_distribution_moderate"]["threshold_trigger_distribution"]
        lines.append(_md_table(["Exit / trigger", "Count", "P(trigger)"], [[f"{x['exit_price']}¢", x["trigger_count"], f"{_fmt(x['trigger_probability'], 2)}%"] for x in td]))
        lines += ["", "### Realized exit-price proxy (Model B: trigger-candle bid close)", ""]
        lines.append("Not the same object as the trigger distribution.")
        lines.append("")
        regs = r["exit_distribution_moderate"]["regions"]
        lines.append(
            _md_table(
                ["Region", "Count", "% of FIRST-80", "% of triggered"],
                [[x["region"], x["count"], f"{_fmt(x['pct_all'], 2)}%", _fmt(x["pct_triggered"], 2) + ("%" if x["pct_triggered"] is not None else "")] for x in regs],
            )
        )
        lines += ["", "### Conservative wick proxy (Model C: trigger-candle bid low)", ""]
        regs2 = r["exit_distribution_conservative"]["regions"]
        lines.append(
            _md_table(
                ["Region", "Count", "% of FIRST-80", "% of triggered"],
                [[x["region"], x["count"], f"{_fmt(x['pct_all'], 2)}%", _fmt(x["pct_triggered"], 2) + ("%" if x["pct_triggered"] is not None else "")] for x in regs2],
            )
        )
        j = r["jumps"]
        lines += [
            "",
            f"## 3. {sport.upper()} — jump-through",
            "",
            "Gaps are `previous_tradable_close − trigger_close`. Candle proxy, not L2.",
            "",
            _md_table(
                ["Stat", "Close gap (¢)", "Low gap (¢)"],
                [
                    ["n", j["jump_close"]["n"], j["jump_low"]["n"]],
                    ["median", _fmt(j["jump_close"]["median"]), _fmt(j["jump_low"]["median"])],
                    ["p75", _fmt(j["jump_close"]["p75"]), "—"],
                    ["p90", _fmt(j["jump_close"]["p90"]), _fmt(j["jump_low"]["p90"])],
                    ["p95", _fmt(j["jump_close"]["p95"]), "—"],
                    ["worst", _fmt(j["jump_close"]["worst"]), _fmt(j["jump_low"]["worst"])],
                    ["mean", _fmt(j["jump_close"]["mean"]), "—"],
                ],
            ),
            "",
            _md_table(
                ["Event (among 40-triggers)", "k", "%"],
                [
                    ["Close at/below 40 (orderly class)", j["close_directly_at_or_below_40"]["k"], _fmt(j["close_directly_at_or_below_40"]["pct"], 2) + "%"],
                    ["Jumped through 40", j["jumped_through_40"]["k"], _fmt(j["jumped_through_40"]["pct"], 2) + "%"],
                    ["From >40 to <35 on trigger candle", j["from_above_40_to_below_35"]["k"], _fmt(j["from_above_40_to_below_35"]["pct"], 2) + "%"],
                    ["From >40 to <30", j["from_above_40_to_below_30"]["k"], _fmt(j["from_above_40_to_below_30"]["pct"], 2) + "%"],
                    ["From >40 to <20", j["from_above_40_to_below_20"]["k"], _fmt(j["from_above_40_to_below_20"]["pct"], 2) + "%"],
                ],
            ),
            "",
            "Jump class counts: " + ", ".join(f"{k}={v}" for k, v in (j.get("orderly_or_class_counts") or {}).items()),
            "",
            "By minutes-to-close at trigger:",
            "",
            _md_table(
                ["Phase", "n", "median jump", "p90 jump"],
                [[x["phase"], x["n"], _fmt(x["median_jump"]), _fmt(x["p90_jump"])] for x in j["by_minutes_to_close"]],
            ),
            "",
            "By terminal outcome (among triggered):",
            "",
            _md_table(
                ["Terminal", "n", "median jump", "p90", "mean Model B exit"],
                [[x["terminal"], x["n"], _fmt(x["median_jump"]), _fmt(x["p90_jump"]), _fmt(x["mean_exit_moderate"])] for x in j["by_terminal_outcome"]],
            ),
            "",
        ]

        lines += [
            f"## 4. {sport.upper()} — taker strategies T1 / T2 / T3",
            "",
            "- **T1** IDEALIZED_TRIGGER_PRICE: exit = 40 whenever close ≤ 40.",
            "- **T2** CANDLE_EXECUTION_PROXY: per-trade exit = trigger-candle `yes_bid_close`. CURRENT fees.",
            "- **T3** conservative: per-trade exit = trigger-candle `yes_bid_low`; CONSERVATIVE fees (taker entry).",
            "",
            _md_table(
                ["Split", "T1 gross", "T1 net", "T2 gross", "T2 net", "T3 net"],
                [
                    [
                        s,
                        _fmt((r["t1_ideal"][s] or {}).get("gross_ev")),
                        _fmt((r["t1_ideal"][s] or {}).get("net_ev")),
                        _fmt((r["t2_moderate"][s] or {}).get("gross_ev")),
                        _fmt((r["t2_moderate"][s] or {}).get("net_ev")),
                        _fmt((r["t3_conservative"][s] or {}).get("net_ev")),
                    ]
                    for s in SPLITS
                ],
            ),
            "",
        ]
        if r.get("oos_note"):
            lines.append(f"OOS note: `{r['oos_note']}`.")
            lines.append("")

        lines += [
            f"## 5. {sport.upper()} — dynamic taker exit frontier",
            "",
            "Trigger selected on VALIDATION only (`net_ev_moderate`). OOS evaluated once.",
            "",
            f"Selected trigger: **{r['trigger_selection']['trigger']}¢** (VAL net EV {_fmt(r['trigger_selection']['val_net_ev_moderate'])}).",
            "",
            "### FULL sample (descriptive — not used for selection)",
            "",
        ]
        fr = r["frontier"]["FULL"]
        lines.append(
            _md_table(
                ["Trigger", "Trigger %", "Mean exit (B)", "Gross EV B", "Fees B", "Net EV moderate", "Net EV conservative"],
                [
                    [
                        x["trigger"],
                        _fmt(x["trigger_pct"], 2),
                        _fmt(x["mean_exit_moderate"]),
                        _fmt(x["gross_ev_moderate"]),
                        _fmt(x["fees_moderate"]),
                        _fmt(x["net_ev_moderate"]),
                        _fmt(x["net_ev_conservative"]),
                    ]
                    for x in fr
                ],
            )
        )
        lines += [
            "",
            "### VALIDATION (selection)",
            "",
            _md_table(
                ["Trigger", "n trig %", "Net EV moderate", "Net EV conservative"],
                [[x["trigger"], _fmt(x["trigger_pct"], 2), _fmt(x["net_ev_moderate"]), _fmt(x["net_ev_conservative"])] for x in r["frontier"]["VALIDATION"]],
            ),
            "",
            "### OOS (once)",
            "",
            _md_table(
                ["Trigger", "n trig %", "Net EV moderate", "Net EV conservative"],
                [[x["trigger"], _fmt(x["trigger_pct"], 2), _fmt(x["net_ev_moderate"]), _fmt(x["net_ev_conservative"])] for x in r["frontier"]["OOS"]],
            ),
            "",
        ]

        hopp = r["hedge_opportunity"]
        lines += [
            f"## 6. {sport.upper()} — dynamic maker hedge (FILL SCENARIO)",
            "",
            f"Opponent available: {hopp['opponent_available']} / {hopp['n']}. Missing: {hopp['missing_opponent']}.",
            "",
            "Opportunity = A2 tradable `yes_bid_close` **up-crosses H from below** after T0 and not after A1 40-close. Already-at-or-above on the first A2 print is **not** treated as a maker fill at H. **Not a fill.**",
            "",
            _md_table(
                ["H", "A2 ≥H before resolution", "%", "A2 ≥H before A1 stop", "%", "P(reach & A1 wins)", "P(reach & A1 loses)", "False-hedge share of opps"],
                [
                    [
                        x["H"],
                        x["a2_reaches_before_resolution"],
                        _fmt(x["pct_resolution"], 2),
                        x["a2_reaches_before_a1_stop"],
                        _fmt(x["pct_before_stop"], 2),
                        _fmt(x["p_reaches_and_a1_wins"], 2),
                        _fmt(x["p_reaches_and_a1_loses"], 2),
                        _fmt(x["false_hedge_share_of_opps"], 2),
                    ]
                    for x in hopp["by_H"]
                ],
            ),
            "",
            "Max A2 before resolution:",
            "",
            _md_table(["Max A2 ≥", "Count", "%"], [[x["max_a2_ge"], x["count"], _fmt(x["pct"], 2)] for x in hopp["max_a2_before_resolution"]]),
            "",
            "### Hedge lock economics (CURRENT / MODERATE / CONSERVATIVE fees)",
            "",
        ]
        ht = [x for x in r["hedge_fee_table"] if x["fee_scenario"] == "CURRENT"]
        lines.append(
            _md_table(
                ["H", "Paired cost", "Lock gross", "Entry fee", "Hedge fee", "Lock net CURRENT"],
                [[x["hedge_price"], x["paired_cost"], x["lock_gross"], x["entry_fee"], x["hedge_fee"], x["lock_net"]] for x in ht],
            )
        )
        lines += [
            "",
            "### H1 / H2 / H3 net EV (FULL)",
            "",
            _md_table(
                ["H", "H1 p=100% CURRENT", "H2 p=50% CURRENT", "H3 p=25% CONSERVATIVE"],
                [
                    [
                        h,
                        _fmt(r["hedge_grid"]["FULL"][h]["H1_optimistic"]["net_ev"]),
                        _fmt(r["hedge_grid"]["FULL"][h]["H2_moderate_p50"]["net_ev"]),
                        _fmt(r["hedge_grid"]["FULL"][h]["H3_conservative_p25"]["net_ev"]),
                    ]
                    for h in EXIT_GRID
                ],
            ),
            "",
            f"Best validated hedge (VAL, H2 p=50%): **H={r['best_validated_hedge']['H']}** · VAL net {_fmt(r['best_validated_hedge']['val']['net_ev'])} · OOS net {_fmt(r['best_validated_hedge']['oos']['net_ev'])}.",
            "",
            "Fill-probability sensitivity at best H (CURRENT fees, FULL):",
            "",
        ]
        bh = r["best_validated_hedge"]["H"]
        sens = r["hedge_grid"]["FULL"][bh]["sensitivity"]
        lines.append(
            _md_table(
                ["p_fill", "Net EV"],
                [[f"{p:.2f}", _fmt(sens[f"{p:.2f}"]["net_ev"])] for p in FILL_GRID],
            )
        )
        lines += ["", f"## 7. {sport.upper()} — master comparison (FULL)", "", _md_table(
            ["Strategy", "Gross EV", "Entry fees", "Exit/hedge fees", "Net EV", "Moderate net", "Conservative net"],
            [
                [
                    x["strategy"],
                    _fmt(x["gross_ev"]),
                    _fmt(x["entry_fees"]),
                    _fmt(x["exit_or_hedge_fees"]),
                    _fmt(x["net_ev"]),
                    _fmt(x["moderate_net_ev"]),
                    _fmt(x["conservative_net_ev"]),
                ]
                for x in r["master"]
            ],
        ), ""]
        lines += [
            f"## 8. {sport.upper()} — capital efficiency",
            "",
            "INITIAL NOTIONAL ≠ MAXIMUM CAPITAL COMMITMENT.",
            "",
            _md_table(
                ["Strategy", "EV/contract", "Initial", "Reserved", "EV / $ deployed", "EV / reserved"],
                [
                    [
                        x["strategy"],
                        _fmt(x["ev_per_contract"]),
                        x["initial_notional"],
                        x["maximum_capital_commitment"],
                        _fmt(x["ev_per_dollar_deployed"], 6),
                        _fmt(x["ev_per_reserved_capital"], 6),
                    ]
                    for x in r["capital"]
                    if "sequential" not in x["strategy"] or x["strategy"].endswith("H=40 sequential (initial only until fill)")
                ][:12],
            ),
            "",
            f"## 9. {sport.upper()} — risk (T2 moderate FULL)",
            "",
        ]
        rk = r["t2_moderate"]["FULL"]["risk"]
        lines.append(
            _md_table(
                ["Stat", "Value"],
                [[k, _fmt(rk.get(k)) if not isinstance(rk.get(k), str) else rk.get(k)] for k in (
                    "n", "mean", "median", "std", "downside_deviation", "sharpe_style", "sortino_style",
                    "max_single_trade_loss", "loss_frequency", "average_loss", "average_win", "profit_factor",
                    "expected_shortfall_5pct",
                )],
            )
        )
        lines.append("")
        lines.append(rk.get("note") or "")
        lines.append("")

    nba, ncaab = results["nba"], results["ncaab"]
    lines += [
        "## 10. NBA vs NCAAB",
        "",
        _md_table(
            ["Metric", "NBA", "NCAAB"],
            [
                ["n / survivors", f"{nba['path_gate']['observed']['n']} / {nba['path_gate']['observed']['survivors']}", f"{ncaab['path_gate']['observed']['n']} / {ncaab['path_gate']['observed']['survivors']}"],
                ["T1 net EV", _fmt(nba['t1_ideal']['FULL']['net_ev']), _fmt(ncaab['t1_ideal']['FULL']['net_ev'])],
                ["T2 moderate net EV", _fmt(nba['t2_moderate']['FULL']['net_ev']), _fmt(ncaab['t2_moderate']['FULL']['net_ev'])],
                ["T3 conservative net EV", _fmt(nba['t3_conservative']['FULL']['net_ev']), _fmt(ncaab['t3_conservative']['FULL']['net_ev'])],
                ["Median jump @40", _fmt(nba['jumps']['jump_close']['median']), _fmt(ncaab['jumps']['jump_close']['median'])],
                ["P90 jump @40", _fmt(nba['jumps']['jump_close']['p90']), _fmt(ncaab['jumps']['jump_close']['p90'])],
                ["P(jump through 40)", _fmt(nba['jumps']['jumped_through_40']['pct'], 2), _fmt(ncaab['jumps']['jumped_through_40']['pct'], 2)],
                ["Best VAL hedge H", nba['best_validated_hedge']['H'], ncaab['best_validated_hedge']['H']],
                ["Best hedge H2 FULL net", _fmt(nba['hedge_grid']['FULL'][nba['best_validated_hedge']['H']]['H2_moderate_p50']['net_ev']), _fmt(ncaab['hedge_grid']['FULL'][ncaab['best_validated_hedge']['H']]['H2_moderate_p50']['net_ev'])],
            ],
        ),
        "",
        "## 11. Dynamic delta / exposure (conceptual)",
        "",
        "| State | A1 | A2 | Portfolio | Action |",
        "| --- | --- | --- | --- | --- |",
        "| Healthy | High positive | Low | Directional | Hold |",
        "| Mild deterioration | Falling | Rising | Increasing risk | Monitor |",
        "| Hedge opportunity | Moderate | Moderate | High uncertainty | Rest maker hedge (scenario) |",
        "| Hedge filled | Offset | Offset | Reduced terminal payoff if pair settles 100 | Manage pair |",
        "| Severe deterioration | Low | High | Thesis failed | Taker liquidate or wait |",
        "",
        "TERMINAL PAYOFF NEUTRALITY (80+H=100 ⇒ lock 20−H) is not PATHWISE DELTA NEUTRALITY. Candles cannot prove simultaneous complementary books or equal contract counts.",
        "",
        "## 12. Verdict grades",
        "",
        "| Grade | Meaning |",
        "| --- | --- |",
        "| A. Path robustness | Frozen 80/40 close-stop reproduced |",
        "| B. Exit-price realism | Trigger ≠ fill; Model B/C measured from candles |",
        "| C. Fee burden | CURRENT taker-on-stop only; stress scenarios explicit |",
        "| D. Hedge opportunity structure | A2 prints measured; fills are scenarios |",
        "| E. Actual execution evidence | UNOBSERVED |",
        "",
        "## 13. Strongest remaining uncertainty",
        "",
        "1. No historical maker/taker fills — all exits and hedges are candle proxies or assumed fill probabilities.",
        "2. IOC liquidation can print through the trigger-candle close; bid_low is a wick proxy, not a queue.",
        "3. FCM $0.01 rounding not applied to fees.",
        "4. NCAAB OOS is small.",
        "5. Production `GET /series` was not re-verified in this run (demo API 2026-09-03: `quadratic`, M=1).",
        "",
        "## 14. Artifacts",
        "",
        "- Ledgers: `.../derived/{nba,ncaab}/first80_realistic_exit_fee_audit_v1/ledger.parquet`",
        "- Summaries: `summary.json`",
        "- Dashboard: `frontend/first80-realistic-exit-fee-audit-v1` (port 5180)",
        "",
        "Do not arm. Do not modify live trading.",
        "",
    ]
    return "\n".join(lines) + "\n"


def dashboard_payload(results: dict[str, dict]) -> dict:
    return {
        "banner": "FIRST80 REALISTIC EXIT + FEE AUDIT V1 — RESEARCH ONLY — LIVE EXECUTION CHANGED: FALSE — CANDLE PATH ≠ FILL — STOP ≠ EXIT — GROSS ≠ NET",
        "verdict": verdict_letter(results),
        "live_execution_changed": False,
        "settlement_fee": SETTLEMENT_FEE_CENTS,
        "sports": {
            s: {
                "halted": r.get("halted", False),
                "path_gate": r.get("path_gate"),
                "stop_gate": r.get("stop_gate"),
                "hold": (r.get("hold") or {}).get("FULL"),
                "t1": (r.get("t1_ideal") or {}).get("FULL"),
                "t2": (r.get("t2_moderate") or {}).get("FULL"),
                "t3": (r.get("t3_conservative") or {}).get("FULL"),
                "t1_splits": r.get("t1_ideal"),
                "t2_splits": r.get("t2_moderate"),
                "t3_splits": r.get("t3_conservative"),
                "exit_regions": (r.get("exit_distribution_moderate") or {}).get("regions"),
                "exit_regions_conservative": (r.get("exit_distribution_conservative") or {}).get("regions"),
                "threshold_triggers": (r.get("exit_distribution_moderate") or {}).get("threshold_trigger_distribution"),
                "jumps": r.get("jumps"),
                "frontier": (r.get("frontier") or {}).get("FULL"),
                "frontier_val": (r.get("frontier") or {}).get("VALIDATION"),
                "frontier_oos": (r.get("frontier") or {}).get("OOS"),
                "trigger_selection": r.get("trigger_selection"),
                "hedge_opportunity": r.get("hedge_opportunity"),
                "hedge_full": {
                    str(h): {
                        "H1": r["hedge_grid"]["FULL"][h]["H1_optimistic"]["net_ev"],
                        "H2": r["hedge_grid"]["FULL"][h]["H2_moderate_p50"]["net_ev"],
                        "H3": r["hedge_grid"]["FULL"][h]["H3_conservative_p25"]["net_ev"],
                        "sens": {f"{p:.2f}": r["hedge_grid"]["FULL"][h]["sensitivity"][f"{p:.2f}"]["net_ev"] for p in FILL_GRID},
                    }
                    for h in EXIT_GRID
                }
                if r.get("hedge_grid")
                else None,
                "best_hedge": r.get("best_validated_hedge"),
                "master": r.get("master"),
                "capital": r.get("capital"),
                "fee_grid": [x for x in (r.get("fee_grid") or []) if x["fee_scenario"] == "CURRENT"],
                "oos_note": r.get("oos_note"),
            }
            for s, r in results.items()
        },
    }


def console_summary(results: dict[str, dict]) -> str:
    v = verdict_letter(results)
    lines = [
        f"VERDICT: {v}",
        "",
        "LIVE EXECUTION CHANGED: FALSE",
        "",
        "CANDLE PATH ≠ ACTUAL FILL",
        "STOP TRIGGER ≠ REALIZED EXIT",
        "GROSS EV ≠ NET EV",
        "",
    ]
    if any(r.get("halted") for r in results.values()):
        for s, r in results.items():
            if r.get("halted"):
                lines.append(f"{s}: HALTED {r.get('reason')}")
        return "\n".join(lines)
    for i, (title, fn) in enumerate(
        [
            ("1. Empirical exit distribution", lambda r: r["exit_distribution_moderate"]["regions"]),
            ("2. Jump-through statistics", lambda r: r["jumps"]["jump_close"]),
            ("3. Taker fee burden", lambda r: r["t2_moderate"]["FULL"]["mean_fees"]),
            ("4. Moderate net EV", lambda r: r["t2_moderate"]["FULL"]["net_ev"]),
            ("5. Conservative net EV", lambda r: r["t3_conservative"]["FULL"]["net_ev"]),
            ("6. Dynamic hedge EV", lambda r: r["hedge_grid"]["FULL"][r["best_validated_hedge"]["H"]]["H2_moderate_p50"]["net_ev"]),
            ("7. Fill-probability sensitivity", lambda r: {f"{p:.2f}": r["hedge_grid"]["FULL"][r["best_validated_hedge"]["H"]]["sensitivity"][f"{p:.2f}"]["net_ev"] for p in FILL_GRID}),
            ("8. NBA vs NCAAB comparison", lambda r: None),
            ("9. Capital efficiency", lambda r: r["capital"][2]),
            ("10. Strongest remaining uncertainty", lambda r: "fills UNOBSERVED; wick ≠ queue; NCAAB OOS small"),
        ],
        1,
    ):
        lines.append(title)
        if title.startswith("8."):
            lines.append(
                f"  NBA T2={results['nba']['t2_moderate']['FULL']['net_ev']} T3={results['nba']['t3_conservative']['FULL']['net_ev']} "
                f"NCAAB T2={results['ncaab']['t2_moderate']['FULL']['net_ev']} T3={results['ncaab']['t3_conservative']['FULL']['net_ev']}"
            )
        else:
            for s, r in results.items():
                try:
                    lines.append(f"  {s}: {fn(r)}")
                except Exception as e:
                    lines.append(f"  {s}: {e}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    sports = args or ["nba", "ncaab"]
    results = {}
    for sport in sports:
        results[sport] = analyze_sport(sport)
        if results[sport].get("halted") and not args:
            print("STOP ANALYSIS — reproduction failed — no new EV claims", flush=True)
            text = render_report(results)
            DOCS.write_text(text)
            print(console_summary(results))
            return 1

    if set(results) >= {"nba", "ncaab"} and not any(r.get("halted") for r in results.values()):
        text = render_report(results)
        DOCS.write_text(text)
        dash = dashboard_payload(results)
        DASH_PUBLIC.mkdir(parents=True, exist_ok=True)
        write_json(DASH_PUBLIC / "dashboard.json", dash)
        write_json(out_dir("nba") / "dashboard.json", dash)
        write_json(out_dir("ncaab") / "dashboard.json", dash)
        print(f"wrote {DOCS}", flush=True)

    print(console_summary(results))
    return 0 if not any(r.get("halted") for r in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
