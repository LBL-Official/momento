#!/usr/bin/env python3
"""FIRST80_OPPONENT_HEDGE_EXECUTION_MODEL_V3

Test 4. Candle PRICE_OPPORTUNITY / FILL_OPPORTUNITY_QUALITY model.

Does not invent L2, queue, depth, or actual maker fills.
Does not modify V1, V2, liquidation v1, Game Path, FIRST01, Risk, or live execution.

LIVE EXECUTION CHANGED: FALSE
ACTUAL_FILL = UNOBSERVED
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
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import davies_bouldin_score, silhouette_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

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
V2 = _load("first80_frontier_v2_engine", HERE / "first80_opponent_hedge_frontier_v2.py")

PROGRAM = "FIRST80_OPPONENT_HEDGE_EXECUTION_MODEL_V3"
ENTRY = 80
WIN = 20
MISS = -80
H_MIN, H_MAX = 10, 60
H_ALL = list(range(H_MIN, H_MAX + 1))
H_FOCUS = (20, 28, 40)
P_GRID = [round(i / 10, 1) for i in range(11)]
PERSIST_MARKS = (1, 2, 3, 5, 10)
CLUSTER_H = 40
CLUSTER_KS = (3, 4, 5)
MIN_VAL_CLUSTER_N = 20
CORR_DROP = 0.92
UMAP_SAMPLE = 800
SPLIT_ORDER = ("TRAIN", "VALIDATION", "OOS", "FULL")

# A priori: cluster on path features only. No settlement. No P&L. No H*.
CLUSTER_FEATURES = [
    "touch_overshoot_high_cents",
    "touch_overshoot_close_cents",
    "persist_subsequent_min",
    "persist_ratio_10",
    "touch_range_cents",
    "path_velocity_in_cents",
    "path_velocity_out_cents",
    "vol_pre_cents",
    "vol_post_cents",
    "market_spread_cents",
    "reversal_minutes",
    "coupling_residual_cents",
]

DOCS = Path("/Users/user/Desktop/Momento/docs/research/FIRST80_OPPONENT_HEDGE_EXECUTION_MODEL_V3.md")
DOCS_TABLES = Path(
    "/Users/user/Desktop/Momento/docs/research/FIRST80_OPPONENT_HEDGE_EXECUTION_MODEL_V3_TABLES.md"
)
DASH_PUBLIC = Path(
    "/Users/user/Desktop/Momento/frontend/first80-hedge-execution-v3/public/data"
)


def e4(h: int) -> int:
    return h * 100


def out_dir(sport: str) -> Path:
    cfg = V1.SPORTS[sport]
    p = cfg["root"] / "derived" / cfg["norm"] / "first80_opponent_hedge_execution_model_v3"
    p.mkdir(parents=True, exist_ok=True)
    return p


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


def hold_pnl(won: bool) -> int:
    return WIN if won else MISS


def lock_pnl(h: int) -> int:
    return WIN - h


def scan_quotes(cfg: dict, trades: list[dict]) -> None:
    candles = cfg["root"] / "normalized" / cfg["norm"] / "candles_1m"
    opp_win: dict[str, tuple[int, int]] = {}
    held_from: dict[str, int] = {}
    by_opp: dict[str, list[int]] = defaultdict(list)
    for i, rec in enumerate(trades):
        rec["v3"] = {}
        if not rec.get("opponent_ticker"):
            continue
        ts0 = int(rec["first_80_timestamp"])
        end = rec.get("close_ts")
        ts1 = int(end) if end is not None else 2**31
        opp_win[rec["opponent_ticker"]] = (ts0, ts1)
        held_from[rec["ticker"]] = ts0
        by_opp[rec["opponent_ticker"]].append(i)

    needed = set(opp_win) | set(held_from)
    files = [p for p in candles.rglob("*.parquet") if p.stem in needed]
    print(f"  candle files {len(files)}", flush=True)
    held_at: dict[str, dict[int, int]] = defaultdict(dict)
    opp_quotes: dict[str, list[tuple]] = defaultdict(list)
    cols = [
        "end_period_ts",
        "yes_bid_high_e4",
        "yes_bid_low_e4",
        "yes_bid_close_e4",
        "yes_ask_close_e4",
        "volume_hundredths",
        "is_valid",
        "orderbook_depth_available",
    ]
    for n_file, path in enumerate(files, 1):
        if n_file % 500 == 0 or n_file == 1:
            print(f"  scan {n_file}/{len(files)}", flush=True)
        table = pq.read_table(path, columns=cols)
        get = {c: table.column(c) for c in cols}
        ticker = path.stem
        had_q = False
        win = opp_win.get(ticker)
        h0 = held_from.get(ticker)
        for i in range(table.num_rows):
            if not get["is_valid"][i].as_py():
                continue
            t = int(get["end_period_ts"][i].as_py())
            bid_c = A._opt_int(get["yes_bid_close_e4"][i].as_py())
            ask_c = A._opt_int(get["yes_ask_close_e4"][i].as_py())
            bid_h = A._opt_int(get["yes_bid_high_e4"][i].as_py())
            bid_l = A._opt_int(get["yes_bid_low_e4"][i].as_py())
            vol = A._opt_int(get["volume_hundredths"][i].as_py())
            depth_flag = get["orderbook_depth_available"][i].as_py()
            if h0 is not None and t >= h0 and bid_c is not None:
                held_at[ticker][t] = bid_c
            if win is None:
                continue
            ts0, ts1 = win
            if t <= ts0 or t > ts1:
                continue
            if not A.quality(bid_c, ask_c, vol, had_q):
                continue
            had_q = True
            opp_quotes[ticker].append((t, bid_c, bid_h, bid_l, ask_c, depth_flag))

    for opp, idxs in by_opp.items():
        quotes = opp_quotes.get(opp, [])
        quotes.sort(key=lambda x: x[0])
        close_i = first_idx(quotes, lambda q: q[1])
        wick_i = first_idx(quotes, lambda q: q[2])
        for i in idxs:
            rec = trades[i]
            held = held_at.get(rec["ticker"], {})
            rec["v3"] = build_trade_H(rec, quotes, close_i, wick_i, held)


def first_idx(quotes: list[tuple], getter) -> dict[int, int]:
    pending = set(H_ALL)
    found: dict[int, int] = {}
    for i, q in enumerate(quotes):
        px = getter(q)
        if px is None:
            continue
        hit = [h for h in list(pending) if px >= e4(h)]
        for h in hit:
            pending.remove(h)
            found[h] = i
    return found


def _cents(e: int | None) -> float | None:
    return None if e is None else e / 100.0


def _std_cents(vals: list[int]) -> float | None:
    if len(vals) < 2:
        return None
    m = sum(vals) / len(vals)
    return math.sqrt(sum((x - m) ** 2 for x in vals) / len(vals)) / 100.0


def build_trade_H(
    rec: dict,
    quotes: list[tuple],
    close_i: dict[int, int],
    wick_i: dict[int, int],
    held: dict[int, int],
) -> dict[int, dict]:
    out: dict[int, dict] = {}
    t_entry = int(rec["first_80_timestamp"])
    close_ts = rec.get("close_ts")
    fav40 = rec.get("first_40_close_ts")
    n = len(quotes)
    for h in H_ALL:
        ci = close_i.get(h)
        wi = wick_i.get(h)
        feat = features_at(quotes, ci if ci is not None else wi, h, n) if (ci is not None or wi is not None) else {}
        if ci is not None:
            feat = features_at(quotes, ci, h, n)
            t, bid_c, bid_h, bid_l, ask_c, depth_flag = quotes[ci]
            qclass, ttype = classify(True, wi is not None, feat)
        elif wi is not None:
            feat = features_at(quotes, wi, h, n)
            t, bid_c, bid_h, bid_l, ask_c, depth_flag = quotes[wi]
            qclass, ttype = classify(False, True, feat)
        else:
            out[h] = empty_H(h)
            continue
        held_bid = held.get(t)
        row = {
            "h": h,
            "opportunity_close": ci is not None,
            "opportunity_high": wi is not None,
            "first_touch_ts": t,
            "time_until_touch_s": t - t_entry,
            "time_resting_before_touch_s": t - t_entry,
            "touch_type": ttype,
            "opportunity_quality_class": qclass,
            "touch_candle_high_cents": _cents(bid_h),
            "touch_candle_low_cents": _cents(bid_l),
            "touch_candle_close_cents": _cents(bid_c),
            "touch_candle_range_cents": feat.get("touch_range_cents"),
            "overshoot_high_cents": feat.get("touch_overshoot_high_cents"),
            "overshoot_close_cents": feat.get("touch_overshoot_close_cents"),
            "close_above_H": feat.get("close_above_H"),
            "minutes_above_H": feat.get("minutes_above_H"),
            "consecutive_minutes_above_H": feat.get("persist_subsequent_min"),
            "persist_subsequent_min": feat.get("persist_subsequent_min"),
            "pre_touch_momentum": feat.get("path_velocity_in_cents"),
            "post_touch_momentum": feat.get("path_velocity_out_cents"),
            "pre_touch_volatility": feat.get("vol_pre_cents"),
            "post_touch_volatility": feat.get("vol_post_cents"),
            "spread_at_touch_cents": feat.get("market_spread_cents"),
            "reversal_flag": feat.get("reversal_flag"),
            "reversal_minutes": feat.get("reversal_minutes"),
            "jump_10c": feat.get("jump_10c"),
            "gradual": feat.get("gradual"),
            "persist_ratio_10": feat.get("persist_ratio_10"),
            "favorite_price_at_touch_cents": _cents(held_bid),
            "complement_sum_at_touch_cents": None
            if held_bid is None or bid_c is None
            else (held_bid + bid_c) / 100.0,
            "dt_fav40_minus_hedge_s": None if not fav40 else int(fav40) - t,
            "dt_hedge_to_close_s": None if close_ts is None else int(close_ts) - t,
            "depth_flag_raw": depth_flag,
            "historical_depth": "UNAVAILABLE",
            "queue_position": "UNKNOWN",
            "actual_fill_observed": False,
            "fill_probability_observed": "UNAVAILABLE",
            "fill_status": "NOT_ACTUAL_FILL",
            "label": "PRICE_OPPORTUNITY",
            "layer": "LAYER_2_FILLABLE_OPPORTUNITY" if ci is not None else "LAYER_1_WICK_ONLY",
        }
        for m in PERSIST_MARKS:
            row[f"persistence_{m}m"] = bool(feat.get(f"persistence_{m}m"))
        out[h] = {**feat, **row}
    return out


def empty_H(h: int) -> dict:
    return {
        "h": h,
        "opportunity_close": False,
        "opportunity_high": False,
        "opportunity_quality_class": None,
        "touch_type": None,
        "actual_fill_observed": False,
        "queue_position": "UNKNOWN",
        "historical_depth": "UNAVAILABLE",
        "fill_probability_observed": "UNAVAILABLE",
        "fill_status": "NOT_ACTUAL_FILL",
        "label": "NO_PRICE_OPPORTUNITY",
        "layer": "LAYER_1_NO_OPPORTUNITY",
    }


def features_at(quotes: list[tuple], idx: int, h: int, n: int) -> dict:
    t, bid_c, bid_h, bid_l, ask_c, _depth = quotes[idx]
    hx = e4(h)
    prev = quotes[idx - 1][1] if idx > 0 else None
    pre = [quotes[j][1] for j in range(max(0, idx - 5), idx) if quotes[j][1] is not None]
    post_c = [quotes[j][1] for j in range(idx + 1, min(n, idx + 11)) if quotes[j][1] is not None]
    jump = prev is not None and prev < hx - 1000 and (bid_c is not None and bid_c >= hx)
    gradual = len(pre) >= 3 and pre[-3] < pre[-2] < pre[-1] < hx and not jump
    vel_in = None
    if pre and bid_c is not None:
        dt = max(1, (t - quotes[max(0, idx - len(pre))][0]) / 60.0)
        vel_in = (bid_c - pre[0]) / 100.0 / dt * min(dt, 5)
        vel_in = (bid_c - pre[0]) / 100.0
    vel_out = None
    if post_c and bid_c is not None:
        vel_out = (post_c[min(4, len(post_c) - 1)] - bid_c) / 100.0
    rng = None
    if bid_h is not None and bid_l is not None:
        rng = (bid_h - bid_l) / 100.0
    spread = None
    if ask_c is not None and bid_c is not None:
        spread = (ask_c - bid_c) / 100.0
    persist = 0
    minutes_above = 1 if bid_c is not None and bid_c >= hx else 0
    last_above = t if minutes_above else None
    reversal_min = None
    for j in range(idx + 1, n):
        tj, cj = quotes[j][0], quotes[j][1]
        if cj is None:
            continue
        if cj >= hx:
            persist += 1
            minutes_above += 1
            last_above = tj
        else:
            if reversal_min is None:
                reversal_min = (tj - t) / 60.0
            if persist >= 0 and j > idx + 1:
                break
            if persist == 0:
                break
    window = quotes[idx : min(n, idx + 11)]
    avail = [q for q in window if q[1] is not None]
    above = [q for q in avail if q[1] >= hx]
    ratio = (len(above) / len(avail)) if avail else None
    persist_by_span = {}
    for m in PERSIST_MARKS:
        persist_by_span[f"persistence_{m}m"] = persist >= m
    residual = None
    return {
        "touch_overshoot_high_cents": None if bid_h is None else (bid_h - hx) / 100.0,
        "touch_overshoot_close_cents": None if bid_c is None else (bid_c - hx) / 100.0,
        "close_above_H": bool(bid_c is not None and bid_c >= hx),
        "touch_range_cents": rng,
        "path_velocity_in_cents": None if vel_in is None else round(vel_in, 4),
        "path_velocity_out_cents": None if vel_out is None else round(vel_out, 4),
        "vol_pre_cents": None if not pre else _std_cents(pre),
        "vol_post_cents": None if not post_c else _std_cents(post_c),
        "market_spread_cents": None if spread is None else round(spread, 4),
        "persist_subsequent_min": persist,
        "minutes_above_H": minutes_above,
        "persist_ratio_10": None if ratio is None else round(ratio, 4),
        "reversal_flag": reversal_min is not None and reversal_min <= 2,
        "reversal_minutes": 15.0 if reversal_min is None else round(reversal_min, 4),
        "jump_10c": bool(jump),
        "gradual": bool(gradual),
        "coupling_residual_cents": residual,
        **persist_by_span,
        "window_bars": len(avail),
        "last_above_span_min": None if last_above is None else (last_above - t) / 60.0,
    }


def classify(close_hit: bool, wick_hit: bool, feat: dict) -> tuple[str, str]:
    if not close_hit and wick_hit:
        return "D_WICK_ONLY", "ONE_MINUTE_WICK"
    persist = int(feat.get("persist_subsequent_min") or 0)
    close_above = bool(feat.get("close_above_H"))
    jump = bool(feat.get("jump_10c"))
    if jump:
        return "E_JUMP", "JUMP_THROUGH"
    if persist >= 5 and close_above:
        return "A_STRONG", "MULTI_MINUTE_ABOVE"
    if persist >= 3 and close_above:
        return "A_STRONG", "PERSISTENT_ABOVE"
    if persist >= 1 and close_above:
        tt = "GRADUAL_APPROACH" if feat.get("gradual") else "CONTINUATION"
        return "B_MODERATE", tt
    return "C_WEAK", "REVERSAL"


def reproduce_v2_h40(sport: str, trades: list[dict]) -> dict:
    gate = V2.V1_GATES[sport]
    n = len(trades)
    hedge = win = miss = 0
    pnls = []
    stops = []
    for rec in trades:
        row = rec.get("v3", {}).get(40, {})
        touched = bool(row.get("opportunity_close"))
        if touched:
            hedge += 1
        elif rec["expiration_result_yes"]:
            win += 1
        else:
            miss += 1
        pnls.append(V2.pnl_hedge(40, touched, rec["expiration_result_yes"]))
        stops.append(V2.stop_pnl(rec))
    ev = round(sum(pnls) / n, 4) if n else None
    stop_ev = round(sum(stops) / n, 4) if n else None
    ok = (
        n == gate["n"]
        and hedge == gate["hedge"]
        and win == gate["win"]
        and miss == gate["miss"]
        and ev == gate["ev"]
        and stop_ev == gate["stop_ev"]
    )
    return {
        "sport": sport,
        "ok": ok,
        "observed": {"n": n, "hedge": hedge, "win": win, "miss": miss, "ev": ev, "stop_ev": stop_ev},
        "expected": gate,
        "label": "CANDLE PRICE_OPPORTUNITY — NOT ACTUAL_FILL",
    }


def split_trades(trades: list[dict], split: str) -> list[dict]:
    if split == "FULL":
        return trades
    return [t for t in trades if t.get("dataset_split") == split]


def opportunity_rows(sport: str, trades: list[dict]) -> list[dict]:
    rows = []
    for rec in trades:
        won = bool(rec["expiration_result_yes"])
        for h in H_ALL:
            v = rec.get("v3", {}).get(h) or empty_H(h)
            fav = v.get("favorite_price_at_touch_cents")
            opp_c = v.get("touch_candle_close_cents")
            residual = None
            if fav is not None and opp_c is not None:
                residual = fav + opp_c - 100.0
            rows.append(
                {
                    "sport": sport,
                    "game_id": rec.get("event_id"),
                    "market_id": rec.get("ticker"),
                    "game_date": rec.get("game_date"),
                    "dataset_split": rec.get("dataset_split"),
                    "favorite_market": rec.get("ticker"),
                    "opponent_market": rec.get("opponent_ticker"),
                    "entry_time": rec.get("first_80_timestamp"),
                    "entry_price": ENTRY,
                    "H": h,
                    "eventual_favorite_settlement": "YES" if won else "NO",
                    "first80_favorite40": rec.get("stop_close_triggered"),
                    "opponent_hedge_touch": bool(v.get("opportunity_close") or v.get("opportunity_high")),
                    "score_differential": "UNAVAILABLE",
                    "possession_state": "UNAVAILABLE",
                    "actual_fill_observed": False,
                    "queue_position": "UNKNOWN",
                    "historical_depth": "UNAVAILABLE",
                    "fill_probability_observed": "UNAVAILABLE",
                    "fill_status": "NOT_ACTUAL_FILL",
                    "coupling_residual_cents": residual,
                    **{
                        k: v.get(k)
                        for k in (
                            "opportunity_close",
                            "opportunity_high",
                            "first_touch_ts",
                            "time_until_touch_s",
                            "time_resting_before_touch_s",
                            "touch_type",
                            "opportunity_quality_class",
                            "minutes_above_H",
                            "consecutive_minutes_above_H",
                            "persist_subsequent_min",
                            "overshoot_high_cents",
                            "overshoot_close_cents",
                            "close_above_H",
                            "touch_candle_high_cents",
                            "touch_candle_low_cents",
                            "touch_candle_close_cents",
                            "touch_candle_range_cents",
                            "pre_touch_momentum",
                            "post_touch_momentum",
                            "pre_touch_volatility",
                            "post_touch_volatility",
                            "spread_at_touch_cents",
                            "persist_ratio_10",
                            "reversal_flag",
                            "reversal_minutes",
                            "jump_10c",
                            "favorite_price_at_touch_cents",
                            "complement_sum_at_touch_cents",
                            "dt_fav40_minus_hedge_s",
                            "persistence_1m",
                            "persistence_2m",
                            "persistence_3m",
                            "persistence_5m",
                            "persistence_10m",
                            "layer",
                        )
                    },
                }
            )
    return rows


def surface_for(trades: list[dict], h: int) -> dict:
    n = len(trades)
    close = wick = wick_only = 0
    classes = defaultdict(int)
    types = defaultdict(int)
    persist = []
    overshoot = []
    rest = []
    false = prot = miss = 0
    persist_ge = {m: 0 for m in PERSIST_MARKS}
    for rec in trades:
        v = rec.get("v3", {}).get(h) or {}
        won = bool(rec["expiration_result_yes"])
        c = bool(v.get("opportunity_close"))
        w = bool(v.get("opportunity_high"))
        if c:
            close += 1
            if won:
                false += 1
            else:
                prot += 1
            if v.get("persist_subsequent_min") is not None:
                persist.append(float(v["persist_subsequent_min"]))
            if v.get("overshoot_high_cents") is not None:
                overshoot.append(float(v["overshoot_high_cents"]))
            if v.get("time_resting_before_touch_s") is not None:
                rest.append(v["time_resting_before_touch_s"] / 60.0)
            q = v.get("opportunity_quality_class")
            if q:
                classes[q] += 1
            if v.get("touch_type"):
                types[v["touch_type"]] += 1
            for m in PERSIST_MARKS:
                if v.get(f"persistence_{m}m"):
                    persist_ge[m] += 1
        elif w:
            wick_only += 1
            classes["D_WICK_ONLY"] += 1
            types["ONE_MINUTE_WICK"] += 1
        if w:
            wick += 1
        if not c and not won:
            miss += 1
    losses = sum(1 for r in trades if not r["expiration_result_yes"])
    return {
        "h": h,
        "n": n,
        "close_opportunities": close,
        "wick_opportunities": wick,
        "wick_only": wick_only,
        "p_close": V2.wilson(close, n),
        "p_wick": V2.wilson(wick, n),
        "p_wick_only": V2.wilson(wick_only, n),
        "classes": dict(classes),
        "touch_types": dict(types),
        "p_class": {k: V2.wilson(v, n) for k, v in classes.items()},
        "false_hedge_opportunities": false,
        "protected_losses": prot,
        "catastrophic_misses": miss,
        "p_false_hedge": V2.wilson(false, n),
        "recall_loss": V2.wilson(prot, losses) if losses else V2.wilson(0, 0),
        "persist_subsequent": V2.dist(persist),
        "overshoot_high": V2.dist(overshoot),
        "time_resting_before_touch_min": V2.dist(rest),
        "p_persist_ge": {
            str(m): None if close == 0 else round(persist_ge[m] / close, 4) for m in PERSIST_MARKS
        },
        "status": "PRICE_OPPORTUNITY",
        "fill_status": "NOT_ACTUAL_FILL",
    }


def path_components(trades: list[dict], h: int) -> dict:
    """Per-trade hold vs lock contribution for close opportunities."""
    hold = []
    deltas = []
    by_class: dict[str, list[float]] = defaultdict(list)
    class_n = defaultdict(int)
    for rec in trades:
        won = bool(rec["expiration_result_yes"])
        hp = hold_pnl(won)
        hold.append(hp)
        v = rec.get("v3", {}).get(h) or {}
        if v.get("opportunity_close"):
            d = lock_pnl(h) - hp
            deltas.append(d)
            q = v.get("opportunity_quality_class") or "UNKNOWN"
            by_class[q].append(d)
            class_n[q] += 1
        else:
            deltas.append(0.0)
    n = len(trades)
    mean_hold = sum(hold) / n if n else 0.0
    mean_delta = sum(deltas) / n if n else 0.0
    return {
        "n": n,
        "mean_hold": mean_hold,
        "mean_delta": mean_delta,
        "class_mean_delta": {k: (sum(v) / n if n else 0.0) for k, v in by_class.items()},
        "class_n": dict(class_n),
        "stop_ev": (sum(V2.stop_pnl(r) for r in trades) / n) if n else 0.0,
    }


def ev_at_p(comp: dict, p: float) -> float:
    return comp["mean_hold"] + p * comp["mean_delta"]


def ev_class_p(comp: dict, p_map: dict[str, float]) -> float:
    ev = comp["mean_hold"]
    for k, md in comp["class_mean_delta"].items():
        ev += p_map.get(k, 0.0) * md
    return ev


def solve_p(comp: dict, target: float) -> float | None:
    """Min universal p on close opportunities such that EV >= target. None if impossible."""
    if comp["n"] == 0:
        return None
    if ev_at_p(comp, 0) >= target - 1e-12:
        return 0.0
    if comp["mean_delta"] <= 1e-12:
        return None if ev_at_p(comp, 1) < target else 1.0
    p = (target - comp["mean_hold"]) / comp["mean_delta"]
    if p > 1 + 1e-9:
        return None
    return max(0.0, min(1.0, p))


def solve_p_on_classes(comp: dict, classes: tuple[str, ...], target: float) -> float | None:
    md = sum(comp["class_mean_delta"].get(c, 0.0) for c in classes)
    base = comp["mean_hold"]
    if base >= target - 1e-12:
        return 0.0
    if md <= 1e-12:
        return None if base + md < target else 1.0
    p = (target - base) / md
    if p > 1 + 1e-9:
        return None
    return max(0.0, min(1.0, p))


def frontier_tables(trades: list[dict], split: str) -> tuple[list[dict], list[dict]]:
    ev_rows = []
    tax_rows = []
    for h in H_ALL:
        surf = surface_for(trades, h)
        surf["split"] = split
        tax_rows.append(surf)
        comp = path_components(trades, h)
        p0 = solve_p(comp, 0.0)
        p_stop = solve_p(comp, comp["stop_ev"])
        for p in P_GRID:
            ev = ev_at_p(comp, p)
            ev_rows.append(
                {
                    "split": split,
                    "h": h,
                    "p_fill_assumed": p,
                    "p_fill_label": "SCENARIO_NOT_ESTIMATE",
                    "gross_ev_cents": round(ev, 4),
                    "hold_ev_cents": round(comp["mean_hold"], 4),
                    "stop_ev_cents": round(comp["stop_ev"], 4),
                    "ev_minus_hold": round(ev - comp["mean_hold"], 4),
                    "ev_minus_stop": round(ev - comp["stop_ev"], 4),
                    "reserved_cents": ENTRY + h,
                    "ev_per_reserved": round(ev / (ENTRY + h), 6),
                    "p_min_ev_positive": None if p0 is None else round(p0, 4),
                    "p_min_beat_8040": None if p_stop is None else round(p_stop, 4),
                    "fill_status": "NOT_ACTUAL_FILL",
                }
            )
    return ev_rows, tax_rows


def conditional_p(trades: list[dict]) -> list[dict]:
    rows = []
    groups = {
        "UNIVERSAL_CLOSE": ("A_STRONG", "B_MODERATE", "C_WEAK", "E_JUMP"),
        "A_STRONG_ONLY": ("A_STRONG",),
        "B_MODERATE_ONLY": ("B_MODERATE",),
        "C_WEAK_ONLY": ("C_WEAK",),
        "E_JUMP_ONLY": ("E_JUMP",),
        "A_PLUS_B": ("A_STRONG", "B_MODERATE"),
        "A_B_E": ("A_STRONG", "B_MODERATE", "E_JUMP"),
    }
    for h in H_ALL:
        comp = path_components(trades, h)
        for name, classes in groups.items():
            rows.append(
                {
                    "h": h,
                    "scenario": name,
                    "classes": list(classes),
                    "p_min_ev_positive": _r(solve_p_on_classes(comp, classes, 0.0)),
                    "p_min_beat_8040": _r(solve_p_on_classes(comp, classes, comp["stop_ev"])),
                    "class_n": {c: comp["class_n"].get(c, 0) for c in classes},
                    "mean_hold": round(comp["mean_hold"], 4),
                    "stop_ev": round(comp["stop_ev"], 4),
                    "label": "SCENARIO_NOT_ESTIMATE",
                }
            )
    return rows


def _r(x):
    return None if x is None else round(x, 4)


def feature_matrix(rows: list[dict], feats: list[str]) -> tuple[np.ndarray, list[int]]:
    keep = []
    mat = []
    for i, r in enumerate(rows):
        vec = [r.get(k) for k in feats]
        if any(v is None or (isinstance(v, float) and math.isnan(v)) for v in vec):
            continue
        keep.append(i)
        mat.append([float(v) for v in vec])
    if not mat:
        return np.zeros((0, len(feats))), []
    return np.asarray(mat, dtype=float), keep


def redundancy(train_rows: list[dict]) -> tuple[list[str], dict]:
    X, _ = feature_matrix(train_rows, CLUSTER_FEATURES)
    report = {
        "input_features": list(CLUSTER_FEATURES),
        "n_complete_train": int(X.shape[0]),
        "pearson": {},
        "spearman": {},
        "dropped": [],
        "kept": [],
        "rule": f"|pearson| > {CORR_DROP} drops the later feature",
    }
    if X.shape[0] < 10:
        report["kept"] = list(CLUSTER_FEATURES)
        return list(CLUSTER_FEATURES), report
    pear = np.corrcoef(X, rowvar=False)
    # Spearman via rank
    ranks = np.apply_along_axis(lambda col: col.argsort().argsort().astype(float), 0, X)
    spear = np.corrcoef(ranks, rowvar=False)
    for i, a in enumerate(CLUSTER_FEATURES):
        report["pearson"][a] = {CLUSTER_FEATURES[j]: None if math.isnan(pear[i, j]) else round(float(pear[i, j]), 4) for j in range(len(CLUSTER_FEATURES))}
        report["spearman"][a] = {CLUSTER_FEATURES[j]: None if math.isnan(spear[i, j]) else round(float(spear[i, j]), 4) for j in range(len(CLUSTER_FEATURES))}
    kept = []
    for i, a in enumerate(CLUSTER_FEATURES):
        drop = False
        for b in kept:
            j = CLUSTER_FEATURES.index(b)
            r = pear[i, j]
            if not math.isnan(r) and abs(r) > CORR_DROP:
                drop = True
                report["dropped"].append({"feature": a, "redundant_with": b, "pearson": round(float(r), 4)})
                break
        if not drop:
            kept.append(a)
    report["kept"] = kept
    return kept, report


def cluster_split_rows(rows: list[dict], h: int, split: str) -> list[dict]:
    out = []
    for r in rows:
        if r["H"] != h:
            continue
        if split != "FULL" and r.get("dataset_split") != split:
            continue
        if not r.get("opportunity_close"):
            continue
        out.append(r)
    return out


def _impute(rows: list[dict], feats: list[str], med: dict[str, float]) -> list[dict]:
    out = []
    for r in rows:
        c = dict(r)
        for f in feats:
            if c.get(f) is None:
                c[f] = med[f]
        out.append(c)
    return out


def fit_clusters(train: list[dict], val: list[dict], oos: list[dict], kept: list[str]) -> dict:
    med = {}
    for f in kept:
        vals = [r.get(f) for r in train if r.get(f) is not None]
        med[f] = float(np.median(vals)) if vals else 0.0
    train = _impute(train, kept, med)
    val = _impute(val, kept, med)
    oos = _impute(oos, kept, med)

    def pack(rows):
        X, idx = feature_matrix(rows, kept)
        return X, idx

    Xtr, itr = pack(train)
    Xva, iva = pack(val)
    Xoo, ioo = pack(oos)
    if Xtr.shape[0] < 40:
        return {"ok": False, "reason": "TRAIN complete-case n < 40", "method": None}
    scaler = StandardScaler()
    Ztr = scaler.fit_transform(Xtr)
    Zva = scaler.transform(Xva) if Xva.shape[0] else np.zeros((0, Ztr.shape[1]))
    Zoo = scaler.transform(Xoo) if Xoo.shape[0] else np.zeros((0, Ztr.shape[1]))

    candidates = []
    for k in CLUSTER_KS:
        km = KMeans(n_clusters=k, random_state=80, n_init=10)
        ytr = km.fit_predict(Ztr)
        sil_tr = float(silhouette_score(Ztr, ytr)) if len(set(ytr)) > 1 else -1
        db_tr = float(davies_bouldin_score(Ztr, ytr)) if len(set(ytr)) > 1 else None
        yva = km.predict(Zva) if Zva.shape[0] else np.array([])
        sil_va = float(silhouette_score(Zva, yva)) if Zva.shape[0] >= 10 and len(set(yva)) > 1 else None
        sizes_va = {int(c): int((yva == c).sum()) for c in range(k)} if Zva.shape[0] else {}
        ok_sizes = bool(sizes_va) and min(sizes_va.values()) >= MIN_VAL_CLUSTER_N
        candidates.append(
            {
                "method": "kmeans",
                "k": k,
                "silhouette_train": sil_tr,
                "silhouette_val": sil_va,
                "davies_bouldin_train": db_tr,
                "val_sizes": sizes_va,
                "eligible": ok_sizes and sil_va is not None,
                "model": km,
                "ytr": ytr,
            }
        )
        gmm = GaussianMixture(n_components=k, random_state=80)
        ytrg = gmm.fit_predict(Ztr)
        sil_trg = float(silhouette_score(Ztr, ytrg)) if len(set(ytrg)) > 1 else -1
        yvag = gmm.predict(Zva) if Zva.shape[0] else np.array([])
        sil_vag = float(silhouette_score(Zva, yvag)) if Zva.shape[0] >= 10 and len(set(yvag)) > 1 else None
        sizes_vag = {int(c): int((yvag == c).sum()) for c in range(k)} if Zva.shape[0] else {}
        candidates.append(
            {
                "method": "gmm",
                "k": k,
                "silhouette_train": sil_trg,
                "silhouette_val": sil_vag,
                "davies_bouldin_train": float(davies_bouldin_score(Ztr, ytrg)) if len(set(ytrg)) > 1 else None,
                "val_sizes": sizes_vag,
                "eligible": bool(sizes_vag) and min(sizes_vag.values()) >= MIN_VAL_CLUSTER_N and sil_vag is not None,
                "model": gmm,
                "ytr": ytrg,
            }
        )

    eligible = [c for c in candidates if c["eligible"]]
    if eligible:
        chosen = max(eligible, key=lambda c: (c["silhouette_val"], -c["k"]))
        selection = "MAX_VAL_SILHOUETTE"
    else:
        chosen = max(candidates, key=lambda c: (c["silhouette_train"], -c["k"]))
        selection = "FALLBACK_TRAIN_SILHOUETTE"

    model = chosen["model"]
    ytr = chosen["ytr"]
    yva = model.predict(Zva) if Zva.shape[0] else np.array([])
    yoo = model.predict(Zoo) if Zoo.shape[0] else np.array([])

    pca = PCA(n_components=2, random_state=80)
    pca.fit(Ztr)

    def attach(rows, idx, labels, split):
        assigned = []
        for local, lab in zip(idx, labels):
            r = dict(rows[local])
            r["cluster"] = int(lab)
            r["cluster_split"] = split
            assigned.append(r)
        return assigned

    assigned = attach(train, itr, ytr, "TRAIN") + attach(val, iva, yva, "VALIDATION") + attach(oos, ioo, yoo, "OOS")

    def cluster_obs(rows_lab: list[dict]) -> dict:
        by = defaultdict(list)
        for r in rows_lab:
            by[r["cluster"]].append(r)
        out = {}
        for c, rs in by.items():
            pers = [r["persist_subsequent_min"] for r in rs if r.get("persist_subsequent_min") is not None]
            ov = [r["overshoot_high_cents"] for r in rs if r.get("overshoot_high_cents") is not None]
            rev = [1.0 if r.get("reversal_flag") else 0.0 for r in rs]
            loss = [1.0 if r.get("eventual_favorite_settlement") == "NO" else 0.0 for r in rs]
            out[str(c)] = {
                "n": len(rs),
                "median_persist": V2.quantile(pers, 0.5) if pers else None,
                "median_overshoot": V2.quantile(ov, 0.5) if ov else None,
                "reversal_rate": round(sum(rev) / len(rev), 4) if rev else None,
                "loss_rate": round(sum(loss) / len(loss), 4) if loss else None,
            }
        return out

    obs = {
        "TRAIN": cluster_obs(assigned[: len(itr)]),
        "VALIDATION": cluster_obs(assigned[len(itr) : len(itr) + len(iva)]),
        "OOS": cluster_obs(assigned[len(itr) + len(iva) :]),
    }

    def persist_rank(d: dict) -> list[str]:
        items = [(k, v.get("median_persist"), v["n"]) for k, v in d.items()]
        items = [x for x in items if x[1] is not None]
        items.sort(key=lambda x: (x[1], x[0]))
        return [x[0] for x in items]

    ranks = {s: persist_rank(obs[s]) for s in ("TRAIN", "VALIDATION", "OOS")}
    stable = ranks["TRAIN"] == ranks["VALIDATION"] == ranks["OOS"] and bool(ranks["TRAIN"])

    umap_points = []
    try:
        import umap

        reducer = umap.UMAP(n_components=2, random_state=80, n_neighbors=15, min_dist=0.1)
        # Fit TRAIN only, transform others — freeze after VAL selection (coords are viz only).
        utr = reducer.fit_transform(Ztr)
        uva = reducer.transform(Zva) if Zva.shape[0] else np.zeros((0, 2))
        uoo = reducer.transform(Zoo) if Zoo.shape[0] else np.zeros((0, 2))
        umap_status = "TRAIN_FIT_THEN_TRANSFORM"
        coords = (
            list(zip(itr, ytr, utr, ["TRAIN"] * len(itr)))
            + list(zip(iva, yva, uva, ["VALIDATION"] * len(iva)))
            + list(zip(ioo, yoo, uoo, ["OOS"] * len(ioo)))
        )
        rng = np.random.default_rng(80)
        if len(coords) > UMAP_SAMPLE:
            pick = set(rng.choice(len(coords), size=UMAP_SAMPLE, replace=False))
            coords = [c for i, c in enumerate(coords) if i in pick]
        src = {"TRAIN": train, "VALIDATION": val, "OOS": oos}
        for idx, lab, xy, split in coords:
            r = src[split][idx]
            umap_points.append(
                {
                    "split": split,
                    "cluster": int(lab),
                    "x": float(xy[0]),
                    "y": float(xy[1]),
                    "persist": r.get("persist_subsequent_min"),
                    "overshoot": r.get("overshoot_high_cents"),
                    "class": r.get("opportunity_quality_class"),
                    "settlement": r.get("eventual_favorite_settlement"),
                }
            )
    except Exception as exc:
        umap_status = f"UNAVAILABLE: {type(exc).__name__}"

    hdb = {"status": "DIAGNOSTIC_ONLY"}
    try:
        import hdbscan

        cl = hdbscan.HDBSCAN(min_cluster_size=25, min_samples=10)
        yh = cl.fit_predict(Ztr)
        labels = [int(x) for x in yh if x >= 0]
        hdb = {
            "status": "DIAGNOSTIC_ONLY_NOT_SELECTED",
            "n_clusters": len(set(labels)),
            "noise": int((yh < 0).sum()),
            "silhouette_non_noise": None,
        }
        mask = yh >= 0
        if mask.sum() > 20 and len(set(yh[mask])) > 1:
            hdb["silhouette_non_noise"] = float(silhouette_score(Ztr[mask], yh[mask]))
    except Exception as exc:
        hdb = {"status": f"UNAVAILABLE: {type(exc).__name__}"}

    pca_var = [round(float(x), 4) for x in pca.explained_variance_ratio_]
    return {
        "ok": True,
        "selection_split": "VALIDATION",
        "selection_rule": selection,
        "method": chosen["method"],
        "k": chosen["k"],
        "features": kept,
        "silhouette_train": chosen["silhouette_train"],
        "silhouette_val": chosen["silhouette_val"],
        "davies_bouldin_train": chosen["davies_bouldin_train"],
        "candidates": [
            {k: v for k, v in c.items() if k not in ("model", "ytr")} for c in candidates
        ],
        "observable": obs,
        "persist_rank": ranks,
        "rank_stable_train_val_oos": stable,
        "pca_variance_2d": pca_var,
        "umap_status": umap_status,
        "umap_points": umap_points,
        "hdbscan": hdb,
        "target": "FILL_OPPORTUNITY_QUALITY_FEATURES — NOT ACTUAL_FILL",
        "assignments": assigned,
    }


def capital_scenarios(trades: list[dict], stop_ev: float) -> list[dict]:
    rows = []
    for h in H_FOCUS:
        comp = path_components(trades, h)
        for p in P_GRID:
            ev = ev_at_p(comp, p)
            reserved = ENTRY + h
            p_opp = sum(1 for r in trades if (r.get("v3", {}).get(h) or {}).get("opportunity_close")) / max(1, len(trades))
            cond = ENTRY + p * p_opp * h
            rows.append(
                {
                    "h": h,
                    "p_fill_assumed": p,
                    "architecture": "A_RESERVED_80_PLUS_H",
                    "reserved_cents": reserved,
                    "gross_ev_cents": round(ev, 4),
                    "ev_per_capital": round(ev / reserved, 6),
                    "vs_8040": round(ev - stop_ev, 4),
                    "portfolio_margin": "UNAVAILABLE",
                    "label": "SCENARIO_NOT_ESTIMATE",
                }
            )
            rows.append(
                {
                    "h": h,
                    "p_fill_assumed": p,
                    "architecture": "B_CONDITIONAL_HEDGE_FUNDING",
                    "reserved_cents": round(cond, 4),
                    "gross_ev_cents": round(ev, 4),
                    "ev_per_capital": None if cond == 0 else round(ev / cond, 6),
                    "vs_8040": round(ev - stop_ev, 4),
                    "portfolio_margin": "UNAVAILABLE",
                    "label": "RESEARCH_ONLY_LIVE_RISK_CANNOT",
                }
            )
        rows.append(
            {
                "h": None,
                "p_fill_assumed": None,
                "architecture": "C_PORTFOLIO_MARGIN",
                "reserved_cents": None,
                "gross_ev_cents": None,
                "ev_per_capital": None,
                "vs_8040": None,
                "portfolio_margin": "UNAVAILABLE",
                "label": "NO_VERIFIED_KALSHI_OFFSET",
            }
        )
    rows.append(
        {
            "h": None,
            "p_fill_assumed": None,
            "architecture": "STOP_80_40",
            "reserved_cents": ENTRY,
            "gross_ev_cents": round(stop_ev, 4),
            "ev_per_capital": round(stop_ev / ENTRY, 6),
            "vs_8040": 0.0,
            "portfolio_margin": "UNAVAILABLE",
            "label": "IDEAL_40_FILL_PROXY",
        }
    )
    return rows


def decide_verdict(nba: dict, ncaab: dict) -> tuple[str, str]:
    """A priori. ACTUAL_FILL remains UNOBSERVED in every letter."""

    def class_share(payload, letter):
        surf = next(s for s in payload["surface"]["FULL"] if s["h"] == 40)
        n = surf["close_opportunities"]
        return (surf["classes"].get(letter, 0) / n) if n else 0.0

    def persist_med(payload):
        surf = next(s for s in payload["surface"]["FULL"] if s["h"] == 40)
        d = surf.get("persist_subsequent") or {}
        return d.get("median")

    def pmin(payload, h):
        row = next(r for r in payload["conditional"] if r["h"] == h and r["scenario"] == "UNIVERSAL_CLOSE")
        return row["p_min_beat_8040"]

    shares_a = [class_share(nba, "A_STRONG"), class_share(ncaab, "A_STRONG")]
    shares_ab = [
        class_share(nba, "A_STRONG") + class_share(nba, "B_MODERATE"),
        class_share(ncaab, "A_STRONG") + class_share(ncaab, "B_MODERATE"),
    ]
    meds = [persist_med(nba), persist_med(ncaab)]
    pmins40 = [pmin(nba, 40), pmin(ncaab, 40)]
    pmins28 = [pmin(nba, 28), pmin(ncaab, 28)]
    pmins20 = [pmin(nba, 20), pmin(ncaab, 20)]

    cl_ok = []
    for p in (nba, ncaab):
        c = p.get("cluster") or {}
        obs = (c.get("observable") or {}).get("TRAIN") or {}
        pers = [v.get("median_persist") for v in obs.values() if v.get("median_persist") is not None]
        spread = (max(pers) - min(pers)) if len(pers) >= 2 else 0
        cl_ok.append(
            bool(c.get("ok"))
            and (c.get("silhouette_val") or -1) >= 0.2
            and spread >= 2
            and c.get("rank_stable_train_val_oos")
        )

    drift = False
    for payload in (nba, ncaab):
        for h in H_FOCUS:
            val = solve_p(
                path_components(split_trades(payload["trades"], "VALIDATION"), h),
                path_components(split_trades(payload["trades"], "VALIDATION"), h)["stop_ev"],
            )
            oos = solve_p(
                path_components(split_trades(payload["trades"], "OOS"), h),
                path_components(split_trades(payload["trades"], "OOS"), h)["stop_ev"],
            )
            if oos is None:
                drift = True
            elif val is not None and oos > val + 0.30:
                drift = True

    wickish = all((m is None or m <= 0) for m in meds) and all(s < 0.10 for s in shares_a)
    high_p = all(x is None or x > 0.90 for x in pmins40)
    practical = all(x is not None and x <= 0.70 for x in pmins40) and all(s >= 0.15 for s in shares_ab)
    structure = all(s >= 0.30 for s in shares_ab) and all(m is not None and m >= 1 for m in meds)

    if wickish or high_p:
        return (
            "C",
            "Most H=40 paths are wick/reversal or required fill rates to beat 80/40 exceed 90%.",
        )
    if all(cl_ok) and practical and structure and not drift:
        return (
            "A",
            "Stable TRAIN→VAL→OOS opportunity clusters with large persist/overshoot gaps and practical p_fill requirements. ACTUAL_FILL still UNOBSERVED.",
        )
    if drift and not structure:
        return (
            "D",
            "Required p_fill to beat 80/40 is unstable across splits; candles do not pin execution.",
        )
    if structure or practical:
        return (
            "B",
            "Historical close-path opportunity is material and a quantitative p_fill requirement exists, but actual maker fills are unobserved.",
        )
    return (
        "D",
        "Plausible fill scenarios change the hedge vs 80/40 ranking; candles cannot resolve Layer 3.",
    )


def run_sport(sport: str) -> dict:
    print(f"=== {sport} V3 ===", flush=True)
    cfg, trades, _games = V2.prepare_trades(sport)
    if len(trades) != V2.V1_GATES[sport]["n"]:
        return {"sport": sport, "stop": True, "reason": "FIRST-80 universe count mismatch", "n": len(trades)}
    scan_quotes(cfg, trades)
    repro = reproduce_v2_h40(sport, trades)
    print(f"  reproduce H=40 {repro['observed']} ok={repro['ok']}", flush=True)
    if not repro["ok"]:
        return {"sport": sport, "stop": True, "reproduction": repro}

    opp = opportunity_rows(sport, trades)
    for r in opp:
        if r.get("favorite_price_at_touch_cents") is not None and r.get("touch_candle_close_cents") is not None:
            r["coupling_residual_cents"] = (
                r["favorite_price_at_touch_cents"] + r["touch_candle_close_cents"] - 100.0
            )

    surface = {s: [surface_for(split_trades(trades, s), h) for h in H_ALL] for s in SPLIT_ORDER}
    ev_all = []
    tax_all = []
    for s in SPLIT_ORDER:
        ev_rows, tax_rows = frontier_tables(split_trades(trades, s), s)
        for r in ev_rows:
            r["sport"] = sport
        for r in tax_rows:
            r["sport"] = sport
        ev_all.extend(ev_rows)
        tax_all.extend(tax_rows)
    cond = conditional_p(trades)
    for r in cond:
        r["sport"] = sport

    feat_rows = []
    for r in opp:
        feat_rows.append(
            {
                **r,
                "touch_overshoot_high_cents": r.get("overshoot_high_cents"),
                "touch_overshoot_close_cents": r.get("overshoot_close_cents"),
                "touch_range_cents": r.get("touch_candle_range_cents"),
                "path_velocity_in_cents": r.get("pre_touch_momentum"),
                "path_velocity_out_cents": r.get("post_touch_momentum"),
                "vol_pre_cents": r.get("pre_touch_volatility"),
                "vol_post_cents": r.get("post_touch_volatility"),
                "market_spread_cents": r.get("spread_at_touch_cents"),
                "market_price": r.get("touch_candle_close_cents"),
                "path_reversal": r.get("reversal_flag"),
                "game_time_remaining_s": r.get("dt_hedge_to_close_s")
                if False
                else None,
                "execution_proxy_class": r.get("opportunity_quality_class"),
            }
        )
    # repair time remaining from original rows
    by_key = {(r["market_id"], r["H"], r["game_date"]): r for r in opp}
    for r in feat_rows:
        src = by_key.get((r["market_id"], r["H"], r["game_date"]), {})
        r["game_time_remaining_s"] = src.get("dt_hedge_to_close_s") if src else None
        r["dt_hedge_to_close_s"] = src.get("dt_hedge_to_close_s") if src else r.get("dt_hedge_to_close_s")

    train_c = cluster_split_rows(feat_rows, CLUSTER_H, "TRAIN")
    val_c = cluster_split_rows(feat_rows, CLUSTER_H, "VALIDATION")
    oos_c = cluster_split_rows(feat_rows, CLUSTER_H, "OOS")
    kept, redun = redundancy(train_c)
    cluster = fit_clusters(train_c, val_c, oos_c, kept)
    print(
        f"  cluster {cluster.get('method')} k={cluster.get('k')} val_sil={cluster.get('silhouette_val')} stable={cluster.get('rank_stable_train_val_oos')}",
        flush=True,
    )

    assign_map = {}
    for a in cluster.get("assignments") or []:
        assign_map[(a["market_id"], a["H"], a["dataset_split"])] = a["cluster"]
    for r in feat_rows:
        r["cluster_h40"] = assign_map.get((r["market_id"], r["H"], r["dataset_split"])) if r["H"] == CLUSTER_H else None

    stop_ev = V2.V1_GATES[sport]["stop_ev"]
    cap = capital_scenarios(trades, stop_ev)

    payload = {
        "sport": sport,
        "stop": False,
        "trades": trades,
        "reproduction": repro,
        "n": len(trades),
        "split_counts": {s: len(split_trades(trades, s)) for s in ("TRAIN", "VALIDATION", "OOS", "FULL")},
        "surface": surface,
        "ev_frontier": ev_all,
        "taxonomy": tax_all,
        "conditional": cond,
        "opportunity": opp,
        "feature_store": feat_rows,
        "redundancy": redun,
        "cluster": {k: v for k, v in cluster.items() if k != "assignments"},
        "cluster_assignments": cluster.get("assignments") or [],
        "capital": cap,
        "comparators": {"stop_full_ev": stop_ev, "hold_full_ev": path_components(trades, 40)["mean_hold"]},
    }
    return payload


def write_sport_artifacts(payload: dict) -> None:
    sport = payload["sport"]
    d = out_dir(sport)
    write_parquet(d / "opportunity_dataset.parquet", payload["opportunity"])
    write_parquet(d / "feature_store.parquet", payload["feature_store"])
    write_parquet(
        d / "opportunity_surface.parquet",
        [{k: v for k, v in r.items() if k != "p_class"} | _flat_wilson(r) for r in payload["taxonomy"]],
    )
    write_parquet(d / "fill_probability_frontier.parquet", payload["ev_frontier"])
    write_parquet(d / "path_taxonomy.parquet", _taxonomy_flat(payload["taxonomy"]))
    write_parquet(d / "cluster_assignments.parquet", payload["cluster_assignments"])
    write_parquet(d / "economic_frontier.parquet", payload["capital"])
    corr_rows = _corr_rows(payload["redundancy"])
    write_parquet(d / "correlation_matrix.parquet", corr_rows)
    (d / "cluster_diagnostics.json").write_text(
        json.dumps({k: v for k, v in payload["cluster"].items() if k != "umap_points"}, indent=2, default=str)
    )
    (d / "feature_redundancy_report.json").write_text(json.dumps(payload["redundancy"], indent=2))
    (d / "reproduction_checks.json").write_text(json.dumps(payload["reproduction"], indent=2))
    (d / "metadata.json").write_text(
        json.dumps(
            {
                "program": PROGRAM,
                "sport": sport,
                "live_execution_changed": False,
                "actual_fill": "UNOBSERVED",
                "queue_position": "UNOBSERVED",
                "historical_depth": "UNOBSERVED",
                "h_range": [H_MIN, H_MAX],
                "splits": "TRAIN game_date<=2025-12-31; VAL through 2026-03-15; OOS after",
                "cluster_h": CLUSTER_H,
                "cluster_target": "FILL_OPPORTUNITY_QUALITY features — not fills, not P&L",
                "p_fill": "SCENARIO grid, not an estimate",
                "portfolio_margin": "UNAVAILABLE",
            },
            indent=2,
        )
    )


def _flat_wilson(r: dict) -> dict:
    out = {}
    for k in ("p_close", "p_wick", "p_false_hedge", "recall_loss"):
        w = r.get(k) or {}
        out[f"{k}_rate"] = w.get("rate")
    return out


def _taxonomy_flat(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        base = {k: v for k, v in r.items() if k not in ("classes", "touch_types", "p_class", "p_close", "p_wick", "p_wick_only", "p_false_hedge", "recall_loss", "persist_subsequent", "overshoot_high", "time_resting_before_touch_min", "p_persist_ge")}
        base["classes_json"] = json.dumps(r.get("classes") or {})
        base["touch_types_json"] = json.dumps(r.get("touch_types") or {})
        base["p_close_rate"] = (r.get("p_close") or {}).get("rate")
        base["p_wick_rate"] = (r.get("p_wick") or {}).get("rate")
        base["median_persist"] = (r.get("persist_subsequent") or {}).get("median")
        base["median_overshoot"] = (r.get("overshoot_high") or {}).get("median")
        base["median_rest_min"] = (r.get("time_resting_before_touch_min") or {}).get("median")
        out.append(base)
    return out


def _corr_rows(redun: dict) -> list[dict]:
    rows = []
    pear = redun.get("pearson") or {}
    spear = redun.get("spearman") or {}
    for a, d in pear.items():
        for b, v in d.items():
            rows.append(
                {
                    "feature_a": a,
                    "feature_b": b,
                    "pearson": v,
                    "spearman": (spear.get(a) or {}).get(b),
                }
            )
    return rows


def dash_payload(nba: dict, ncaab: dict, verdict: tuple[str, str]) -> dict:
    def slim_surf(payload):
        out = {}
        for split, rows in payload["surface"].items():
            out[split] = [
                {
                    "h": r["h"],
                    "n": r["n"],
                    "close": r["close_opportunities"],
                    "wick": r["wick_opportunities"],
                    "wick_only": r["wick_only"],
                    "classes": r["classes"],
                    "p_close": (r["p_close"] or {}).get("rate"),
                    "p_wick": (r["p_wick"] or {}).get("rate"),
                    "median_persist": (r["persist_subsequent"] or {}).get("median"),
                    "median_overshoot": (r["overshoot_high"] or {}).get("median"),
                    "median_rest_min": (r["time_resting_before_touch_min"] or {}).get("median"),
                    "p_persist_ge": r["p_persist_ge"],
                    "false": r["false_hedge_opportunities"],
                    "protected": r["protected_losses"],
                    "miss": r["catastrophic_misses"],
                    "recall": (r["recall_loss"] or {}).get("rate"),
                }
                for r in rows
            ]
        return out

    def slim_ev(payload):
        # FULL only for interactive surface; plus p_min per H
        rows = [r for r in payload["ev_frontier"] if r["split"] == "FULL"]
        pmins = {}
        for r in rows:
            if r["p_fill_assumed"] == 0.0:
                pmins[r["h"]] = {
                    "p_min_ev_positive": r["p_min_ev_positive"],
                    "p_min_beat_8040": r["p_min_beat_8040"],
                    "hold": r["hold_ev_cents"],
                    "stop": r["stop_ev_cents"],
                }
        return {
            "grid": [
                {
                    "h": r["h"],
                    "p": r["p_fill_assumed"],
                    "ev": r["gross_ev_cents"],
                    "vs_stop": r["ev_minus_stop"],
                    "ev_cap": r["ev_per_reserved"],
                }
                for r in rows
            ],
            "pmin": pmins,
        }

    def pmin_focus(payload):
        out = []
        for r in payload["conditional"]:
            if r["h"] in H_FOCUS:
                out.append(
                    {
                        "h": r["h"],
                        "scenario": r["scenario"],
                        "p_min_pos": r["p_min_ev_positive"],
                        "p_min_8040": r["p_min_beat_8040"],
                        "class_n": r["class_n"],
                    }
                )
        return out

    return {
        "banner": "CANDLE PRICE OPPORTUNITY MODEL  ·  NOT ACTUAL MAKER FILL DATA  ·  LIVE EXECUTION CHANGED: FALSE",
        "verdict": list(verdict),
        "layers": [
            {"id": 1, "name": "PRICE OPPORTUNITY", "status": "OBSERVABLE from 1m candles"},
            {"id": 2, "name": "FILLABLE OPPORTUNITY", "status": "PARTIAL — path quality only"},
            {"id": 3, "name": "ACTUAL FILL", "status": "UNOBSERVED HISTORICALLY"},
            {"id": 4, "name": "ECONOMIC OUTCOME", "status": "SCENARIO in p_fill — not realized"},
        ],
        "reproduction": {"nba": nba["reproduction"], "ncaab": ncaab["reproduction"]},
        "split_counts": {"nba": nba["split_counts"], "ncaab": ncaab["split_counts"]},
        "surface": {"nba": slim_surf(nba), "ncaab": slim_surf(ncaab)},
        "frontier": {"nba": slim_ev(nba), "ncaab": slim_ev(ncaab)},
        "required_fill": {"nba": pmin_focus(nba), "ncaab": pmin_focus(ncaab)},
        "cluster": {
            "nba": {k: nba["cluster"].get(k) for k in ("ok", "method", "k", "silhouette_train", "silhouette_val", "rank_stable_train_val_oos", "observable", "persist_rank", "umap_status", "hdbscan", "selection_rule", "features")},
            "ncaab": {k: ncaab["cluster"].get(k) for k in ("ok", "method", "k", "silhouette_train", "silhouette_val", "rank_stable_train_val_oos", "observable", "persist_rank", "umap_status", "hdbscan", "selection_rule", "features")},
        },
        "umap": {"nba": nba["cluster"].get("umap_points") or [], "ncaab": ncaab["cluster"].get("umap_points") or []},
        "capital": {
            "nba": [r for r in nba["capital"] if r["architecture"] in ("A_RESERVED_80_PLUS_H", "STOP_80_40", "C_PORTFOLIO_MARGIN")],
            "ncaab": [r for r in ncaab["capital"] if r["architecture"] in ("A_RESERVED_80_PLUS_H", "STOP_80_40", "C_PORTFOLIO_MARGIN")],
        },
        "v2_h_star": {"nba": 28, "ncaab": 20},
        "portfolio_margin": "UNAVAILABLE",
        "actual_fill_experiment": "NOT_RUN",
    }


def write_reports(nba: dict, ncaab: dict, verdict: tuple[str, str]) -> None:
    def surf(p, h, split="FULL"):
        return next(s for s in p["surface"][split] if s["h"] == h)

    def pmin(p, h, scen="UNIVERSAL_CLOSE"):
        return next(r for r in p["conditional"] if r["h"] == h and r["scenario"] == scen)

    lines = [
        "# FIRST80_OPPONENT_HEDGE_EXECUTION_MODEL_V3",
        "",
        "Research only. **LIVE EXECUTION CHANGED: FALSE.**",
        "",
        "```text",
        "CANDLE PRICE OPPORTUNITY  ≠  ACTUAL MAKER FILL",
        "LAYER 3 ACTUAL FILL = UNOBSERVED HISTORICALLY",
        "QUEUE = UNOBSERVED    DEPTH = UNOBSERVED",
        "p_fill values are SCENARIOS, not estimates",
        "PORTFOLIO MARGIN = UNAVAILABLE",
        "```",
        "",
        f"**Verdict: {verdict[0]} — {verdict[1]}**",
        "",
        "Test 4. Does not modify V1, V2, liquidation v1, Game Path V1–V4, FIRST01, Risk, or live execution.",
        "Locked P&L remains `100 − 80 − H = 20 − H`.",
        "",
        "## Question 1 — Close-price opportunity frequency",
        "",
        f"- NBA H=40: {surf(nba,40)['close_opportunities']} / {surf(nba,40)['n']} = {(surf(nba,40)['p_close'] or {}).get('pct')}%",
        f"- NCAAB H=40: {surf(ncaab,40)['close_opportunities']} / {surf(ncaab,40)['n']} = {(surf(ncaab,40)['p_close'] or {}).get('pct')}%",
        f"- NBA H=28: {surf(nba,28)['close_opportunities']} / {surf(nba,28)['n']}",
        f"- NCAAB H=20: {surf(ncaab,20)['close_opportunities']} / {surf(ncaab,20)['n']}",
        "",
        "## Question 2 — Wick-only opportunity",
        "",
        f"- NBA H=40 wick-only: {surf(nba,40)['wick_only']}",
        f"- NCAAB H=40 wick-only: {surf(ncaab,40)['wick_only']}",
        "",
        "## Question 3 — Persistence after first close touch",
        "",
        f"- NBA H=40 subsequent minutes ≥ H: {surf(nba,40).get('persist_subsequent')}",
        f"- NCAAB H=40: {surf(ncaab,40).get('persist_subsequent')}",
        f"- NBA H=40 P(persist≥5m | close opp): {(surf(nba,40).get('p_persist_ge') or {}).get('5')}",
        f"- NCAAB H=40 P(persist≥5m | close opp): {(surf(ncaab,40).get('p_persist_ge') or {}).get('5')}",
        "",
        "## Question 4 — Path archetypes (deterministic classes at H=40 FULL)",
        "",
        f"- NBA classes: {surf(nba,40)['classes']}",
        f"- NCAAB classes: {surf(ncaab,40)['classes']}",
        "",
        "CLASS E (jump ≥10¢ through H) is a gap: 1m candles cannot prove a print at H.",
        "",
        "## Question 5 — Cluster stability (H=40 close opportunities, path features only)",
        "",
        f"- NBA: method={nba['cluster'].get('method')} k={nba['cluster'].get('k')} VAL silhouette={nba['cluster'].get('silhouette_val')} rank-stable={nba['cluster'].get('rank_stable_train_val_oos')}",
        f"- NCAAB: method={ncaab['cluster'].get('method')} k={ncaab['cluster'].get('k')} VAL silhouette={ncaab['cluster'].get('silhouette_val')} rank-stable={ncaab['cluster'].get('rank_stable_train_val_oos')}",
        "",
        f"NBA observable: {nba['cluster'].get('observable')}",
        f"NCAAB observable: {ncaab['cluster'].get('observable')}",
        "",
        "Clusters were selected on VALIDATION silhouette, then frozen. OOS labeled once. Target is not P&L.",
        "",
        "## Question 6 — Minimum assumed p_fill for EV > 0",
        "",
        "Hold-to-settlement EV is already positive, so universal p_min for EV>0 is **0** on both sports.",
        "That does not mean the hedge is free. It means missing the hedge still leaves the +20/−80 book.",
        "",
        "## Question 7 — Minimum assumed p_fill to beat frozen 80/40",
        "",
        f"- NBA H=40 universal: {pmin(nba,40)['p_min_beat_8040']}",
        f"- NCAAB H=40 universal: {pmin(ncaab,40)['p_min_beat_8040']}",
        f"- NBA H=28 (V2 H*): {pmin(nba,28)['p_min_beat_8040']}",
        f"- NCAAB H=20 (V2 H*): {pmin(ncaab,20)['p_min_beat_8040']}",
        "",
        "These are **scenario thresholds**, not estimated fill rates.",
        "",
        "## Question 8 — Does the V2 low-H plateau survive imperfect fills?",
        "",
        "Yes as a *shape*: lower H still has a smaller lock (`20−H`) and more close opportunities, so the p_fill needed to beat 80/40 is typically lower than at H=40. See tables. Capital reservation of 80+H still punishes high H.",
        "",
        "## Question 9 — What to prioritize in a live/paper fill test",
        "",
        "1. CLASS A (multi-minute close ≥ H) — strongest observed opportunity.",
        "2. Pre-rested maker bid (T_rest ≪ T_touch). Median rest time is in the surface.",
        "3. CLASS E jumps — measure whether price *traded* at H or gapped through.",
        "4. CLASS D wick-only — expect the weakest fill rate; do not pool with A.",
        "",
        "## Question 10 — Can historical candles answer actual fill?",
        "",
        "**NO.** Layer 3 is unobserved. Candles can state a fill-quality taxonomy and a required p_fill. They cannot estimate P(ActualMakerFill | ·).",
        "",
        "## Reproduction",
        "",
        f"- NBA: {nba['reproduction']}",
        f"- NCAAB: {ncaab['reproduction']}",
        "",
        "## Passive hedge vs reactive liquidation",
        "",
        "| Dimension | Passive hedge | Reactive 80/40 |",
        "|---|---|---|",
        "| Placement | After 80 fill, before H | After 40 trigger |",
        "| Side | Resting buy opponent YES | Sell/liquidate favorite YES |",
        "| Latency after trigger | Lower (already resting) | High |",
        "| Queue | High (unobserved) | Lower if taking |",
        "| Depth | High (unobserved) | High (unobserved) |",
        "| Gap risk | Jump through H may skip the bid | Collapse can skip 40 |",
        "| Historical fill | UNOBSERVED | UNOBSERVED |",
        "",
        "Neither is declared superior. They are different unobserved execution problems.",
        "",
        "## Required live/paper telemetry",
        "",
        "ORDER_ID, GAME_ID, MARKET_ID, H, T_ENTRY, T_ORDER_SUBMIT, T_ORDER_ACK,",
        "T_FIRST_PRICE_TOUCH_H, T_FIRST_POTENTIAL_MATCH, T_FIRST_FILL, T_LAST_FILL,",
        "ORDER_PRICE, INITIAL_QTY, FILLED_QTY, REMAINING_QTY, VWAP_FILL,",
        "CANCEL_TIME, CANCEL_REASON, BEST_BID/ASK at submit and touch, VISIBLE_DEPTH or DEPTH_UNAVAILABLE.",
        "",
        "Target: `P(ActualMakerFill | H, path, persist, overshoot, vol, time_resting)` plus P(partial), E(fill fraction), E(VWAP), time-to-fill.",
        "",
        "Status: **ACTUAL FILL EXPERIMENT NOT_RUN.**",
        "",
        "## Selection protocol (a priori)",
        "",
        "- Discover path clusters on TRAIN H=40 close opportunities.",
        "- Features: overshoot, persist, range, velocities, vols, spread, reversal, complement residual.",
        "- Drop |pearson|>0.92.",
        "- Choose kmeans/gmm k∈{3,4,5} by VALIDATION silhouette, min VAL cluster n=20.",
        "- Freeze. Label OOS once.",
        "- Do not choose a new production H.",
        "",
        "Code: `apps/ncaab-data/scripts/first80_opponent_hedge_execution_model_v3.py`",
        "Dashboard: `frontend/first80-hedge-execution-v3/`",
        "Tables: `docs/research/FIRST80_OPPONENT_HEDGE_EXECUTION_MODEL_V3_TABLES.md`",
        "",
        "LIVE EXECUTION CHANGED: FALSE",
        "",
    ]
    DOCS.write_text("\n".join(lines) + "\n")

    tlines = [
        "# FIRST80_OPPONENT_HEDGE_EXECUTION_MODEL_V3 — tables",
        "",
        "LIVE EXECUTION CHANGED: FALSE. `p_fill` is a scenario, not an estimate.",
        "",
        "## Reproduction H=40 close path",
        "",
        f"- NBA: {nba['reproduction']['observed']}",
        f"- NCAAB: {ncaab['reproduction']['observed']}",
        "",
        "## Opportunity surface (FULL close)",
        "",
        "| Sport | H | Close | Wick | Wick-only | A | B | C | E | Median persist | Median overshoot | P(persist≥5) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for sport, p in (("nba", nba), ("ncaab", ncaab)):
        for h in H_ALL:
            s = next(x for x in p["surface"]["FULL"] if x["h"] == h)
            cl = s["classes"]
            tlines.append(
                f"| {sport} | {h} | {s['close_opportunities']} | {s['wick_opportunities']} | "
                f"{s['wick_only']} | {cl.get('A_STRONG', 0)} | {cl.get('B_MODERATE', 0)} | "
                f"{cl.get('C_WEAK', 0)} | {cl.get('E_JUMP', 0)} | "
                f"{(s.get('persist_subsequent') or {}).get('median')} | "
                f"{(s.get('overshoot_high') or {}).get('median')} | "
                f"{(s.get('p_persist_ge') or {}).get('5')} |"
            )
    tlines.extend(
        [
            "",
            "## Universal p_fill frontier vs 80/40 (FULL)",
            "",
            "| Sport | H | Hold EV | 80/40 EV | EV(p=0.3) | EV(p=0.5) | EV(p=1) | p_min EV>0 | p_min beat 80/40 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for sport, p in (("nba", nba), ("ncaab", ncaab)):
        by = defaultdict(dict)
        for r in p["ev_frontier"]:
            if r["split"] != "FULL":
                continue
            by[r["h"]][r["p_fill_assumed"]] = r
        for h in H_ALL:
            g = by[h]
            tlines.append(
                f"| {sport} | {h} | {g[0.0]['hold_ev_cents']} | {g[0.0]['stop_ev_cents']} | "
                f"{g[0.3]['gross_ev_cents']} | {g[0.5]['gross_ev_cents']} | {g[1.0]['gross_ev_cents']} | "
                f"{g[0.0]['p_min_ev_positive']} | {g[0.0]['p_min_beat_8040']} |"
            )
    tlines.extend(
        [
            "",
            "## Conditional fill scenarios (FULL)",
            "",
            "| Sport | H | Scenario | p_min EV>0 | p_min beat 80/40 | class n |",
            "|---|---:|---|---:|---:|---|",
        ]
    )
    for sport, p in (("nba", nba), ("ncaab", ncaab)):
        for r in p["conditional"]:
            if r["h"] not in H_FOCUS:
                continue
            tlines.append(
                f"| {sport} | {r['h']} | {r['scenario']} | {r['p_min_ev_positive']} | "
                f"{r['p_min_beat_8040']} | {r['class_n']} |"
            )
    tlines.extend(
        [
            "",
            "## TRAIN / VAL / OOS p_min to beat 80/40 (universal close)",
            "",
            "| Sport | H | TRAIN | VAL | OOS |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for sport, p in (("nba", nba), ("ncaab", ncaab)):
        for h in H_FOCUS:
            cells = []
            for split in ("TRAIN", "VALIDATION", "OOS"):
                row = next(
                    r
                    for r in p["ev_frontier"]
                    if r["split"] == split and r["h"] == h and r["p_fill_assumed"] == 0.0
                )
                cells.append(str(row["p_min_beat_8040"]))
            tlines.append(f"| {sport} | {h} | {cells[0]} | {cells[1]} | {cells[2]} |")
    tlines.append("")
    tlines.append("LIVE EXECUTION CHANGED: FALSE")
    tlines.append("")
    DOCS_TABLES.write_text("\n".join(tlines) + "\n")
    for sport, payload in (("nba", nba), ("ncaab", ncaab)):
        (out_dir(sport) / "REPORT.md").write_text(DOCS.read_text())


def main() -> int:
    print(PROGRAM, "LIVE EXECUTION CHANGED: FALSE", flush=True)
    nba = run_sport("nba")
    if nba.get("stop"):
        print("STOP reproduction/universe failure NBA", json.dumps(nba, default=str)[:2000])
        return 2
    ncaab = run_sport("ncaab")
    if ncaab.get("stop"):
        print("STOP reproduction/universe failure NCAAB", json.dumps(ncaab, default=str)[:2000])
        return 2
    verdict = decide_verdict(nba, ncaab)
    print("VERDICT", verdict, flush=True)
    write_sport_artifacts(nba)
    write_sport_artifacts(ncaab)
    write_reports(nba, ncaab, verdict)
    dash = dash_payload(nba, ncaab, verdict)
    DASH_PUBLIC.mkdir(parents=True, exist_ok=True)
    (DASH_PUBLIC / "dashboard.json").write_text(json.dumps(dash))
    for sport in ("nba", "ncaab"):
        (out_dir(sport) / "dashboard.json").write_text(json.dumps(dash))
    print("wrote", DOCS)
    print("wrote", DOCS_TABLES)
    print("done", verdict[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())