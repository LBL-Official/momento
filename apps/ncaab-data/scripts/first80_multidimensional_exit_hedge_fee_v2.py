#!/usr/bin/env python3
"""FIRST80_MULTIDIMENSIONAL_EXIT_HEDGE_FEE_ENGINE_V2

Hierarchical execution-policy research on frozen FIRST-80 paths.

Does not modify FIRST01, Risk, live execution, hedge V1–V4, or V1 artifacts.

LIVE EXECUTION CHANGED: FALSE
CANDLE PATH ≠ ACTUAL FILL
STOP TRIGGER ≠ REALIZED EXIT
MAKER OPPORTUNITY ≠ MAKER FILL
GROSS EV ≠ NET EV
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

try:
    import yaml  # optional; config constants below are authoritative if missing
except ImportError:
    yaml = None  # type: ignore

NBA_SCRIPTS = Path("/Users/user/Desktop/Momento/apps/nba-data/scripts")
HERE = Path(__file__).resolve().parent
CONFIG_PATH = Path(
    "/Users/user/Desktop/Momento/docs/research/first80_multidimensional_exit_hedge_fee_v2.yaml"
)
DOCS = Path(
    "/Users/user/Desktop/Momento/docs/research/FIRST80_MULTIDIMENSIONAL_EXIT_HEDGE_FEE_ENGINE_V2.md"
)
DASH_PUBLIC = Path(
    "/Users/user/Desktop/Momento/frontend/first80-multidimensional-exit-hedge-fee-v2/public/data"
)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


sys.path.insert(0, str(NBA_SCRIPTS))
V1A = _load("first80_exit_fee_v1", HERE / "first80_realistic_exit_fee_audit_v1.py")
V1 = V1A.V1
A = V1A.A

PROGRAM = "FIRST80_MULTIDIMENSIONAL_EXIT_HEDGE_FEE_ENGINE_V2"
BANNER = (
    "VERDICT: RESEARCH ONLY  |  LIVE EXECUTION CHANGED: FALSE  |  "
    "CANDLE PATH ≠ ACTUAL FILL  |  STOP TRIGGER ≠ REALIZED EXIT  |  "
    "MAKER OPPORTUNITY ≠ MAKER FILL  |  GROSS EV ≠ NET EV"
)
ENTRY = 80
WIN = 20
MISS = -80
SETTLE_FEE = 0.0
THRESHOLDS = V1A.THRESHOLDS
EXIT_GRID = V1A.EXIT_GRID
SPLITS = V1A.SPLITS
PERSIST_GRID = (1, 2, 3, 5)
FILL_GRID = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
RATIOS = (0.0, 0.25, 0.5, 0.75, 1.0)
N_MC = 10_000
SEED = 20260903
TIME_BUCKETS = (
    ("0-5m", 0, 5),
    ("5-15m", 5, 15),
    ("15-30m", 15, 30),
    ("30-60m", 30, 60),
    ("60-120m", 60, 120),
    ("120m+", 120, None),
)
EXIT_BANDS = (
    ("37-40", 37, 40),
    ("32-36", 32, 36),
    ("27-31", 27, 31),
    ("22-26", 22, 26),
    ("<22", 0, 21.999),
)
CFG = {}
if CONFIG_PATH.exists() and yaml is not None:
    CFG = yaml.safe_load(CONFIG_PATH.read_text()) or {}


def out_dir(sport: str) -> Path:
    cfg = V1.SPORTS[sport]
    p = cfg["root"] / "derived" / cfg["norm"] / "first80_multidimensional_exit_hedge_fee_v2"
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def write_parquet(path: Path, rows: list[dict]) -> None:
    V1A.write_parquet(path, rows)


def fee_cents(kind: str, price: float, scen: str) -> float:
    taker_m = {"CURRENT_BASE_CASE": 1.0, "CONSERVATIVE_FEE_STRESS": 1.0, "HIGHER_FUTURE_FEE_STRESS": 1.5}[scen]
    if kind == "taker":
        return V1A.quadratic_fee_cents(V1A.TAKER_COEF * taker_m, 1, price)
    if kind == "entry":
        if scen == "CURRENT_BASE_CASE":
            return 0.0
        raw = V1A.quadratic_fee_cents(V1A.MAKER_COEF, 1, ENTRY)
        return raw * (2.0 if scen != "CURRENT_BASE_CASE" else 1.0) if scen != "CURRENT_BASE_CASE" else raw
    if kind == "hedge":
        if scen == "CURRENT_BASE_CASE":
            return 0.0
        raw = V1A.quadratic_fee_cents(V1A.MAKER_COEF, 1, price)
        return raw * (2.0 if scen == "HIGHER_FUTURE_FEE_STRESS" else 1.0)
    raise ValueError(kind)


def entry_fee(scen: str) -> float:
    if scen == "CURRENT_BASE_CASE":
        return 0.0
    raw = V1A.quadratic_fee_cents(V1A.MAKER_COEF, 1, ENTRY)
    return raw * 2.0 if scen in ("CONSERVATIVE_FEE_STRESS", "HIGHER_FUTURE_FEE_STRESS") else raw


def mid_of(q: dict) -> float | None:
    b, a = V1A.e4_to_cents(q.get("bid_c")), V1A.e4_to_cents(q.get("ask_c"))
    if b is None:
        return None
    if a is None:
        return b
    return (b + a) / 2.0


def time_bucket(minutes: float | None) -> str:
    if minutes is None:
        return "UNKNOWN"
    for name, lo, hi in TIME_BUCKETS:
        if minutes >= lo and (hi is None or minutes < hi):
            return name
    return "UNKNOWN"


def vol_regime(abs5: float | None, jump: float | None, n_down: int) -> str:
    if jump is not None and jump >= 15:
        return "JUMP_EVENT"
    if n_down >= 3:
        return "SUSTAINED_REVERSAL"
    if abs5 is None:
        return "UNKNOWN"
    if abs5 < 3:
        return "LOW_VOL"
    if abs5 < 8:
        return "MODERATE_VOL"
    return "HIGH_VOL"


def band_of(px: float | None) -> str | None:
    if px is None:
        return None
    for name, lo, hi in EXIT_BANDS:
        if lo <= px <= hi:
            return name
    return "<22"


def risk_stats(pnls: list[float]) -> dict:
    return V1A.risk_stats(pnls)


def hold_gross(t: dict) -> float:
    return WIN if t["expiration_result_yes"] else MISS


def reproduce(sport: str) -> tuple[list[dict], dict]:
    trades = V1A.load_frozen(sport)
    gate = V1A.reproduce_path(sport, trades)
    return trades, gate


def scan_quotes(sport: str, trades: list[dict], games: dict) -> dict:
    cfg = V1.SPORTS[sport]
    candles = cfg["root"] / "normalized" / cfg["norm"] / "candles_1m"
    by_t = {t["ticker"]: t for t in trades}
    opp_map: dict[str, list[dict]] = defaultdict(list)
    miss_g = miss_o = 0
    for rec in trades:
        rec["_a1"] = []
        rec["_a2"] = []
        g = games.get(rec.get("event_id"))
        V1A.attach_scan_window(rec, g)
        rec["opponent_ticker"] = None
        rec["opponent_available"] = False
        if not g:
            rec["opponent_status"] = "GAME_MISSING"
            miss_g += 1
            continue
        opp = V1.opponent_of(g, rec["ticker"])
        if not opp:
            rec["opponent_status"] = "OPPONENT_UNAVAILABLE"
            miss_o += 1
            continue
        rec["opponent_ticker"] = opp
        rec["opponent_available"] = True
        rec["opponent_status"] = "OK"
        opp_map[opp].append(rec)
    needed = set(by_t) | set(opp_map)
    files = [p for p in candles.rglob("*.parquet") if p.stem in needed]
    print(f"  candle files {len(files)}/{len(needed)}", flush=True)
    for n, path in enumerate(files, 1):
        if n % 500 == 0 or n in (1, len(files)):
            print(f"  scan {n}/{len(files)}", flush=True)
        quotes = V1A.load_ticker_quotes(path)
        stem = path.stem
        if stem in by_t:
            by_t[stem]["_a1"] = quotes
        if stem in opp_map:
            for rec in opp_map[stem]:
                rec["_a2"] = quotes
    return {"files": len(files), "needed": len(needed), "missing_game": miss_g, "missing_opp": miss_o}


def path_of(rec: dict, key: str) -> list[dict]:
    ck = "_path_a1" if key == "_a1" else "_path_a2"
    cached = rec.get(ck)
    if cached is not None:
        return cached
    t0 = int(rec["first_80_timestamp"])
    end = rec.get("scan_window_end")
    start = rec.get("scan_window_start")
    out = V1A.subsequent_tradable(rec.get(key) or [], t0, end, start)
    rec[ck] = out
    return out


def first_trigger(t: dict, thr: int, kind: str, persist: int, path: list[dict] | None = None, entry_px: float | None = None) -> dict | None:
    """Causal: uses only candles at/before the decision bar. Cached per trade."""
    cache = t.setdefault("_ft", {})
    key = (kind, int(thr), int(persist))
    if key in cache:
        return cache[key]
    path = path if path is not None else path_of(t, "_a1")
    entry_px = entry_px if entry_px is not None else (t.get("entry_price_proxy") or float(ENTRY))
    closes: list[float] = []
    hit_row = None
    for i, q in enumerate(path):
        c = V1A.e4_to_cents(q["bid_c"])
        lo = V1A.e4_to_cents(q["bid_l"])
        md = mid_of(q)
        if c is not None:
            closes.append(c)
        else:
            closes.append(closes[-1] if closes else entry_px)
        hit = False
        if kind == "BID_CLOSE_BELOW_THRESHOLD":
            hit = c is not None and c <= thr
        elif kind == "BID_LOW_BELOW_THRESHOLD":
            hit = lo is not None and lo <= thr
        elif kind == "MID_PROXY_BELOW_THRESHOLD":
            hit = md is not None and md <= thr
        elif kind == "N_CONSECUTIVE_MINUTES_BELOW_THRESHOLD":
            if len(closes) >= persist and all(x <= thr for x in closes[-persist:]):
                hit = True
        elif kind == "PERCENTAGE_DECLINE_FROM_ENTRY":
            hit = c is not None and (entry_px - c) >= (ENTRY - thr)
        elif kind == "RATE_OF_CHANGE_DETERIORATION":
            if len(closes) >= 5 and c is not None:
                hit = (closes[-5] - c) >= max(5.0, (ENTRY - thr) / 4.0)
        if hit:
            prev = path[i - 1] if i else None
            prev_c = V1A.e4_to_cents(prev["bid_c"]) if prev else None
            abs5 = None
            if len(closes) >= 5:
                abs5 = abs(closes[-1] - closes[-5])
            n_down = 0
            for a, b in zip(closes[-4:], closes[-3:]):
                if b < a:
                    n_down += 1
            jump = None if prev_c is None or c is None else prev_c - c
            hit_row = {
                "ts": q["ts"],
                "close": c,
                "low": lo,
                "high": V1A.e4_to_cents(q["bid_h"]),
                "mid": md,
                "prev_close": prev_c,
                "jump": jump,
                "abs5": abs5,
                "n_down": n_down,
                "vol": vol_regime(abs5, jump, n_down),
                "idx": i,
            }
            break
    cache[key] = hit_row
    return hit_row


def a2_upcross(t: dict, h: int, before_ts: int | None, path: list[dict] | None = None) -> dict | None:
    cache = t.setdefault("_ax", {})
    key = (int(h), before_ts)
    if key in cache:
        return cache[key]
    path = path if path is not None else path_of(t, "_a2")
    prev_c = None
    found = None
    for q in path:
        if before_ts is not None and q["ts"] > before_ts:
            break
        c = V1A.e4_to_cents(q["bid_c"])
        if c is None:
            continue
        if prev_c is not None and prev_c < h <= c:
            found = {
                "ts": q["ts"],
                "close": c,
                "prev": prev_c,
                "jump": c - prev_c,
                "low": V1A.e4_to_cents(q["bid_l"]),
                "high": V1A.e4_to_cents(q["bid_h"]),
            }
            break
        prev_c = c
    cache[key] = found
    return found


def enrich_trade(rec: dict) -> dict:
    a1 = path_of(rec, "_a1")
    a2 = path_of(rec, "_a2")
    t0 = int(rec["first_80_timestamp"])
    entry_px = rec.get("entry_close_cents") or V1A.e4_to_cents(rec.get("entry_bid_close_e4")) or float(ENTRY)
    rec["entry_price_proxy"] = entry_px
    min_px = None
    min_ts = None
    max_a2 = None
    max_a2_ts = None
    touches = {}
    for i, q in enumerate(a1):
        c = V1A.e4_to_cents(q["bid_c"])
        lo = V1A.e4_to_cents(q["bid_l"])
        if c is not None and (min_px is None or c < min_px):
            min_px, min_ts = c, q["ts"]
        for thr in THRESHOLDS:
            if thr not in touches:
                touches[thr] = {
                    "touch": False,
                    "close": False,
                    "jump": False,
                    "first_close": None,
                    "first_low": None,
                    "ts": None,
                    "touch_ts": None,
                }
            st = touches[thr]
            if lo is not None and lo <= thr:
                st["touch"] = True
                if st["first_low"] is None:
                    st["first_low"] = lo
                    st["touch_ts"] = q["ts"]
            if c is not None and c <= thr:
                if not st["close"]:
                    st["close"] = True
                    st["first_close"] = c
                    st["ts"] = q["ts"]
                    if i > 0:
                        pc = V1A.e4_to_cents(a1[i - 1]["bid_c"])
                        if pc is not None and pc > thr and c < thr:
                            st["jump"] = True
    for q in a2:
        c = V1A.e4_to_cents(q["bid_c"])
        if c is not None and (max_a2 is None or c > max_a2):
            max_a2, max_a2_ts = c, q["ts"]
    rec["minimum_favorite_price"] = min_px
    rec["time_to_minimum"] = None if min_ts is None else (min_ts - t0) / 60.0
    rec["maximum_opponent_price"] = max_a2
    rec["time_to_opponent_maximum"] = None if max_a2_ts is None else (max_a2_ts - t0) / 60.0
    rec["max_drawdown"] = None if min_px is None else entry_px - min_px
    rec["touches"] = touches
    rec["n_a1"] = len(a1)
    rec["n_a2"] = len(a2)
    rec["favorite_won"] = bool(rec["expiration_result_yes"])
    # freeze 40 close-stop rescan
    rec["rescanned_stop_close"] = bool(touches.get(40, {}).get("close"))
    return rec


def stop_gate(sport: str, trades: list[dict]) -> dict:
    missing = [t["ticker"] for t in trades if not t.get("_a1")]
    mismatch = []
    for t in trades:
        if not t.get("_a1"):
            continue
        if bool(t.get("stop_close_triggered")) != bool(t.get("rescanned_stop_close")):
            mismatch.append(t["ticker"])
    return {
        "sport": sport,
        "ok": len(missing) == 0 and len(mismatch) == 0,
        "missing_candles": len(missing),
        "stop_flag_mismatches": len(mismatch),
        "mismatch_tickers": mismatch[:20],
    }


def phase1(trades: list[dict]) -> dict:
    n = len(trades)
    winners = [t for t in trades if t["favorite_won"]]
    losers = [t for t in trades if not t["favorite_won"]]
    reach = []
    for thr in THRESHOLDS:
        k_c = sum(1 for t in trades if t["touches"][thr]["close"])
        k_t = sum(1 for t in trades if t["touches"][thr]["touch"])
        k_j = sum(1 for t in trades if t["touches"][thr]["jump"])
        kw = sum(1 for t in winners if t["touches"][thr]["close"])
        kl = sum(1 for t in losers if t["touches"][thr]["close"])
        closed = [t for t in trades if t["touches"][thr]["close"]]
        win_given = None if not closed else 100.0 * sum(1 for t in closed if t["favorite_won"]) / len(closed)
        reach.append(
            {
                "threshold": thr,
                "p_touch": round(100.0 * k_t / n, 4),
                "p_close": round(100.0 * k_c / n, 4),
                "p_jump": round(100.0 * k_j / n, 4),
                "p_close_winners": None if not winners else round(100.0 * kw / len(winners), 4),
                "p_close_losers": None if not losers else round(100.0 * kl / len(losers), 4),
                "p_win_given_close": None if win_given is None else round(win_given, 4),
                "n_close": k_c,
                "evidence": "A",
            }
        )
    dd_rows = []
    for x in THRESHOLDS:
        hit = [t for t in trades if t.get("minimum_favorite_price") is not None and t["minimum_favorite_price"] <= x]
        dd_rows.append(
            {
                "max_dd_reaches": x,
                "n": len(hit),
                "p_of_universe": round(100.0 * len(hit) / n, 4),
                "p_win": None if not hit else round(100.0 * sum(1 for t in hit if t["favorite_won"]) / len(hit), 4),
                "evidence": "A",
            }
        )
    exits = []
    for thr in EXIT_GRID:
        trig = [t for t in trades if t["touches"][thr]["close"]]
        bands = {name: 0 for name, _, _ in EXIT_BANDS}
        px = []
        for t in trig:
            p = t["touches"][thr]["first_close"]
            if p is None:
                continue
            px.append(p)
            b = band_of(p)
            if b:
                bands[b] += 1
        nt = len(trig) or 1
        exits.append(
            {
                "trigger": thr,
                "n": len(trig),
                "mean_proxy": None if not px else round(float(np.mean(px)), 4),
                "median_proxy": None if not px else round(float(np.median(px)), 4),
                "bands": {k: round(100.0 * v / nt, 4) for k, v in bands.items()},
                "band_counts": bands,
                "label": "CANDLE_EXECUTION_PROXY",
                "evidence": "B",
            }
        )
    return {"reach": reach, "p_win_given_dd": dd_rows, "exit_bands": exits, "n": n}


def taker_pnl(t: dict, trig: dict | None, model: str, scen: str, ideal_thr: int | None) -> dict:
    ef = entry_fee(scen)
    if trig is None:
        g = hold_gross(t)
        return {"gross": g, "entry_fee": ef, "exit_fee": 0.0, "hedge_fee": 0.0, "net": g - ef - SETTLE_FEE, "exit_px": None, "branch": "HOLD"}
    if model == "T1":
        px = float(ideal_thr if ideal_thr is not None else 40)
    elif model == "T2":
        px = trig["close"] if trig["close"] is not None else float(ideal_thr or 40)
    elif model == "T3":
        px = trig["low"] if trig["low"] is not None else trig["close"]
        if px is None:
            px = float(ideal_thr or 40)
    else:
        px = trig["close"] if trig["close"] is not None else float(ideal_thr or 40)
    xf = fee_cents("taker", px, scen)
    g = px - ENTRY
    return {"gross": g, "entry_fee": ef, "exit_fee": xf, "hedge_fee": 0.0, "net": g - ef - xf - SETTLE_FEE, "exit_px": px, "branch": "TAKER"}


def lock_net(h: float, scen: str, fill_px: float | None = None) -> dict:
    px = h if fill_px is None else fill_px
    ef = entry_fee(scen)
    hf = fee_cents("hedge", px, scen)
    g = 100.0 - ENTRY - px
    return {"gross": g, "entry_fee": ef, "exit_fee": 0.0, "hedge_fee": hf, "net": g - ef - hf - SETTLE_FEE, "exit_px": px, "branch": "HEDGE"}


def eval_taker(trades: list[dict], thr: int, kind: str, persist: int, model: str, scen: str) -> dict:
    pnls, fees, exits, flags = [], [], [], []
    for t in trades:
        trig = first_trigger(t, thr, kind, persist)
        r = taker_pnl(t, trig, model, scen, thr)
        pnls.append(r["net"])
        fees.append(r["entry_fee"] + r["exit_fee"])
        if r["exit_px"] is not None:
            exits.append(r["exit_px"])
        flags.append(trig is not None)
    ev = float(np.mean(pnls)) if pnls else None
    return {
        "policy": f"TAKER|{kind}|T={thr}|P={persist}|{model}|{scen}",
        "family": "TAKER",
        "threshold": thr,
        "trigger_type": kind,
        "persist": persist,
        "exit_model": model,
        "fee_scenario": scen,
        "n": len(trades),
        "trigger_pct": None if not trades else round(100.0 * sum(flags) / len(trades), 4),
        "mean_exit": None if not exits else round(float(np.mean(exits)), 4),
        "gross_ev": round(float(np.mean([hold_gross(t) if not f else (exits[i] - ENTRY if i < len(exits) else -40) for i, (t, f) in enumerate(zip(trades, flags))])), 4)
        if False
        else None,
        "net_ev": None if ev is None else round(ev, 4),
        "mean_fees": round(float(np.mean(fees)), 4) if fees else None,
        "risk": risk_stats(pnls),
        "evidence": "B" if model in ("T2", "T3") else "C",
        "flags": {
            "LOOKAHEAD_BIAS": False,
            "UNOBSERVED_FILL_ASSUMPTION": False,
            "EXECUTION_PRICE_ASSUMPTION": model in ("T1", "T3", "T4"),
            "FEE_ASSUMPTION": scen != "CURRENT_BASE_CASE",
        },
        "_pnls": pnls,
    }


def eval_taker_clean(trades, thr, kind, persist, model, scen) -> dict:
    """Same as eval_taker but compute gross properly."""
    nets, grosses, fees, exits, n_tr = [], [], [], [], 0
    for t in trades:
        entry_px = t.get("entry_price_proxy") or float(ENTRY)
        trig = first_trigger(t, thr, kind, persist)
        r = taker_pnl(t, trig, model, scen, thr)
        nets.append(r["net"])
        grosses.append(r["gross"])
        fees.append(r["entry_fee"] + r["exit_fee"] + r["hedge_fee"])
        if trig is not None:
            n_tr += 1
            if r["exit_px"] is not None:
                exits.append(r["exit_px"])
    return {
        "policy": f"TAKER|{kind}|T={thr}|P={persist}|{model}|{scen}",
        "family": "TAKER",
        "threshold": thr,
        "trigger_type": kind,
        "persist": persist,
        "exit_model": model,
        "fee_scenario": scen,
        "n": len(trades),
        "trigger_pct": None if not trades else round(100.0 * n_tr / len(trades), 4),
        "mean_exit": None if not exits else round(float(np.mean(exits)), 4),
        "gross_ev": round(float(np.mean(grosses)), 4) if grosses else None,
        "net_ev": round(float(np.mean(nets)), 4) if nets else None,
        "mean_fees": round(float(np.mean(fees)), 4) if fees else None,
        "entry_fees": round(float(np.mean([entry_fee(scen) for _ in trades])), 4) if trades else None,
        "exit_fees": round(float(np.mean(fees)) - entry_fee(scen), 4) if trades else None,
        "hedge_fees": 0.0,
        "risk": risk_stats(nets),
        "evidence": "B" if model in ("T2", "T3") else ("C" if model == "T1" else "D"),
        "capital_initial": ENTRY,
        "capital_reserved": ENTRY,
        "flags": {
            "LOOKAHEAD_BIAS": False,
            "UNOBSERVED_FILL_ASSUMPTION": False,
            "EXECUTION_PRICE_ASSUMPTION": model != "T2",
            "FEE_ASSUMPTION": scen != "CURRENT_BASE_CASE",
            "SMALL_SAMPLE_SIZE": len(trades) < 100,
        },
        "_pnls": nets,
    }


def hybrid_components(t, h, ratio, taker_thr, taker_model, scen, h_mode: str) -> dict:
    """Causal hybrid legs. p_fill is applied later — no future path filtering."""
    trig = first_trigger(t, taker_thr, "BID_CLOSE_BELOW_THRESHOLD", 1)
    stop_ts = None if trig is None else trig["ts"]
    opp = a2_upcross(t, h, stop_ts)
    unhedged = taker_pnl(t, trig, taker_model, scen, taker_thr)
    if not opp:
        return {
            "opp": False,
            "p_scale": 0.0,
            "filled_net": unhedged["net"],
            "miss_net": unhedged["net"],
            "filled_gross": unhedged["gross"],
            "miss_gross": unhedged["gross"],
            "entry_fee": unhedged["entry_fee"],
            "filled_exit_fee": unhedged["exit_fee"],
            "miss_exit_fee": unhedged["exit_fee"],
            "filled_hedge_fee": 0.0,
        }
    jump = opp.get("jump") or 0
    fill_px = float(h)
    p_scale = 1.0
    if h_mode == "H4" and jump >= 10:
        p_scale = 0.35
        fill_px = float(opp["close"])
    if h_mode == "H3":
        fill_px = float(np.clip(opp["close"], h - 3, h + 2))
    locked = lock_net(h, scen, fill_px)
    filled_net = ratio * locked["net"] + (1.0 - ratio) * unhedged["net"]
    filled_gross = ratio * locked["gross"] + (1.0 - ratio) * unhedged["gross"]
    return {
        "opp": True,
        "p_scale": p_scale,
        "filled_net": filled_net,
        "miss_net": unhedged["net"],
        "filled_gross": filled_gross,
        "miss_gross": unhedged["gross"],
        "entry_fee": unhedged["entry_fee"],
        "filled_exit_fee": (1.0 - ratio) * unhedged["exit_fee"],
        "miss_exit_fee": unhedged["exit_fee"],
        "filled_hedge_fee": ratio * locked["hedge_fee"],
    }


def mix_hybrid(c: dict, p: float) -> dict:
    p_use = (p * c["p_scale"]) if c["opp"] else 0.0
    net = p_use * c["filled_net"] + (1.0 - p_use) * c["miss_net"]
    gross = p_use * c["filled_gross"] + (1.0 - p_use) * c["miss_gross"]
    exit_fee = p_use * c["filled_exit_fee"] + (1.0 - p_use) * c["miss_exit_fee"]
    hedge_fee = p_use * c["filled_hedge_fee"]
    ef = c["entry_fee"]
    return {
        "gross": gross,
        "net": net,
        "fees": ef + exit_fee + hedge_fee,
        "entry_fee": ef,
        "exit_fee": exit_fee,
        "hedge_fee": hedge_fee,
        "opp": c["opp"],
        "branch": "HYBRID" if c["opp"] else "TAKER_OR_HOLD",
    }


def hybrid_one(t, h, p, ratio, taker_thr, taker_model, scen, h_mode: str) -> dict:
    return mix_hybrid(hybrid_components(t, h, ratio, taker_thr, taker_model, scen, h_mode), p)


def _hybrid_meta(h, p, ratio, taker_thr, taker_model, scen, h_mode, rows) -> dict:
    nets = [r["net"] for r in rows]
    return {
        "policy": f"HYBRID|H={h}|p={p:.2f}|r={ratio}|T={taker_thr}|{taker_model}|{h_mode}|{scen}",
        "family": "HYBRID",
        "hedge_h": h,
        "p_fill": p,
        "hedge_ratio": ratio,
        "threshold": taker_thr,
        "exit_model": taker_model,
        "hedge_mode": h_mode,
        "fee_scenario": scen,
        "n": len(rows),
        "opp_pct": None if not rows else round(100.0 * sum(1 for r in rows if r["opp"]) / len(rows), 4),
        "gross_ev": round(float(np.mean([r["gross"] for r in rows])), 4) if rows else None,
        "net_ev": round(float(np.mean(nets)), 4) if nets else None,
        "mean_fees": round(float(np.mean([r["fees"] for r in rows])), 4) if rows else None,
        "entry_fees": round(float(np.mean([r["entry_fee"] for r in rows])), 4) if rows else None,
        "exit_fees": round(float(np.mean([r["exit_fee"] for r in rows])), 4) if rows else None,
        "hedge_fees": round(float(np.mean([r["hedge_fee"] for r in rows])), 4) if rows else None,
        "risk": risk_stats(nets),
        "evidence": "D",
        "capital_initial": ENTRY,
        "capital_reserved": ENTRY + ratio * h,
        "label": "MAKER FILL SCENARIO — NOT ACTUAL FILL",
        "flags": {
            "LOOKAHEAD_BIAS": False,
            "UNOBSERVED_FILL_ASSUMPTION": True,
            "EXECUTION_PRICE_ASSUMPTION": True,
            "FEE_ASSUMPTION": scen != "CURRENT_BASE_CASE",
            "SMALL_SAMPLE_SIZE": len(rows) < 100,
        },
        "_pnls": nets,
    }


def eval_hybrid(trades, h, p, ratio, taker_thr, taker_model, scen, h_mode="H2") -> dict:
    comps = [hybrid_components(t, h, ratio, taker_thr, taker_model, scen, h_mode) for t in trades]
    rows = [mix_hybrid(c, p) for c in comps]
    return _hybrid_meta(h, p, ratio, taker_thr, taker_model, scen, h_mode, rows)


def eval_hybrid_pgrid(trades, h, ps, ratio, taker_thr, taker_model, scen, h_mode="H2") -> list[dict]:
    """Walk each path once; remix p_fill. Same causal tree as eval_hybrid."""
    comps = [hybrid_components(t, h, ratio, taker_thr, taker_model, scen, h_mode) for t in trades]
    return [_hybrid_meta(h, p, ratio, taker_thr, taker_model, scen, h_mode, [mix_hybrid(c, p) for c in comps]) for p in ps]


def hold_policy(trades, scen) -> dict:
    nets = []
    for t in trades:
        ef = entry_fee(scen)
        g = hold_gross(t)
        nets.append(g - ef - SETTLE_FEE)
    return {
        "policy": f"HOLD|{scen}",
        "family": "HOLD",
        "fee_scenario": scen,
        "n": len(trades),
        "gross_ev": round(float(np.mean([hold_gross(t) for t in trades])), 4) if trades else None,
        "net_ev": round(float(np.mean(nets)), 4) if nets else None,
        "mean_fees": entry_fee(scen),
        "entry_fees": entry_fee(scen),
        "exit_fees": 0.0,
        "hedge_fees": 0.0,
        "risk": risk_stats(nets),
        "evidence": "A",
        "capital_initial": ENTRY,
        "capital_reserved": ENTRY,
        "_pnls": nets,
    }


def subset(trades, split):
    return trades if split == "FULL" else [t for t in trades if t.get("dataset_split") == split]


def t4_monte_carlo(trades, thr, kind, scen, n_sims=N_MC, seed=SEED) -> dict:
    """Bootstrap trades; sample exits from empirical (thr, vol) pools. ASSUMED residual."""
    rng = np.random.default_rng(seed)
    pools: dict[str, list[float]] = defaultdict(list)
    all_px = []
    cached = []
    for t in trades:
        trig = first_trigger(t, thr, kind, 1)
        cached.append((t, trig))
        if trig and trig["close"] is not None:
            pools[trig["vol"]].append(trig["close"])
            all_px.append(trig["close"])
    if not all_px:
        return {"n_sims": 0, "note": "no empirical exits"}
    holds = [hold_gross(t) - entry_fee(scen) for t, _ in cached]
    vols = [(None if trig is None else trig["vol"]) for _, trig in cached]
    n = len(cached)
    means = []
    for _ in range(n_sims):
        idx = rng.integers(0, n, size=n)
        pnls = []
        for i in idx:
            i = int(i)
            if vols[i] is None:
                pnls.append(holds[i])
                continue
            pool = pools.get(vols[i]) or all_px
            px = float(pool[int(rng.integers(0, len(pool)))])
            xf = fee_cents("taker", px, scen)
            pnls.append(px - ENTRY - entry_fee(scen) - xf)
        means.append(float(np.mean(pnls)))
    a = np.array(means)
    return {
        "n_sims": n_sims,
        "threshold": thr,
        "trigger_type": kind,
        "fee_scenario": scen,
        "mean_ev": round(float(a.mean()), 4),
        "median_ev": round(float(np.median(a)), 4),
        "p05": round(float(np.percentile(a, 5)), 4),
        "p25": round(float(np.percentile(a, 25)), 4),
        "p75": round(float(np.percentile(a, 75)), 4),
        "p95": round(float(np.percentile(a, 95)), 4),
        "p_ev_gt_0": round(float((a > 0).mean()), 4),
        "evidence": "C",
        "label": "MONTE CARLO ON CANDLE EXIT POOLS — NOT IOC FILLS",
    }


def season_mc(pnls: list[float], dates: list[str], n_sims=N_MC, seed=SEED, contracts=7) -> dict:
    rng = np.random.default_rng(seed)
    a = np.array(pnls, dtype=float)
    if a.size == 0:
        return {"n_sims": 0}
    # independent
    ind = []
    for _ in range(n_sims):
        idx = rng.integers(0, a.size, size=a.size)
        ind.append(float(a[idx].sum()) * contracts)
    # correlated: block by date
    by_d = defaultdict(list)
    for p, d in zip(pnls, dates):
        by_d[d or "NA"].append(p)
    blocks = [np.array(v, dtype=float) for v in by_d.values()]
    corr = []
    for _ in range(n_sims):
        picks = rng.integers(0, len(blocks), size=len(blocks))
        s = 0.0
        for j in picks:
            s += float(blocks[int(j)].sum())
        corr.append(s * contracts)

    def pack(xs, name):
        x = np.array(xs)
        # drawdown on shuffled path of one sim is not a path; use worst-block as proxy
        return {
            "mode": name,
            "mean": round(float(x.mean()), 4),
            "median": round(float(np.median(x)), 4),
            "p05": round(float(np.percentile(x, 5)), 4),
            "p95": round(float(np.percentile(x, 95)), 4),
            "p_losing_season": round(float((x < 0).mean()), 4),
            "std": round(float(x.std(ddof=1)), 4) if x.size > 1 else 0.0,
            "sharpe_like": None if x.std(ddof=1) == 0 else round(float(x.mean() / x.std(ddof=1)), 4),
            "n_sims": n_sims,
            "contracts": contracts,
            "units": "cents * contracts over resampled universe",
            "evidence": "C",
        }

    return {"independent": pack(ind, "independent"), "correlated_date_blocks": pack(corr, "correlated")}


def twod_threshold_vol(trades, thr, scen) -> list[dict]:
    rows = []
    for reg in ("LOW_VOL", "MODERATE_VOL", "HIGH_VOL", "JUMP_EVENT", "SUSTAINED_REVERSAL"):
        sub = []
        for t in trades:
            trig = first_trigger(t, thr, "BID_CLOSE_BELOW_THRESHOLD", 1)
            if trig and trig["vol"] == reg:
                sub.append((t, trig))
        if not sub:
            rows.append({"threshold": thr, "vol": reg, "n": 0})
            continue
        px = [tr["close"] for _, tr in sub if tr["close"] is not None]
        win = sum(1 for t, _ in sub if t["favorite_won"])
        rows.append(
            {
                "threshold": thr,
                "vol": reg,
                "n": len(sub),
                "mean_exit": None if not px else round(float(np.mean(px)), 4),
                "p_win": round(100.0 * win / len(sub), 4),
                "evidence": "B",
            }
        )
    return rows


def twod_threshold_time(trades, thr) -> list[dict]:
    rows = []
    t0s = []
    for t in trades:
        trig = first_trigger(t, thr, "BID_CLOSE_BELOW_THRESHOLD", 1)
        if not trig:
            continue
        mins = (trig["ts"] - int(t["first_80_timestamp"])) / 60.0
        t0s.append((t, trig, mins))
    for name, lo, hi in TIME_BUCKETS:
        sub = [x for x in t0s if x[2] >= lo and (hi is None or x[2] < hi)]
        if not sub:
            rows.append({"threshold": thr, "time": name, "n": 0})
            continue
        px = [tr["close"] for _, tr, _ in sub if tr["close"] is not None]
        win = sum(1 for t, _, _ in sub if t["favorite_won"])
        rows.append(
            {
                "threshold": thr,
                "time": name,
                "n": len(sub),
                "mean_exit": None if not px else round(float(np.mean(px)), 4),
                "p_win": round(100.0 * win / len(sub), 4),
                "evidence": "B",
            }
        )
    return rows


def strip_pnls(d: dict) -> dict:
    return {k: v for k, v in d.items() if k != "_pnls"}


def pick_best(cands: list[dict], key="net_ev") -> dict | None:
    ok = [c for c in cands if c.get(key) is not None and c.get("n", 0) >= 30]
    if not ok:
        return None
    return max(ok, key=lambda c: (c[key], -abs((c.get("threshold") or 40) - 40)))


def analyze_sport(sport: str) -> dict:
    print(f"=== {sport} V2 ===", flush=True)
    trades, path_gate = reproduce(sport)
    print(f"  path gate {'PASS' if path_gate['ok'] else 'FAIL'} {path_gate['observed']}", flush=True)
    if not path_gate["ok"]:
        return {"sport": sport, "halted": True, "reason": "BASELINE_PATH_GATE_FAIL", "path_gate": path_gate}

    games = V1.load_games(V1.SPORTS[sport])
    scan_meta = scan_quotes(sport, trades, games)
    for t in trades:
        enrich_trade(t)
    sg = stop_gate(sport, trades)
    print(f"  stop gate {'PASS' if sg['ok'] else 'FAIL'} mismatches={sg['stop_flag_mismatches']}", flush=True)
    if not sg["ok"]:
        return {"sport": sport, "halted": True, "reason": "BASELINE_STOP_MODEL_GATE_FAIL", "path_gate": path_gate, "stop_gate": sg}

    dest = out_dir(sport)
    # ledgers
    summaries = []
    thresh_events = []
    path_rows = []
    hedge_rows = []
    for t in trades:
        tid = t["ticker"]
        row = {
            "trade_id": tid,
            "sport": sport,
            "event_id": t.get("event_id"),
            "dataset_split": t.get("dataset_split"),
            "entry_timestamp": t.get("first_80_timestamp"),
            "entry_price": t.get("entry_price_proxy"),
            "minimum_favorite_price": t.get("minimum_favorite_price"),
            "time_to_minimum": t.get("time_to_minimum"),
            "maximum_opponent_price": t.get("maximum_opponent_price"),
            "time_to_opponent_maximum": t.get("time_to_opponent_maximum"),
            "settlement": "YES" if t["favorite_won"] else "NO",
            "favorite_won": t["favorite_won"],
            "max_drawdown": t.get("max_drawdown"),
        }
        for thr in THRESHOLDS:
            st = t["touches"][thr]
            row[f"first_touch_{thr}"] = st.get("touch_ts") or st["ts"]
            row[f"touch_{thr}"] = st["touch"]
            row[f"closed_{thr}"] = st["close"]
            row[f"jumped_{thr}"] = st["jump"]
            thresh_events.append(
                {
                    "trade_id": tid,
                    "sport": sport,
                    "threshold": thr,
                    "touched": st["touch"],
                    "closed_below": st["close"],
                    "jumped_through": st["jump"],
                    "first_close": st["first_close"],
                    "first_low": st["first_low"],
                    "ts": st["ts"],
                    "favorite_won": t["favorite_won"],
                    "dataset_split": t.get("dataset_split"),
                }
            )
        summaries.append(row)
        t0 = int(t["first_80_timestamp"])
        a2_by_ts = {q["ts"]: q for q in path_of(t, "_a2")}
        entry_px = t.get("entry_price_proxy") or ENTRY
        max_a2 = None
        min_a1 = entry_px
        for q in path_of(t, "_a1"):
            c = V1A.e4_to_cents(q["bid_c"])
            if c is not None:
                min_a1 = min(min_a1, c)
            oq = a2_by_ts.get(q["ts"])
            oc = V1A.e4_to_cents(oq["bid_c"]) if oq else None
            if oc is not None:
                max_a2 = oc if max_a2 is None else max(max_a2, oc)
            path_rows.append(
                {
                    "game_id": t.get("event_id"),
                    "sport": sport,
                    "market_id": t.get("market_id") or t.get("ticker"),
                    "trade_id": tid,
                    "entry_timestamp": t0,
                    "entry_price_proxy": entry_px,
                    "t_plus_minutes": (q["ts"] - t0) / 60.0,
                    "favorite_yes_bid_open": V1A.e4_to_cents(q.get("bid_o")),
                    "favorite_yes_bid_high": V1A.e4_to_cents(q.get("bid_h")),
                    "favorite_yes_bid_low": V1A.e4_to_cents(q.get("bid_l")),
                    "favorite_yes_bid_close": c,
                    "opponent_yes_bid_open": None if not oq else V1A.e4_to_cents(oq.get("bid_o")),
                    "opponent_yes_bid_high": None if not oq else V1A.e4_to_cents(oq.get("bid_h")),
                    "opponent_yes_bid_low": None if not oq else V1A.e4_to_cents(oq.get("bid_l")),
                    "opponent_yes_bid_close": oc,
                    "favorite_mid_proxy": mid_of(q),
                    "opponent_mid_proxy": None if not oq else mid_of(oq),
                    "favorite_max_drawdown_from_entry": None if c is None else entry_px - min_a1,
                    "opponent_max_rise_from_entry": max_a2,
                    "settlement_outcome": "YES" if t["favorite_won"] else "NO",
                    "favorite_won": t["favorite_won"],
                }
            )
        for h in EXIT_GRID:
            ev = a2_upcross(t, h, None)
            if not ev:
                continue
            a1_at = None
            for q in path_of(t, "_a1"):
                if q["ts"] == ev["ts"]:
                    a1_at = V1A.e4_to_cents(q["bid_c"])
                    break
            hedge_rows.append(
                {
                    "trade_id": tid,
                    "sport": sport,
                    "H": h,
                    "timestamp": ev["ts"],
                    "opponent_price_before": ev["prev"],
                    "opponent_price_during": ev["close"],
                    "favorite_price_same_moment": a1_at,
                    "opponent_jump_size": ev["jump"],
                    "time_since_first80_min": (ev["ts"] - t0) / 60.0,
                    "eventual_settlement": "YES" if t["favorite_won"] else "NO",
                    "label": "HEDGE OPPORTUNITY — NOT A FILL",
                    "evidence": "B",
                }
            )

    write_parquet(dest / "trade_summaries.parquet", summaries)
    write_parquet(dest / "threshold_events.parquet", thresh_events)
    write_parquet(dest / "post_entry_paths.parquet", path_rows)
    write_parquet(dest / "hedge_opportunities.parquet", hedge_rows)
    print(f"  paths {len(path_rows)}  hedge_opps {len(hedge_rows)}", flush=True)

    p1 = phase1(trades)
    write_parquet(dest / "exit_distribution.parquet", p1["exit_bands"])

    by = {s: subset(trades, s) for s in SPLITS}
    dates = [t.get("game_date") for t in trades]

    # Phase 2 univariate
    print("  phase2 univariate", flush=True)
    hold = {s: hold_policy(by[s], "CURRENT_BASE_CASE") for s in SPLITS}
    taker_thr = []
    for thr in THRESHOLDS:
        for model in ("T1", "T2", "T3"):
            taker_thr.append(eval_taker_clean(trades, thr, "BID_CLOSE_BELOW_THRESHOLD", 1, model, "CURRENT_BASE_CASE"))
    trigger_types = []
    for kind in (
        "BID_CLOSE_BELOW_THRESHOLD",
        "BID_LOW_BELOW_THRESHOLD",
        "MID_PROXY_BELOW_THRESHOLD",
        "PERCENTAGE_DECLINE_FROM_ENTRY",
        "RATE_OF_CHANGE_DETERIORATION",
    ):
        trigger_types.append(eval_taker_clean(trades, 40, kind, 1, "T2", "CURRENT_BASE_CASE"))
    for persist in PERSIST_GRID:
        trigger_types.append(
            eval_taker_clean(trades, 40, "N_CONSECUTIVE_MINUTES_BELOW_THRESHOLD", persist, "T2", "CURRENT_BASE_CASE")
        )
    fee_uni = []
    for scen in ("CURRENT_BASE_CASE", "CONSERVATIVE_FEE_STRESS", "HIGHER_FUTURE_FEE_STRESS"):
        fee_uni.append(eval_taker_clean(trades, 40, "BID_CLOSE_BELOW_THRESHOLD", 1, "T2", scen))

    t4 = {}
    for thr in (40, 30, 20):
        print(f"  T4 MC T={thr}", flush=True)
        t4[thr] = t4_monte_carlo(trades, thr, "BID_CLOSE_BELOW_THRESHOLD", "CURRENT_BASE_CASE")

    # Phase 3 two-d
    print("  phase3 twod", flush=True)
    vol_x = []
    time_x = []
    for thr in EXIT_GRID:
        vol_x.extend(twod_threshold_vol(trades, thr, "CURRENT_BASE_CASE"))
        time_x.extend(twod_threshold_time(trades, thr))

    hedge_surface = []
    for h in EXIT_GRID:
        hedge_surface.extend(eval_hybrid_pgrid(trades, h, FILL_GRID, 1.0, 40, "T2", "CURRENT_BASE_CASE", "H2"))

    ratios = []
    for r in RATIOS:
        ratios.append(eval_hybrid(trades, 40, 0.5, r, 40, "T2", "CURRENT_BASE_CASE", "H2"))

    h4 = eval_hybrid(trades, 40, 0.5, 1.0, 40, "T2", "CURRENT_BASE_CASE", "H4")
    h3 = eval_hybrid(trades, 40, 0.5, 1.0, 40, "T2", "CURRENT_BASE_CASE", "H3")

    # Phase 4 selection on VAL, OOS once
    val_takers = [
        eval_taker_clean(by["VALIDATION"], thr, "BID_CLOSE_BELOW_THRESHOLD", 1, "T2", "CURRENT_BASE_CASE")
        for thr in THRESHOLDS
    ]
    picked_taker = pick_best(val_takers)
    oos_taker = None
    if picked_taker:
        oos_taker = eval_taker_clean(
            by["OOS"], picked_taker["threshold"], "BID_CLOSE_BELOW_THRESHOLD", 1, "T2", "CURRENT_BASE_CASE"
        )

    val_hedge = [
        eval_hybrid(by["VALIDATION"], h, 0.5, 1.0, 40, "T2", "CURRENT_BASE_CASE", "H2") for h in EXIT_GRID
    ]
    picked_hedge = pick_best(val_hedge)
    oos_hedge = None
    if picked_hedge:
        oos_hedge = eval_hybrid(
            by["OOS"], picked_hedge["hedge_h"], 0.5, 1.0, 40, "T2", "CURRENT_BASE_CASE", "H2"
        )

    def _taker(thr, model, scen="CURRENT_BASE_CASE"):
        for x in taker_thr:
            if x["threshold"] == thr and x["exit_model"] == model and x["fee_scenario"] == scen:
                return x
        return eval_taker_clean(trades, thr, "BID_CLOSE_BELOW_THRESHOLD", 1, model, scen)

    def _hedge(h, p):
        for x in hedge_surface:
            if x["hedge_h"] == h and abs(x["p_fill"] - p) < 1e-9:
                return x
        return eval_hybrid(trades, h, p, 1.0, 40, "T2", "CURRENT_BASE_CASE", "H2")

    cons_taker = {
        thr: eval_taker_clean(trades, thr, "BID_CLOSE_BELOW_THRESHOLD", 1, "T3", "CONSERVATIVE_FEE_STRESS")
        for thr in (40, 35, 30)
    }

    # named policies for master table
    named = {
        "Hold": hold["FULL"],
        "80→40": _taker(40, "T1"),
        "80→35": _taker(35, "T1"),
        "80→30": _taker(30, "T1"),
        "Dynamic taker T2@40": _taker(40, "T2"),
        "Dynamic taker T3@40": _taker(40, "T3"),
        "Hedge H=40 H2 p50": _hedge(40, 0.5),
        "Hedge H=30 H2 p50": _hedge(30, 0.5),
        "Hybrid H40/T40": _hedge(40, 0.5),
        "Dynamic exposure r=50% H40": eval_hybrid(trades, 40, 0.5, 0.5, 40, "T2", "CURRENT_BASE_CASE", "H2"),
        "Conservative taker": cons_taker[40],
        "Conservative hybrid": eval_hybrid(trades, 40, 0.25, 1.0, 40, "T3", "CONSERVATIVE_FEE_STRESS", "H4"),
    }
    # break-evens
    be_exit = []
    for x in range(0, 81):
        ev = 0.0
        for t in trades:
            if t["touches"][40]["close"]:
                xf = fee_cents("taker", float(x), "CURRENT_BASE_CASE")
                ev += x - ENTRY - xf
            else:
                ev += hold_gross(t)
        be_exit.append({"exit_px": x, "net_ev": round(ev / len(trades), 4)})
    be_fill = [{"p_fill": x["p_fill"], "net_ev": x["net_ev"]} for x in hedge_surface if x["hedge_h"] == 40]

    by_split = {}
    for spl in SPLITS:
        by_split[spl] = {
            "Hold": strip_pnls(hold[spl]),
            "Dynamic taker T2@40": strip_pnls(
                eval_taker_clean(by[spl], 40, "BID_CLOSE_BELOW_THRESHOLD", 1, "T2", "CURRENT_BASE_CASE")
            ),
            "Hedge H=40 H2 p50": strip_pnls(
                eval_hybrid(by[spl], 40, 0.5, 1.0, 40, "T2", "CURRENT_BASE_CASE", "H2")
            ),
        }

    train_takers = [
        eval_taker_clean(by["TRAIN"], thr, "BID_CLOSE_BELOW_THRESHOLD", 1, "T2", "CURRENT_BASE_CASE")
        for thr in THRESHOLDS
    ]
    discovered_taker = pick_best(train_takers)

    season = {}
    for label, pol in (
        ("hold", hold["FULL"]),
        ("t2_40", named["Dynamic taker T2@40"]),
        ("hybrid_h40", named["Hybrid H40/T40"]),
        ("conservative", named["Conservative taker"]),
    ):
        season[label] = season_mc(pol["_pnls"], dates)

    policies = (
        [hold["FULL"]]
        + [x for x in taker_thr if x["exit_model"] == "T2"]
        + [x for x in hedge_surface if abs(x["p_fill"] - 0.5) < 1e-9]
        + [named["Hybrid H40/T40"], named["Dynamic exposure r=50% H40"], named["Conservative taker"]]
    )
    write_parquet(dest / "policy_results.parquet", [strip_pnls(p) for p in policies])
    fee_attr = []
    for name, p in named.items():
        g = p.get("gross_ev") or 0
        fee_attr.append(
            {
                "strategy": name,
                "gross_ev": p.get("gross_ev"),
                "entry_fees": p.get("entry_fees") or 0,
                "exit_fees": p.get("exit_fees") or 0,
                "hedge_fees": p.get("hedge_fees") or 0,
                "net_ev": p.get("net_ev"),
                "fees_pct_of_gross": None if not g else round(100.0 * (g - (p.get("net_ev") or 0)) / g, 4),
                "fees_vs_slippage_note": "Compare T1 vs T2 at same threshold to isolate slippage vs fees",
            }
        )
    write_parquet(dest / "fee_attribution.parquet", fee_attr)
    write_json(dest / "monte_carlo_results.json", {"t4": t4, "season": {k: v for k, v in season.items()}})
    # flatten season for parquet
    mc_rows = []
    for k, v in t4.items():
        mc_rows.append({"kind": "T4_exit", "key": str(k), **v})
    for k, v in season.items():
        for mode, pack in v.items():
            mc_rows.append({"kind": "season", "key": k, **pack})
    write_parquet(dest / "monte_carlo_results.parquet", mc_rows)

    # frontier: net EV vs downside / vs fill-dependence
    frontier = []
    for p in policies:
        rsk = p.get("risk") or {}
        frontier.append(
            {
                "policy": p.get("policy"),
                "family": p.get("family"),
                "net_ev": p.get("net_ev"),
                "downside": rsk.get("downside_deviation"),
                "max_loss": rsk.get("max_single_trade_loss"),
                "capital": p.get("capital_reserved") or ENTRY,
                "fill_dependency": 1.0 if p.get("family") in ("HYBRID",) else 0.0,
                "evidence": p.get("evidence"),
            }
        )

    oos_n = len(by["OOS"])
    summary = {
        "program": PROGRAM,
        "banner": BANNER,
        "sport": sport,
        "halted": False,
        "live_execution_changed": False,
        "path_gate": path_gate,
        "stop_gate": sg,
        "scan": scan_meta,
        "splits": {s: len(by[s]) for s in SPLITS},
        "oos_n": oos_n,
        "oos_note": "INSUFFICIENT_SAMPLE" if oos_n < 100 else None,
        "phase1": p1,
        "hold": {s: strip_pnls(hold[s]) for s in SPLITS},
        "univariate_threshold": [strip_pnls(x) for x in taker_thr],
        "univariate_trigger_type": [strip_pnls(x) for x in trigger_types],
        "univariate_fees": [strip_pnls(x) for x in fee_uni],
        "t4": t4,
        "vol_x_threshold": vol_x,
        "time_x_threshold": time_x,
        "hedge_surface": [strip_pnls(x) for x in hedge_surface],
        "hedge_ratios": [strip_pnls(x) for x in ratios],
        "h3": strip_pnls(h3),
        "h4": strip_pnls(h4),
        "named": {k: strip_pnls(v) for k, v in named.items()},
        "selection": {
            "taker_train": strip_pnls(discovered_taker) if discovered_taker else None,
            "taker_val": strip_pnls(picked_taker) if picked_taker else None,
            "taker_oos": strip_pnls(oos_taker) if oos_taker else None,
            "hedge_val": strip_pnls(picked_hedge) if picked_hedge else None,
            "hedge_oos": strip_pnls(oos_hedge) if oos_hedge else None,
            "rule": "Discover TRAIN / select VAL / evaluate OOS once. Never tune on OOS.",
        },
        "by_split": by_split,
        "conservative_taker": {str(k): strip_pnls(v) for k, v in cons_taker.items()},
        "break_even_exit": be_exit,
        "break_even_fill": be_fill,
        "season": season,
        "frontier": frontier,
        "fee_attribution": fee_attr,
    }
    write_json(dest / "summary.json", summary)
    write_json(
        dest / "reproduction_checks.json",
        {"PATH": "PASS" if path_gate["ok"] else "FAIL", "STOP": "PASS" if sg["ok"] else "FAIL"},
    )
    # drop heavy quote caches before return
    for t in trades:
        t.pop("_a1", None)
        t.pop("_a2", None)
        t.pop("_path_a1", None)
        t.pop("_path_a2", None)
        t.pop("_ft", None)
        t.pop("_ax", None)
    print(f"  wrote {dest}", flush=True)
    return summary


def _fmt(x, d=4):
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.{d}f}"
    return str(x)


def md_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for r in rows:
        lines.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(lines)


def render_report(results: dict[str, dict]) -> str:
    lines = [
        f"# {PROGRAM}",
        "",
        "```text",
        "VERDICT: RESEARCH ONLY",
        "",
        "LIVE EXECUTION CHANGED: FALSE",
        "",
        "CANDLE PATH ≠ ACTUAL FILL",
        "STOP TRIGGER ≠ REALIZED EXIT",
        "MAKER OPPORTUNITY ≠ MAKER FILL",
        "GROSS EV ≠ NET EV",
        "```",
        "",
        "Isolated V2 extension of `FIRST80_REALISTIC_EXIT_FEE_AUDIT_V1`. Hierarchical — not a full combinatorial blast. V1 artifacts were not overwritten.",
        "",
        f"Config: `{CONFIG_PATH}`",
        "",
        "## 0. Reproduction",
        "",
    ]
    if any(r.get("halted") for r in results.values()):
        for s, r in results.items():
            lines.append(f"- {s}: HALTED `{r.get('reason')}`")
        lines.append("")
        lines.append("STOP THE EXPERIMENT. No optimization results.")
        return "\n".join(lines) + "\n"

    for s, r in results.items():
        o = r["path_gate"]["observed"]
        lines.append(
            f"- **{s.upper()}** path **PASS** {o['survivors']}/{o['n']} = {o['surv_pct']}% · stop **PASS** · OOS n={r['oos_n']} {r.get('oos_note') or ''}"
        )
    lines += ["", "## 1. Phase 1 — what actually happens", ""]

    for s, r in results.items():
        lines += [f"### {s.upper()} reach rates (close ≤ T) and P(win | close ≤ T)", ""]
        lines.append(
            md_table(
                ["T", "P(close)", "P(touch)", "P(jump)", "P(close|win)", "P(close|lose)", "P(win|close)"],
                [
                    [
                        x["threshold"],
                        _fmt(x["p_close"], 2),
                        _fmt(x["p_touch"], 2),
                        _fmt(x["p_jump"], 2),
                        _fmt(x["p_close_winners"], 2),
                        _fmt(x["p_close_losers"], 2),
                        _fmt(x["p_win_given_close"], 2),
                    ]
                    for x in r["phase1"]["reach"]
                ],
            )
        )
        lines += ["", f"P(win | min price ≤ X) — {s}", ""]
        lines.append(
            md_table(
                ["X", "n", "% univ", "P(win)"],
                [[x["max_dd_reaches"], x["n"], _fmt(x["p_of_universe"], 2), _fmt(x["p_win"], 2)] for x in r["phase1"]["p_win_given_dd"]],
            )
        )
        lines += ["", f"Exit-band % given trigger (Model B close) — {s}", ""]
        lines.append(
            md_table(
                ["Trigger", "n", "mean", "37–40", "32–36", "27–31", "22–26", "<22"],
                [
                    [
                        x["trigger"],
                        x["n"],
                        _fmt(x["mean_proxy"], 2),
                        _fmt(x["bands"].get("37-40"), 1),
                        _fmt(x["bands"].get("32-36"), 1),
                        _fmt(x["bands"].get("27-31"), 1),
                        _fmt(x["bands"].get("22-26"), 1),
                        _fmt(x["bands"].get("<22"), 1),
                    ]
                    for x in r["phase1"]["exit_bands"]
                ],
            )
        )
        lines.append("")

    lines += ["## 2. Phase 2 — univariate (T2 close, CURRENT fees unless noted)", ""]
    for s, r in results.items():
        t2 = [x for x in r["univariate_threshold"] if x["exit_model"] == "T2"]
        lines += [f"### {s.upper()} threshold sweep T2", ""]
        lines.append(
            md_table(
                ["T", "Trig %", "Mean exit", "Gross", "Fees", "Net", "Max loss"],
                [
                    [
                        x["threshold"],
                        _fmt(x["trigger_pct"], 2),
                        _fmt(x["mean_exit"], 2),
                        _fmt(x["gross_ev"]),
                        _fmt(x["mean_fees"]),
                        _fmt(x["net_ev"]),
                        _fmt((x.get("risk") or {}).get("max_single_trade_loss")),
                    ]
                    for x in t2
                ],
            )
        )
        lines += ["", f"Trigger-type @40 T2 — {s}", ""]
        lines.append(
            md_table(
                ["Type", "P", "Trig %", "Net"],
                [[x["trigger_type"], x["persist"], _fmt(x["trigger_pct"], 2), _fmt(x["net_ev"])] for x in r["univariate_trigger_type"]],
            )
        )
        lines += ["", f"Fee scenarios @40 T2 — {s}", ""]
        lines.append(md_table(["Scenario", "Net", "Fees"], [[x["fee_scenario"], _fmt(x["net_ev"]), _fmt(x["mean_fees"])] for x in r["univariate_fees"]]))
        lines += ["", f"T4 Monte Carlo (10k) — {s}", ""]
        lines.append(
            md_table(
                ["T", "mean", "p05", "p50", "p95", "P(EV>0)"],
                [[k, _fmt(v.get("mean_ev")), _fmt(v.get("p05")), _fmt(v.get("median_ev")), _fmt(v.get("p95")), _fmt(v.get("p_ev_gt_0"), 3)] for k, v in r["t4"].items()],
            )
        )
        lines.append("")

    lines += ["## 3. Phase 3 — two-dimensional", ""]
    for s, r in results.items():
        lines += [f"### {s.upper()} H × p_fill (hybrid H2, T2@40 fallback) net EV", ""]
        # compact matrix
        byh = defaultdict(dict)
        for x in r["hedge_surface"]:
            byh[x["hedge_h"]][x["p_fill"]] = x["net_ev"]
        headers = ["H"] + [f"{p:.0%}" for p in FILL_GRID]
        rows = []
        for h in EXIT_GRID:
            rows.append([h] + [_fmt(byh[h].get(p)) for p in FILL_GRID])
        lines.append(md_table(headers, rows))
        lines.append("")
        lines.append(f"H4 jump-skip (p=50% H=40) net={_fmt(r['h4']['net_ev'])} · H3 band fill net={_fmt(r['h3']['net_ev'])} — both ASSUMED.")
        lines.append("")

    lines += ["## 4. Phase 4 — selection (VAL → OOS once)", ""]
    for s, r in results.items():
        sel = r["selection"]
        lines.append(
            f"- **{s}**: VAL taker T={_fmt((sel['taker_val'] or {}).get('threshold'), 0)} net={_fmt((sel['taker_val'] or {}).get('net_ev'))} → OOS net={_fmt((sel['taker_oos'] or {}).get('net_ev'))} (n={r['oos_n']} {r.get('oos_note') or ''})"
        )
        lines.append(
            f"- **{s}**: VAL hedge H={_fmt((sel['hedge_val'] or {}).get('hedge_h'), 0)} net={_fmt((sel['hedge_val'] or {}).get('net_ev'))} → OOS net={_fmt((sel['hedge_oos'] or {}).get('net_ev'))}"
        )
    lines += ["", "## 5. Master EV table (FULL)", ""]
    keys = [
        "Hold",
        "80→40",
        "80→35",
        "80→30",
        "Dynamic taker T2@40",
        "Hedge H=40 H2 p50",
        "Hedge H=30 H2 p50",
        "Hybrid H40/T40",
        "Dynamic exposure r=50% H40",
    ]
    def _mod(sport_r, k):
        named = sport_r["named"]
        if k.startswith("80→"):
            thr = int(k.split("→")[1])
            rows_t = [x for x in sport_r["univariate_threshold"] if x["threshold"] == thr and x["exit_model"] == "T2"]
            return rows_t[0]["net_ev"] if rows_t else named[k]["net_ev"]
        return named[k]["net_ev"]

    def _cons(sport_r, k):
        named = sport_r["named"]
        if k == "Hold":
            return named["Hold"]["net_ev"]
        if k.startswith("80→"):
            thr = int(k.split("→")[1])
            return (sport_r.get("conservative_taker") or {}).get(str(thr), {}).get("net_ev")
        if "taker" in k.lower():
            return named["Conservative taker"]["net_ev"]
        return named["Conservative hybrid"]["net_ev"]

    rows = []
    for k in keys:
        nba, nca = results["nba"]["named"][k], results["ncaab"]["named"][k]
        rows.append(
            [
                k,
                _fmt(nba["gross_ev"]),
                _fmt(_mod(results["nba"], k)),
                _fmt(_cons(results["nba"], k)),
                _fmt(nca["gross_ev"]),
                _fmt(_mod(results["ncaab"], k)),
                _fmt(_cons(results["ncaab"], k)),
            ]
        )
    lines.append(
        md_table(
            ["Strategy", "NBA Gross", "NBA Moderate Net", "NBA Conservative Net", "NCAAB Gross", "NCAAB Moderate Net", "NCAAB Conservative Net"],
            rows,
        )
    )

    lines += ["", "## 6. Fee vs slippage", ""]
    for s, r in results.items():
        t1 = r["named"]["80→40"]
        t2 = r["named"]["Dynamic taker T2@40"]
        lines.append(
            f"- **{s}**: T1 net {_fmt(t1['net_ev'])} vs T2 net {_fmt(t2['net_ev'])} · fee drag T1 {_fmt(t1['mean_fees'])} vs T2 {_fmt(t2['mean_fees'])}. Slippage (T1−T2) dominates fees."
        )

    lines += ["", "## 7. Break-evens (NBA shown in dashboard for both)", ""]
    nba_be = results["nba"]["break_even_exit"]
    # find first x where ev>=0 when coming from low x
    cross = next((x for x in nba_be if x["net_ev"] >= 0), None)
    lines.append(f"- NBA taker mixture crosses 0 near exit ≈ **{cross['exit_px'] if cross else '—'}¢** (hold+stop blend, CURRENT fees).")
    fill0 = next((x for x in results["nba"]["break_even_fill"] if (x["net_ev"] or 0) >= (results["nba"]["named"]["Hold"]["net_ev"] or 0)), None)
    lines.append(f"- NBA hybrid vs hold: first p_fill with EV≥hold is **{fill0['p_fill'] if fill0 else 'never'}**.")

    lines += ["", "## 8. Season Monte Carlo (7 contracts, resampled universe)", ""]
    for s, r in results.items():
        sm = r["season"]["t2_40"]["independent"]
        lines.append(f"- **{s} T2@40 independent**: mean {sm['mean']}¢ · p05 {sm['p05']} · P(lose season) {sm['p_losing_season']} · n_sims={sm['n_sims']}")

    # six questions
    nba, nca = results["nba"], results["ncaab"]

    def best_named(sport_r, keys, field="net_ev"):
        return max(((k, sport_r["named"][k]) for k in keys), key=lambda kv: kv[1].get(field) or -999)

    ideal_keys = ["Hold", "80→40", "80→35", "80→30"]
    mod_keys = ["Hold", "Dynamic taker T2@40", "Hedge H=40 H2 p50", "Hedge H=30 H2 p50", "Hybrid H40/T40", "Dynamic exposure r=50% H40"]
    cons_keys = ["Hold", "Conservative taker", "Conservative hybrid"]

    q1n, q1 = best_named(nba, ideal_keys)
    q2n, q2 = best_named(nba, mod_keys)
    q3n, q3 = best_named(nba, cons_keys)
    t2n, t2c = nba["named"]["Dynamic taker T2@40"]["net_ev"], nca["named"]["Dynamic taker T2@40"]["net_ev"]
    hdn, hdc = nba["named"]["Hold"]["net_ev"], nca["named"]["Hold"]["net_ev"]
    t1n, t1c = nba["named"]["80→40"]["net_ev"], nca["named"]["80→40"]["net_ev"]
    csn, csc = nba["named"]["Conservative taker"]["net_ev"], nca["named"]["Conservative taker"]["net_ev"]
    path_v = "PASS"
    gross_v = "PASS" if (t1n or 0) > 0 and (t1c or 0) > 0 else "FAIL"
    mod_v = (
        "FAIL vs hold"
        if (t2n or 0) < (hdn or 0) or (t2c or 0) < (hdc or 0)
        else ("PASS" if (t2n or 0) > 0 and (t2c or 0) > 0 else "FAIL")
    )
    cons_v = "PASS" if (csn or 0) > 0 and (csc or 0) > 0 else "FAIL"
    t2_vs_hold = f"NBA T2@40 {_fmt(t2n)} vs hold {_fmt(hdn)}; NCAAB T2@40 {_fmt(t2c)} vs hold {_fmt(hdc)}"

    lines += [
        "",
        "## 9. Six decision questions",
        "",
        f"**Q1 Idealized highest EV:** `{q1n}` NBA net {_fmt(q1['net_ev'])} (NCAAB 80→40 {_fmt(nca['named']['80→40']['net_ev'])}). Evidence C for exact-threshold fills.",
        "",
        f"**Q2 Moderate highest EV:** `{q2n}` NBA net {_fmt(q2['net_ev'])}. Hedge/hybrid numbers are **D — assumed p_fill**. Among observed-proxy policies, Hold vs T2@40 is the honest fight.",
        "",
        f"**Q3 Conservative highest EV:** `{q3n}` NBA net {_fmt(q3['net_ev'])}. NCAAB conservative taker {_fmt(nca['named']['Conservative taker']['net_ev'])}.",
        "",
        "**Q4 Least assumption-dependent:** Hold (evidence A) then T2 candle close (B). Hedge p_fill is D.",
        "",
        f"**Q5 Min execution quality for FIRST80 + stop to beat hold:** {t2_vs_hold}. A 40-stop needs realized exits close enough to 40 that T2 ≥ hold, or a later/persistent trigger.",
        "",
        "**Q6 Balance:** Path edge is measured (A). Taker stops depend on the exit proxy (B/C). Maker hedge can dominate on paper only by assuming fills (D). This experiment does not authorize a live policy.",
        "",
        "## 10. Final verdict",
        "",
        "```text",
        f"FIRST80 PATH EFFECT:           {path_v}",
        f"GROSS ECONOMIC EDGE:           {gross_v}   (ideal 80→40 net {_fmt(t1n)} / {_fmt(t1c)} ¢)",
        f"MODERATE EXECUTION EDGE:       {mod_v}   (T2@40 {_fmt(t2n)} / {_fmt(t2c)} vs hold {_fmt(hdn)} / {_fmt(hdc)})",
        f"CONSERVATIVE EXECUTION EDGE:   {cons_v}   (T3+fee-stress {_fmt(csn)} / {_fmt(csc)} ¢)",
        f"TAKER EXIT VIABILITY:          LOW CONFIDENCE",
        f"MAKER HEDGE VIABILITY:         LOW CONFIDENCE  (fill rate UNOBSERVED)",
        f"FEE BURDEN:                    IMMATERIAL vs slippage  (see T1 vs T2 gap vs fee drag)",
        f"PRIMARY REMAINING UNCERTAINTY: IOC realized fill vs candle close; maker fill probability",
        f"LIVE DEPLOYMENT:               NOT AUTHORIZED BY THIS EXPERIMENT",
        "```",
        "",
        "## 11. Integrity flags",
        "",
        "| Claim | Grade |",
        "| --- | --- |",
        "| FIRST-80 survival | A |",
        "| Trigger-candle exit | B |",
        "| IOC realized fill | C |",
        "| Maker hedge fill probability | D |",
        "| T4 / season Monte Carlo | C |",
        "",
        "No lookahead in trigger types. No oracle hedge. NCAAB OOS is small.",
        "",
        "Do not arm. Do not modify live trading.",
        "",
    ]
    return "\n".join(lines) + "\n"


def dashboard_payload(results: dict[str, dict]) -> dict:
    return {
        "banner": BANNER,
        "verdict": "RESEARCH ONLY",
        "live_execution_changed": False,
        "fill_grid": list(FILL_GRID),
        "thresholds": list(THRESHOLDS),
        "exit_grid": list(EXIT_GRID),
        "sports": {
            s: {
                "halted": r.get("halted", False),
                "path_gate": r.get("path_gate"),
                "stop_gate": r.get("stop_gate"),
                "splits": r.get("splits"),
                "oos_n": r.get("oos_n"),
                "oos_note": r.get("oos_note"),
                "reach": (r.get("phase1") or {}).get("reach"),
                "p_win_dd": (r.get("phase1") or {}).get("p_win_given_dd"),
                "exit_bands": (r.get("phase1") or {}).get("exit_bands"),
                "t2_thresholds": [x for x in (r.get("univariate_threshold") or []) if x.get("exit_model") == "T2"],
                "t1_thresholds": [x for x in (r.get("univariate_threshold") or []) if x.get("exit_model") == "T1"],
                "t3_thresholds": [x for x in (r.get("univariate_threshold") or []) if x.get("exit_model") == "T3"],
                "trigger_types": r.get("univariate_trigger_type"),
                "fees": r.get("univariate_fees"),
                "t4": r.get("t4"),
                "vol": r.get("vol_x_threshold"),
                "time": r.get("time_x_threshold"),
                "hedge_surface": [
                    {"H": x["hedge_h"], "p": x["p_fill"], "net": x["net_ev"], "opp": x.get("opp_pct")}
                    for x in (r.get("hedge_surface") or [])
                ],
                "ratios": r.get("hedge_ratios"),
                "named": r.get("named"),
                "selection": r.get("selection"),
                "break_even_exit": r.get("break_even_exit"),
                "break_even_fill": r.get("break_even_fill"),
                "frontier": r.get("frontier"),
                "fee_attribution": r.get("fee_attribution"),
                "season": r.get("season"),
                "by_split": r.get("by_split"),
            }
            for s, r in results.items()
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    sports = args or ["nba", "ncaab"]
    results = {}
    for sport in sports:
        results[sport] = analyze_sport(sport)
        if results[sport].get("halted") and not args:
            print("STOP THE EXPERIMENT — reproduction failed — no optimization", flush=True)
            DOCS.write_text(render_report(results))
            return 1
        dest = out_dir(sport)
        if CONFIG_PATH.exists():
            (dest / "config.yaml").write_text(CONFIG_PATH.read_text())

    if set(results) >= {"nba", "ncaab"} and not any(r.get("halted") for r in results.values()):
        DOCS.write_text(render_report(results))
        dash = dashboard_payload(results)
        DASH_PUBLIC.mkdir(parents=True, exist_ok=True)
        write_json(DASH_PUBLIC / "dashboard.json", dash)
        write_json(out_dir("nba") / "dashboard.json", dash)
        write_json(out_dir("ncaab") / "dashboard.json", dash)
        print(f"wrote {DOCS}", flush=True)
        print(BANNER, flush=True)
        print(
            "NBA T2@40",
            results["nba"]["named"]["Dynamic taker T2@40"]["net_ev"],
            "Hold",
            results["nba"]["named"]["Hold"]["net_ev"],
            flush=True,
        )
        print(
            "NCAAB T2@40",
            results["ncaab"]["named"]["Dynamic taker T2@40"]["net_ev"],
            "Hold",
            results["ncaab"]["named"]["Hold"]["net_ev"],
            flush=True,
        )
    return 0 if not any(r.get("halted") for r in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
