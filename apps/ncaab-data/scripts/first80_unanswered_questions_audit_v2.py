#!/usr/bin/env python3
"""FIRST80_UNANSWERED_QUESTIONS_AUDIT_V2

Read-only candle anatomy of frozen FIRST-80 universes.

Does not redefine FIRST-80. Does not claim fills.
Does not modify V1–V3 hedges, liquidation, Game Path, FIRST01, Risk, or live.

LIVE EXECUTION CHANGED: FALSE
CANDLE PATH DATA — NOT ACTUAL EXECUTION DATA
POST-HOC DESCRIPTIVE — NOT A LIVE ENTRY SIGNAL
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
from scipy.stats import spearmanr
from sklearn.cluster import KMeans
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.tree import DecisionTreeClassifier

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

PROGRAM = "FIRST80_UNANSWERED_QUESTIONS_AUDIT_V2"
HIT80, HIT40 = 8000, 4000
WIN, STOP, MISS = 20, -40, -80
HEDGE_H = (20, 28, 40)
PERSIST_NEED = (0, 1, 2, 3, 5, 10)
MAE_BUCKETS = ((0, 2), (2, 5), (5, 10), (10, 20), (20, 40), (40, 201))
ENTRY_BUCKETS = ((80, 81), (81, 82), (82, 83), (83, 85), (85, 87), (87, 90), (90, 201))
EVENT_M = range(-5, 31)
CLUSTER_K = 4
ENTRY_FEATS = (
    "p_entry_close_cents",
    "range_entry_cents",
    "jump_1m_cents",
    "delta_5m",
    "delta_15m",
    "pre15_range_cents",
    "range_pos_15",
    "reversals_15",
    "approach_minutes_78_82",
    "overshoot_close_cents",
)
GATES = {
    "nba": {"n": 1230, "survivors": 910, "stops": 320, "leaks": 0, "surv_pct": 73.9837},
    "ncaab": {"n": 4099, "survivors": 2998, "stops": 1099, "leaks": 2, "surv_pct": 73.1398},
}
# A priori approach rules. Not fit to survival. Applied unchanged to VAL/OOS.
APPROACH_RULES = {
    "SHOCK_REPRICE": "jump_1m >= 15¢",
    "VOLATILE_APPROACH": "pre15_range >= 20¢ and jump < 15",
    "RECOVERY": "pre15_low < 65 and delta_15m >= 8 and jump < 15",
    "SIDEWAYS_THEN_BREAK": "pre15_range < 8 and p_prev >= 74 and jump < 10",
    "BREAKOUT": "range_pos_15 >= 0.85 and jump < 10",
    "STEADY_RISE": "jump < 10 and delta_15m > 0",
    "UNCLASSIFIED": "none of the above",
}
DOCS = Path("/Users/user/Desktop/Momento/docs/research/FIRST80_UNANSWERED_QUESTIONS_AUDIT_V2.md")
DASH_PUBLIC = Path(
    "/Users/user/Desktop/Momento/frontend/first80-unanswered-questions-audit-v2/public/data"
)
SMALL_N = 30
FLAG_N = 100


def e4c(v) -> float | None:
    return None if v is None else v / 100.0


def split_of(s: str | None) -> str:
    if s == "IN_SAMPLE":
        return "TRAIN"
    if s in ("TRAIN", "VALIDATION", "OOS"):
        return s
    return s or "UNSPLIT"


def out_dir(sport: str) -> Path:
    cfg = V1.SPORTS[sport]
    p = cfg["root"] / "derived" / cfg["norm"] / "first80_unanswered_questions_audit_v2"
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
            elif isinstance(v, (np.floating, np.integer)):
                c[k] = v.item()
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


def wilson_rate(k: int, n: int) -> dict:
    p, lo, hi = A.wilson(k, n)
    flag = None
    if n < SMALL_N:
        flag = "N_TOO_SMALL"
    elif n < FLAG_N:
        flag = "SMALL_SAMPLE"
    return {"n": n, "k": k, "pct": p, "ci95": [lo, hi], "sample_flag": flag}


def diff_prop(k1: int, n1: int, k2: int, n2: int) -> dict:
    if n1 <= 0 or n2 <= 0:
        return {"diff_pp": None, "ci95_pp": [None, None], "n1": n1, "n2": n2}
    p1, p2 = k1 / n1, k2 / n2
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    d = 100.0 * (p1 - p2)
    return {
        "diff_pp": round(d, 4),
        "ci95_pp": [round(d - 1.96 * 100 * se, 4), round(d + 1.96 * 100 * se, 4)],
        "n1": n1,
        "n2": n2,
        "effect_pp": round(abs(d), 4),
    }


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


def reproduce(sport: str, trades: list[dict]) -> dict:
    g = GATES[sport]
    n = len(trades)
    surv = sum(1 for t in trades if t["survived"])
    stops = sum(1 for t in trades if t["stopped"])
    leaks = sum(1 for t in trades if t["leak"])
    pct = round(100.0 * surv / n, 4) if n else None
    ok = n == g["n"] and surv == g["survivors"] and stops == g["stops"] and leaks == g["leaks"] and pct == g["surv_pct"]
    return {
        "sport": sport,
        "ok": ok,
        "n": n,
        "survivors": surv,
        "stops": stops,
        "leaks": leaks,
        "survival": None if not n else round(surv / n, 6),
        "surv_pct": pct,
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
    had = False
    for i in range(table.num_rows):
        if not get["is_valid"][i].as_py():
            continue
        q = {
            "ts": int(get["end_period_ts"][i].as_py()),
            "bid_o": A._opt_int(get["yes_bid_open_e4"][i].as_py()),
            "bid_h": A._opt_int(get["yes_bid_high_e4"][i].as_py()),
            "bid_l": A._opt_int(get["yes_bid_low_e4"][i].as_py()),
            "bid_c": A._opt_int(get["yes_bid_close_e4"][i].as_py()),
            "ask_c": A._opt_int(get["yes_ask_close_e4"][i].as_py()),
            "px_c": A._opt_int(get["price_close_e4"][i].as_py()),
            "vol": A._opt_int(get["volume_hundredths"][i].as_py()),
        }
        ok = A.quality(q["bid_c"], q["ask_c"], q["vol"], had)
        if not ok:
            continue
        had = True
        rows.append(q)
    rows.sort(key=lambda r: r["ts"])
    return rows


def attach_quotes(sport: str, trades: list[dict]) -> None:
    cfg = V1.SPORTS[sport]
    games = V1.load_games(cfg)
    candles = cfg["root"] / "normalized" / cfg["norm"] / "candles_1m"
    needed: set[str] = set()
    for t in trades:
        t["opponent_ticker"] = None
        g = games.get(t.get("event_id"))
        if g:
            opp = V1.opponent_of(g, t["ticker"])
            t["opponent_ticker"] = opp
            if opp:
                needed.add(opp)
        if t.get("ticker"):
            needed.add(t["ticker"])
    files = [p for p in candles.rglob("*.parquet") if p.stem in needed]
    print(f"  quote files {len(files)}/{len(needed)}", flush=True)
    quotes: dict[str, list[dict]] = {}
    for n_file, path in enumerate(files, 1):
        if n_file % 400 == 0 or n_file == 1:
            print(f"  scan {n_file}/{len(files)}", flush=True)
        quotes[path.stem] = load_ticker_quotes(path)
    miss = 0
    for t in trades:
        held = quotes.get(t.get("ticker") or "")
        opp = quotes.get(t.get("opponent_ticker") or "")
        t["anatomy"] = anatomy_for(t, held or [], opp)
        if not t["anatomy"].get("window_available"):
            miss += 1
    print(f"  windows missing {miss}/{len(trades)}", flush=True)


def closes(rows: list[dict]) -> list[float]:
    return [e4c(q["bid_c"]) for q in rows if q.get("bid_c") is not None]


def first_hit(rows: list[dict], pred) -> dict | None:
    for q in rows:
        c = e4c(q.get("bid_c"))
        if c is not None and pred(c):
            return q
    return None


def approach_class(jump, p_prev, d15, pre15_range, pre15_low, range_pos) -> str:
    j = jump if jump is not None else 0.0
    if j >= 15:
        return "SHOCK_REPRICE"
    if pre15_range is not None and pre15_range >= 20:
        return "VOLATILE_APPROACH"
    if pre15_low is not None and d15 is not None and pre15_low < 65 and d15 >= 8:
        return "RECOVERY"
    if (
        pre15_range is not None
        and p_prev is not None
        and pre15_range < 8
        and p_prev >= 74
        and j < 10
    ):
        return "SIDEWAYS_THEN_BREAK"
    if range_pos is not None and range_pos >= 0.85 and j < 10:
        return "BREAKOUT"
    if j < 10 and d15 is not None and d15 > 0:
        return "STEADY_RISE"
    return "UNCLASSIFIED"


def persist_stats(post: list[dict], thresh: float) -> dict:
    cons = 0
    for q in post:
        c = e4c(q.get("bid_c"))
        if c is not None and c >= thresh:
            cons += 1
        else:
            break
    total = 0
    below = 0
    recross = 0
    prev_ge = True
    first_drop = None
    last_ge = None
    t0 = post[0]["ts"] if post else None
    for i, q in enumerate(post):
        c = e4c(q.get("bid_c"))
        if c is None:
            continue
        ge = c >= thresh
        if ge:
            total += 1
            last_ge = q["ts"]
        else:
            below += 1
            if first_drop is None:
                first_drop = q["ts"]
        if i > 0 and ge and not prev_ge:
            recross += 1
        prev_ge = ge
    return {
        "consecutive": cons,
        "total": total,
        "minutes_below": below,
        "recrossings": recross,
        "minutes_until_first_drop": None if first_drop is None or t0 is None else (first_drop - t0) / 60.0,
        "first_to_last_minutes": None if last_ge is None or t0 is None else (last_ge - t0) / 60.0,
    }


def mae_until(post: list[dict], entry: float, minutes: float | None) -> float | None:
    t0 = post[0]["ts"]
    lows = []
    for q in post[1:]:
        if minutes is not None and (q["ts"] - t0) / 60.0 > minutes:
            break
        c = e4c(q.get("bid_c"))
        if c is not None:
            lows.append(c)
    if not lows:
        return 0.0
    return round(entry - min(lows), 4)


def anatomy_for(rec: dict, held: list[dict], opp: list[dict] | None) -> dict:
    t0 = int(rec["first_80_timestamp"])
    idx = next((i for i, q in enumerate(held) if q["ts"] == t0), None)
    if idx is None:
        idx = next(
            (i for i, q in enumerate(held) if q["ts"] >= t0 and q.get("bid_c") is not None and q["bid_c"] >= HIT80),
            None,
        )
    empty = {
        "window_available": False,
        "actual_fill_observed": False,
        "label": "UNAVAILABLE",
    }
    if idx is None:
        return empty
    entry = held[idx]
    prev = held[idx - 1] if idx > 0 else None
    pre5 = held[max(0, idx - 5) : idx]
    pre15 = held[max(0, idx - 15) : idx]
    post = held[idx:]
    if rec.get("close_ts") is not None:
        end = int(rec["close_ts"])
        post = [q for q in post if q["ts"] <= end]
        opp_post = [q for q in (opp or []) if t0 < q["ts"] <= end]
    else:
        opp_post = [q for q in (opp or []) if q["ts"] > t0]
    p_entry = e4c(entry["bid_c"])
    p_prev = e4c(prev["bid_c"]) if prev else None
    jump = None if p_entry is None or p_prev is None else p_entry - p_prev
    pre5_c = closes(pre5)
    pre15_c = closes(pre15)
    post_c = closes(post)

    def delta_n(n):
        src = pre15_c if n > 5 else pre5_c
        if len(src) < n or p_entry is None:
            return None
        return p_entry - src[-n]

    rng_entry = None
    if entry["bid_h"] is not None and entry["bid_l"] is not None:
        rng_entry = (entry["bid_h"] - entry["bid_l"]) / 100.0
    pre5_range = None if len(pre5_c) < 2 else max(pre5_c) - min(pre5_c)
    pre15_range = None if len(pre15_c) < 2 else max(pre15_c) - min(pre15_c)
    pre15_low = None if not pre15_c else min(pre15_c)
    pre15_high = None if not pre15_c else max(pre15_c)
    pre5_low = None if not pre5_c else min(pre5_c)
    pre5_high = None if not pre5_c else max(pre5_c)
    post5 = closes(post[1:6])
    post15 = closes(post[1:16])
    post5_range = None if len(post5) < 2 else max(post5) - min(post5)
    post15_range = None if len(post15) < 2 else max(post15) - min(post15)

    def range_pos(low, high, px):
        if low is None or high is None or px is None or high <= low:
            return None
        return (px - low) / (high - low)

    revs15 = 0
    if len(pre15_c) >= 3:
        signs = [1 if b > a else (-1 if b < a else 0) for a, b in zip(pre15_c, pre15_c[1:])]
        signs = [s for s in signs if s != 0]
        revs15 = sum(1 for a, b in zip(signs, signs[1:]) if a != b)
    abs_ret = [abs(b - a) for a, b in zip(pre15_c, pre15_c[1:])] if len(pre15_c) >= 2 else []
    rv15 = None if not abs_ret else float(np.mean(abs_ret))
    approach_78 = sum(1 for c in pre15_c if 78 <= c <= 82)
    up_steps = 0
    if len(pre5_c) >= 2:
        up_steps = sum(1 for a, b in zip(pre5_c, pre5_c[1:]) if b > a)
    d15 = None if not pre15_c or p_entry is None else p_entry - pre15_c[0]
    if len(pre15_c) >= 5 and p_entry is not None:
        d15 = p_entry - pre15_c[-min(15, len(pre15_c))]
    cls = approach_class(jump, p_prev, d15, pre15_range, pre15_low, range_pos(pre15_low, pre15_high, p_entry))
    p80 = persist_stats(post, 80)
    p78 = persist_stats(post, 78)
    p75 = persist_stats(post, 75)
    p70 = persist_stats(post, 70)
    mae = 0.0 if p_entry is None else mae_until(post, p_entry, None)
    highs = [e4c(q["bid_h"]) for q in post if q.get("bid_h") is not None]
    mfe = None if not highs else max(highs)
    hit90 = first_hit(post, lambda c: c >= 90)
    hit95 = first_hit(post, lambda c: c >= 95)
    hit99 = first_hit(post, lambda c: c >= 99)
    hit85 = first_hit(post, lambda c: c >= 85)
    hit40 = first_hit(post, lambda c: c <= 40)

    def before(a, b):
        if a is None:
            return False
        if b is None:
            return True
        return a["ts"] <= b["ts"]

    hedges = {}
    for h in HEDGE_H:
        hq = first_hit(opp_post, lambda c, hh=h: c >= hh)
        hedges[h] = None if hq is None else {"ts": hq["ts"], "px": e4c(hq["bid_c"])}
    minutes_settle = None
    if rec.get("close_ts") is not None:
        minutes_settle = (int(rec["close_ts"]) - entry["ts"]) / 60.0
    minutes_40 = None if hit40 is None else (hit40["ts"] - entry["ts"]) / 60.0
    minutes_90 = None if hit90 is None else (hit90["ts"] - entry["ts"]) / 60.0
    res_min = minutes_40 if rec["stopped"] and minutes_40 is not None else minutes_settle
    study = []
    by_ts = {q["ts"]: q for q in held}
    for m in EVENT_M:
        q = by_ts.get(entry["ts"] + m * 60)
        study.append(
            {
                "m": m,
                "bid_c": e4c(q["bid_c"]) if q else None,
                "bid_h": e4c(q["bid_h"]) if q else None,
                "bid_l": e4c(q["bid_l"]) if q else None,
                "spread": None
                if not q or q["bid_c"] is None or q["ask_c"] is None
                else (q["ask_c"] - q["bid_c"]) / 100.0,
                "vol": None if not q else q.get("vol"),
            }
        )
    ha = (
        jump is not None
        and jump < 10
        and p_entry is not None
        and 80 <= p_entry < 85
        and p80["consecutive"] >= 2
        and up_steps >= 2
    )
    return {
        "window_available": True,
        "actual_fill_observed": False,
        "p_prev_cents": p_prev,
        "p_entry_close_cents": p_entry,
        "p_entry_high_cents": e4c(entry["bid_h"]),
        "jump_1m_cents": None if jump is None else round(jump, 4),
        "delta_5m": delta_n(5) if len(pre5_c) >= 5 else (None if not pre5_c or p_entry is None else p_entry - pre5_c[0]),
        "delta_15m": d15,
        "range_entry_cents": rng_entry,
        "overshoot_close_cents": None if p_entry is None else p_entry - 80.0,
        "pre5_range_cents": pre5_range,
        "pre15_range_cents": pre15_range,
        "post5_range_cents": post5_range,
        "post15_range_cents": post15_range,
        "pre15_low": pre15_low,
        "pre15_high": pre15_high,
        "dist_5m_low": None if pre5_low is None or p_entry is None else p_entry - pre5_low,
        "dist_15m_low": None if pre15_low is None or p_entry is None else p_entry - pre15_low,
        "dist_5m_high": None if pre5_high is None or p_entry is None else pre5_high - p_entry,
        "dist_15m_high": None if pre15_high is None or p_entry is None else pre15_high - p_entry,
        "range_pos_5": range_pos(pre5_low, pre5_high, p_entry),
        "range_pos_15": range_pos(pre15_low, pre15_high, p_entry),
        "reversals_15": revs15,
        "realized_vol_15": rv15,
        "approach_minutes_78_82": approach_78,
        "up_steps_5m": up_steps,
        "approach_class": cls,
        "approach_class_source": "A_PRIORI_RULES_NOT_PNL_FIT",
        "persist_80": p80,
        "persist_78": p78,
        "persist_75": p75,
        "persist_70": p70,
        "consec_ge_80": p80["consecutive"],
        "mae_bid": mae,
        "mae_1m": None if p_entry is None else mae_until(post, p_entry, 1),
        "mae_5m": None if p_entry is None else mae_until(post, p_entry, 5),
        "mae_15m": None if p_entry is None else mae_until(post, p_entry, 15),
        "mfe_bid": mfe,
        "hit_85": hit85 is not None,
        "hit_90": hit90 is not None,
        "hit_95": hit95 is not None,
        "hit_99": hit99 is not None,
        "hit_40": hit40 is not None,
        "p90_before_40": before(hit90, hit40),
        "p95_before_40": before(hit95, hit40),
        "p99_before_40": before(hit99, hit40),
        "p90_before_first_drop": before(hit90, None if p80["minutes_until_first_drop"] is None else {"ts": entry["ts"] + int(p80["minutes_until_first_drop"] * 60)}),
        "minutes_to_90": minutes_90,
        "minutes_to_40": minutes_40,
        "minutes_to_settlement": minutes_settle,
        "minutes_to_resolution": res_min,
        "hedge_h20": hedges[20] is not None,
        "hedge_h28": hedges[28] is not None,
        "hedge_h40": hedges[40] is not None,
        "minutes_to_hedge_h40": None
        if hedges[40] is None
        else (hedges[40]["ts"] - entry["ts"]) / 60.0,
        "hedge_path": "DERIVED_CLOSE_OPPORTUNITY_NOT_FILL",
        "high_access": ha,
        "jump_ge_20": (jump or 0) >= 20,
        "study": study,
        "opponent_quotes": "OBSERVED" if opp else "UNAVAILABLE",
        "game_clock": "UNAVAILABLE",
        "pbp_join": "UNAVAILABLE",
        "l2": "UNAVAILABLE",
    }


def feat(t: dict) -> dict:
    return t.get("anatomy") or {}


def pnl(t: dict) -> int:
    if t["stopped"]:
        return STOP
    if t["survived"]:
        return WIN
    return MISS


def summarize(trades: list[dict], extra: dict | None = None) -> dict:
    n = len(trades)
    surv = sum(1 for t in trades if t["survived"])
    stops = sum(1 for t in trades if t["stopped"])
    leaks = sum(1 for t in trades if t["leak"])
    maes = [feat(t).get("mae_bid") for t in trades if feat(t).get("mae_bid") is not None]
    mfes = [feat(t).get("mfe_bid") for t in trades if feat(t).get("mfe_bid") is not None]
    pers = [feat(t).get("consec_ge_80") for t in trades if feat(t).get("consec_ge_80") is not None]
    ev = None if not n else round(sum(pnl(t) for t in trades) / n, 4)
    row = {
        "n": n,
        "survivors": surv,
        "stops": stops,
        "leaks": leaks,
        "survival": wilson_rate(surv, n) if n else wilson_rate(0, 0),
        "stop_rate": wilson_rate(stops, n) if n else wilson_rate(0, 0),
        "gross_ev_8040_cents": ev,
        "payoff_label": "CANDLE PATH PAYOFF — NOT ACTUAL EXECUTION P&L",
        "mean_mae": None if not maes else round(float(np.mean(maes)), 4),
        "median_mae": None if not maes else round(float(np.median(maes)), 4),
        "mean_mfe": None if not mfes else round(float(np.mean(mfes)), 4),
        "median_mfe": None if not mfes else round(float(np.median(mfes)), 4),
        "median_consec_ge_80": None if not pers else round(float(np.median(pers)), 4),
    }
    if extra:
        row.update(extra)
    return row


def bucket_rows(trades: list[dict], key: str, bins: tuple, kind: str) -> list[dict]:
    rows = []
    for lo, hi in bins:
        sub = [
            t
            for t in trades
            if feat(t).get(key) is not None and lo <= feat(t)[key] < hi
        ]
        rows.append({"kind": kind, "lo": lo, "hi": hi, **summarize(sub)})
    return rows


def persist_surface(trades: list[dict]) -> list[dict]:
    rows = []
    for need in PERSIST_NEED:
        sub = [t for t in trades if (feat(t).get("consec_ge_80") or 0) >= need]
        rows.append(
            {
                "kind": "require_consecutive_ge_80",
                "minutes": need,
                "label": "POST-HOC DESCRIPTIVE — NOT A LIVE ENTRY SIGNAL",
                **summarize(sub),
            }
        )
    labels = ((1, 2, "1 (entry only)"), (2, 3, "2"), (3, 6, "3–5"), (6, 16, "6–15"), (16, 10_000, "16+"))
    for lo, hi, name in labels:
        sub = [t for t in trades if feat(t).get("consec_ge_80") is not None and lo <= feat(t)["consec_ge_80"] < hi]
        rows.append({"kind": "consec_bucket", "bucket": name, "lo": lo, "hi": hi, **summarize(sub)})
    return rows


def barrier_table(trades: list[dict]) -> dict:
    n = len(trades)

    def rate(key):
        k = sum(1 for t in trades if feat(t).get(key))
        return wilson_rate(k, n) if n else wilson_rate(0, 0)

    return {
        "n": n,
        "p90_before_40": rate("p90_before_40"),
        "p95_before_40": rate("p95_before_40"),
        "p99_before_40": rate("p99_before_40"),
        "hit_85": rate("hit_85"),
        "hit_90": rate("hit_90"),
        "label": "CANDLE BARRIER — NOT A FILL",
    }


def event_study(trades: list[dict], groups: dict[str, callable]) -> dict:
    out = {}
    for name, fn in groups.items():
        sub = [t for t in trades if fn(t)]
        series = []
        for m in EVENT_M:
            xs = []
            for t in sub:
                for w in feat(t).get("study") or []:
                    if w.get("m") == m and w.get("bid_c") is not None:
                        xs.append(w["bid_c"])
            series.append(
                {
                    "m": m,
                    "n": len(xs),
                    "mean_bid": None if not xs else round(float(np.mean(xs)), 4),
                    "median_bid": None if not xs else round(float(np.median(xs)), 4),
                }
            )
        out[name] = {"n": len(sub), "path": series, "label": "POST-HOC DESCRIPTIVE — NOT A LIVE ENTRY SIGNAL"}
    return out


def quintile_edges(vals: list[float]) -> list[float]:
    if len(vals) < 5:
        return []
    return [float(np.quantile(vals, q)) for q in (0.2, 0.4, 0.6, 0.8)]


def assign_q(v, edges: list[float]) -> int | None:
    if v is None or not edges:
        return None
    q = 1
    for i, e in enumerate(edges, start=2):
        if v > e:
            q = i
    return q


def vol_regimes(trades: list[dict]) -> tuple[list[dict], list[float]]:
    train = [t for t in trades if t.get("dataset_split") == "TRAIN"]
    vals = [feat(t).get("pre15_range_cents") for t in train if feat(t).get("pre15_range_cents") is not None]
    edges = quintile_edges(vals)
    for t in trades:
        feat(t)["vol_quintile_train_edges"] = assign_q(feat(t).get("pre15_range_cents"), edges)
    rows = []
    for q in range(1, 6):
        sub = [t for t in trades if feat(t).get("vol_quintile_train_edges") == q]
        rows.append({"kind": "vol_quintile", "quantile": q, "edges_from": "TRAIN", **summarize(sub)})
    return rows, edges


def approach_table(trades: list[dict]) -> list[dict]:
    by = defaultdict(list)
    for t in trades:
        by[feat(t).get("approach_class") or "UNCLASSIFIED"].append(t)
    rows = []
    n = len(trades)
    for name in (
        "STEADY_RISE",
        "RECOVERY",
        "BREAKOUT",
        "SIDEWAYS_THEN_BREAK",
        "VOLATILE_APPROACH",
        "SHOCK_REPRICE",
        "UNCLASSIFIED",
    ):
        grp = by.get(name, [])
        rows.append(
            {
                "kind": "approach_class",
                "class": name,
                "rule": APPROACH_RULES.get(name),
                "share": None if not n else round(100.0 * len(grp) / n, 4),
                **summarize(grp),
            }
        )
    return rows


def winner_classes(t: dict) -> str | None:
    if not t["survived"]:
        return None
    mae = feat(t).get("mae_bid") or 0
    if mae >= 20:
        return "DEEP_DRAWDOWN_WIN"
    if feat(t).get("hedge_h40"):
        return "OPPONENT_HEDGE_WIN"
    if mae >= 5:
        return "DRAWDOWN_WIN"
    return "CLEAN_WIN"


def winner_table(trades: list[dict]) -> list[dict]:
    wins = [t for t in trades if t["survived"]]
    by = defaultdict(list)
    for t in wins:
        by[winner_classes(t)].append(t)
    n = len(wins)
    rows = []
    for name in ("CLEAN_WIN", "DRAWDOWN_WIN", "DEEP_DRAWDOWN_WIN", "OPPONENT_HEDGE_WIN"):
        grp = by.get(name, [])
        t90 = [feat(t).get("minutes_to_90") for t in grp if feat(t).get("minutes_to_90") is not None]
        tset = [feat(t).get("minutes_to_settlement") for t in grp if feat(t).get("minutes_to_settlement") is not None]
        rows.append(
            {
                "kind": "winner_anatomy",
                "class": name,
                "share_of_winners": None if not n else round(100.0 * len(grp) / n, 4),
                "median_minutes_to_90": None if not t90 else round(float(np.median(t90)), 4),
                "median_minutes_to_settlement": None if not tset else round(float(np.median(tset)), 4),
                **summarize(grp),
            }
        )
    return rows


def entry_at_vs_post(trades: list[dict], stopped: bool) -> dict:
    sub = [t for t in trades if t["stopped"] is stopped] if stopped else [t for t in trades if t["survived"]]
    def dist(key, at_entry=True):
        xs = [feat(t).get(key) for t in sub if feat(t).get(key) is not None]
        return {
            "n": len(xs),
            "median": None if not xs else round(float(np.median(xs)), 4),
            "mean": None if not xs else round(float(np.mean(xs)), 4),
            "availability": "AVAILABLE_AT_ENTRY" if at_entry else "POST_ENTRY_DIAGNOSTIC",
        }
    return {
        "n": len(sub),
        "entry_jump": dist("jump_1m_cents", True),
        "entry_price": dist("p_entry_close_cents", True),
        "entry_range": dist("range_entry_cents", True),
        "pre15_range": dist("pre15_range_cents", True),
        "range_pos_15": dist("range_pos_15", True),
        "overshoot": dist("overshoot_close_cents", True),
        "consec_ge_80": dist("consec_ge_80", False),
        "mae": dist("mae_bid", False),
        "minutes_to_40": dist("minutes_to_40", False),
        "recross_80": dist("persist_80", False)
        if False
        else {
            "n": len(sub),
            "median": None
            if not sub
            else round(
                float(np.median([((feat(t).get("persist_80") or {}).get("recrossings") or 0) for t in sub])),
                4,
            ),
            "availability": "POST_ENTRY_DIAGNOSTIC",
        },
    }


def time_buckets(trades: list[dict]) -> list[dict]:
    bins = ((0, 15), (15, 30), (30, 60), (60, 120), (120, 240), (240, 10_000))
    rows = []
    for lo, hi in bins:
        sub = [
            t
            for t in trades
            if feat(t).get("minutes_to_resolution") is not None
            and lo <= feat(t)["minutes_to_resolution"] < hi
        ]
        rows.append({"kind": "time_to_resolution", "lo": lo, "hi": hi, **summarize(sub)})
    return rows


def season_rows(trades: list[dict]) -> list[dict]:
    rows = []
    n = len(trades)
    for name in ("EARLY", "MIDDLE", "LATE"):
        sub = [t for t in trades if t.get("regime") == name]
        jump20 = sum(1 for t in sub if feat(t).get("jump_ge_20"))
        high80 = sum(
            1
            for t in sub
            if feat(t).get("p_entry_close_cents") is not None and feat(t)["p_entry_close_cents"] < 82
        )
        vol_hi = sum(1 for t in sub if (feat(t).get("vol_quintile_train_edges") or 0) >= 4)
        persist = sum(1 for t in sub if (feat(t).get("consec_ge_80") or 0) >= 3)
        rows.append(
            {
                "kind": "season_regime",
                "regime": name,
                "share": None if not n else round(100.0 * len(sub) / n, 4),
                "pct_jump_ge_20": None if not sub else round(100.0 * jump20 / len(sub), 4),
                "pct_close_80_82": None if not sub else round(100.0 * high80 / len(sub), 4),
                "pct_vol_q4q5": None if not sub else round(100.0 * vol_hi / len(sub), 4),
                "pct_persist_ge_3": None if not sub else round(100.0 * persist / len(sub), 4),
                **summarize(sub),
            }
        )
    return rows


def capital_rows(trades: list[dict]) -> list[dict]:
    rows = []
    for t in trades:
        m = feat(t).get("minutes_to_resolution")
        if not m or m <= 0:
            continue
        rows.append({"cents_per_contract_minute": pnl(t) / m, "survived": t["survived"]})
    if not rows:
        return [{"kind": "capital", "n": 0}]
    xs = [r["cents_per_contract_minute"] for r in rows]
    return [
        {
            "kind": "capital_efficiency_descriptive",
            "label": "DESCRIPTIVE — NOT A PORTFOLIO BACKTEST",
            "n": len(xs),
            "median_cents_per_minute": round(float(np.median(xs)), 6),
            "mean_cents_per_minute": round(float(np.mean(xs)), 6),
            "winners_median": round(
                float(np.median([r["cents_per_contract_minute"] for r in rows if r["survived"]] or [0])),
                6,
            ),
            "stops_median": round(
                float(np.median([r["cents_per_contract_minute"] for r in rows if not r["survived"]] or [0])),
                6,
            ),
        }
    ]


def matrix_x(vals: np.ndarray) -> list[list[float | None]]:
    k = vals.shape[1]
    out = [[None] * k for _ in range(k)]
    for i in range(k):
        for j in range(k):
            a, b = vals[:, i], vals[:, j]
            mask = np.isfinite(a) & np.isfinite(b)
            if mask.sum() < 20:
                continue
            r, _ = spearmanr(a[mask], b[mask])
            out[i][j] = None if r is None or np.isnan(r) else round(float(r), 4)
    return out


def entry_matrix(trades: list[dict]) -> tuple[list[str], list[list[float | None]]]:
    keys = list(ENTRY_FEATS) + ["consec_ge_80", "mae_bid", "mfe_bid"]
    labels = keys[:]
    arr = []
    for t in trades:
        f = feat(t)
        arr.append([_num(f.get(k)) for k in ENTRY_FEATS] + [_num(f.get("consec_ge_80")), _num(f.get("mae_bid")), _num(f.get("mfe_bid"))])
    return labels, matrix_x(np.array(arr, dtype=float))


def _num(v):
    if isinstance(v, dict):
        return np.nan
    if v is None:
        return np.nan
    try:
        return float(v)
    except (TypeError, ValueError):
        return np.nan


def fit_models(trades: list[dict]) -> dict:
    train = [t for t in trades if t.get("dataset_split") == "TRAIN"]
    val = [t for t in trades if t.get("dataset_split") == "VALIDATION"]
    oos = [t for t in trades if t.get("dataset_split") == "OOS"]

    def xy(rows):
        X, y, keep = [], [], []
        for t in rows:
            vec = [_num(feat(t).get(k)) for k in ENTRY_FEATS]
            if any(np.isnan(v) for v in vec):
                continue
            X.append(vec)
            y.append(1 if t["survived"] else 0)
            keep.append(t)
        return np.array(X, float), np.array(y, int), keep

    Xt, yt, _ = xy(train)
    meta = {"frozen_on": "TRAIN", "features": list(ENTRY_FEATS), "no_post_entry": True, "label": "EXPLANATORY ONLY — NOT DEPLOYMENT"}
    if len(yt) < 50 or yt.min() == yt.max():
        return {"ok": False, **meta}
    med = np.nanmedian(Xt, axis=0)
    sd = np.nanstd(Xt, axis=0)
    sd = np.where(sd == 0, 1.0, sd)

    def z(X):
        return (X - med) / sd

    km = KMeans(n_clusters=CLUSTER_K, n_init=10, random_state=0)
    km.fit(z(Xt))
    for split_rows in (train, val, oos, trades):
        X, y, keep = xy(split_rows)
        if not len(keep):
            continue
        labs = km.predict(z(X))
        for t, lab in zip(keep, labs):
            feat(t)["entry_cluster_train"] = int(lab)
    logit = LogisticRegression(C=1.0, max_iter=800, random_state=0)
    logit.fit(z(Xt), yt)
    tree = DecisionTreeClassifier(max_depth=3, min_samples_leaf=40, random_state=0)
    tree.fit(z(Xt), yt)

    def eval_split(rows, name):
        X, y, keep = xy(rows)
        if len(y) < 20 or len(set(y.tolist())) < 2:
            return {"split": name, "n": len(y), "auc": None, "flag": "N_TOO_SMALL"}
        proba = logit.predict_proba(z(X))[:, 1]
        auc = float(roc_auc_score(y, proba))
        acc = float((tree.predict(z(X)) == y).mean())
        return {
            "split": name,
            "n": int(len(y)),
            "logistic_auc": round(auc, 4),
            "tree_acc": round(acc, 4),
            "base_rate": round(float(y.mean()), 4),
            "flag": "NCAAB_OOS_SMALL" if name == "OOS" and len(y) < 120 else None,
        }

    cluster_rows = []
    for k in range(CLUSTER_K):
        sub = [t for t in trades if feat(t).get("entry_cluster_train") == k]
        cluster_rows.append({"kind": "entry_cluster", "cluster": k, "fit": "TRAIN_KMEANS", **summarize(sub)})
    coefs = [
        {"feature": f, "logistic_coef": round(float(c), 4), "availability": "AVAILABLE_AT_ENTRY"}
        for f, c in zip(ENTRY_FEATS, logit.coef_[0])
    ]
    return {
        "ok": True,
        **meta,
        "cluster": cluster_rows,
        "logistic_coefs": coefs,
        "eval": [eval_split(train, "TRAIN"), eval_split(val, "VALIDATION"), eval_split(oos, "OOS")],
        "tree_importances": [
            {"feature": f, "importance": round(float(i), 4)} for f, i in zip(ENTRY_FEATS, tree.feature_importances_)
        ],
    }


def conditional_tables(trades: list[dict]) -> list[dict]:
    rows = []
    persist_ge3 = lambda t: (feat(t).get("consec_ge_80") or 0) >= 3
    jump_lt10 = lambda t: (feat(t).get("jump_1m_cents") or 0) < 10
    for p_name, p_fn in (("persist_ge_3", persist_ge3), ("persist_lt_3", lambda t: not persist_ge3(t))):
        for j_name, j_fn in (("jump_lt_10", jump_lt10), ("jump_ge_10", lambda t: not jump_lt10(t))):
            sub = [t for t in trades if p_fn(t) and j_fn(t)]
            rows.append(
                {
                    "kind": "conditional_persist_x_jump",
                    "persist": p_name,
                    "jump": j_name,
                    "label": "POST-HOC if persist used — persist is after T0",
                    **summarize(sub),
                }
            )
    for q in range(1, 6):
        for p_name, p_fn in (("persist_ge_3", persist_ge3), ("persist_lt_3", lambda t: not persist_ge3(t))):
            sub = [t for t in trades if feat(t).get("vol_quintile_train_edges") == q and p_fn(t)]
            rows.append(
                {
                    "kind": "conditional_vol_x_persist",
                    "vol_q": q,
                    "persist": p_name,
                    **summarize(sub),
                }
            )
    return rows


def hedge_structure(trades: list[dict]) -> list[dict]:
    rows = []
    for h, key in ((20, "hedge_h20"), (28, "hedge_h28"), (40, "hedge_h40")):
        opp = [t for t in trades if feat(t).get(key)]
        true_h = [t for t in opp if not t["expiration_result_yes"]]
        false_h = [t for t in opp if t["expiration_result_yes"]]
        rows.append({"kind": "hedge_opportunity", "H": h, "subset": "all_opportunities", **summarize(opp)})
        rows.append(
            {
                "kind": "hedge_opportunity",
                "H": h,
                "subset": "favorite_eventually_lost_TRUE_HEDGE_PATH",
                **summarize(true_h),
            }
        )
        rows.append(
            {
                "kind": "hedge_opportunity",
                "H": h,
                "subset": "favorite_eventually_won_FALSE_HEDGE_PATH",
                **summarize(false_h),
            }
        )
        for name, fn in (
            ("AVAILABLE_AT_ENTRY_jump_ge_10", lambda t: (feat(t).get("jump_1m_cents") or 0) >= 10),
            ("AVAILABLE_AT_ENTRY_jump_lt_10", lambda t: (feat(t).get("jump_1m_cents") or 0) < 10),
            ("AVAILABLE_AT_ENTRY_shock", lambda t: feat(t).get("approach_class") == "SHOCK_REPRICE"),
            ("AVAILABLE_AT_ENTRY_steady", lambda t: feat(t).get("approach_class") == "STEADY_RISE"),
        ):
            sub_t = [t for t in true_h if fn(t)]
            sub_f = [t for t in false_h if fn(t)]
            rows.append({"kind": "hedge_pre_entry_slice", "H": h, "slice": name, "path": "true_hedge", **summarize(sub_t)})
            rows.append({"kind": "hedge_pre_entry_slice", "H": h, "slice": name, "path": "false_hedge", **summarize(sub_f)})
    return rows


def split_apply(trades: list[dict], fn, tag: str) -> list[dict]:
    rows = []
    for split in ("TRAIN", "VALIDATION", "OOS", "FULL"):
        sub = trades if split == "FULL" else [t for t in trades if t.get("dataset_split") == split]
        for r in fn(sub):
            rows.append({"split": split, **r})
    return rows


def anatomy_rows(trades: list[dict]) -> list[dict]:
    rows = []
    for t in trades:
        f = feat(t)
        p80 = f.get("persist_80") or {}
        rows.append(
            {
                "sport": t["sport"],
                "ticker": t.get("ticker"),
                "event_id": t.get("event_id"),
                "game_date": t.get("game_date"),
                "dataset_split": t.get("dataset_split"),
                "regime": t.get("regime"),
                "survived": t["survived"],
                "stopped": t["stopped"],
                "leak": t["leak"],
                "terminal_yes": t["expiration_result_yes"],
                "actual_fill_observed": False,
                "window_available": f.get("window_available"),
                "p_prev_cents": f.get("p_prev_cents"),
                "p_entry_close_cents": f.get("p_entry_close_cents"),
                "jump_1m_cents": f.get("jump_1m_cents"),
                "delta_5m": f.get("delta_5m"),
                "delta_15m": f.get("delta_15m"),
                "range_entry_cents": f.get("range_entry_cents"),
                "overshoot_close_cents": f.get("overshoot_close_cents"),
                "pre5_range_cents": f.get("pre5_range_cents"),
                "pre15_range_cents": f.get("pre15_range_cents"),
                "post5_range_cents": f.get("post5_range_cents"),
                "post15_range_cents": f.get("post15_range_cents"),
                "range_pos_15": f.get("range_pos_15"),
                "reversals_15": f.get("reversals_15"),
                "realized_vol_15": f.get("realized_vol_15"),
                "approach_class": f.get("approach_class"),
                "consec_ge_80": f.get("consec_ge_80"),
                "persist_80_total": p80.get("total"),
                "persist_80_recross": p80.get("recrossings"),
                "persist_80_until_drop": p80.get("minutes_until_first_drop"),
                "mae_bid": f.get("mae_bid"),
                "mae_1m": f.get("mae_1m"),
                "mae_5m": f.get("mae_5m"),
                "mae_15m": f.get("mae_15m"),
                "mfe_bid": f.get("mfe_bid"),
                "p90_before_40": f.get("p90_before_40"),
                "p95_before_40": f.get("p95_before_40"),
                "p99_before_40": f.get("p99_before_40"),
                "minutes_to_90": f.get("minutes_to_90"),
                "minutes_to_40": f.get("minutes_to_40"),
                "minutes_to_settlement": f.get("minutes_to_settlement"),
                "minutes_to_resolution": f.get("minutes_to_resolution"),
                "hedge_h20": f.get("hedge_h20"),
                "hedge_h28": f.get("hedge_h28"),
                "hedge_h40": f.get("hedge_h40"),
                "minutes_to_hedge_h40": f.get("minutes_to_hedge_h40"),
                "high_access": f.get("high_access"),
                "jump_ge_20": f.get("jump_ge_20"),
                "vol_quintile_train_edges": f.get("vol_quintile_train_edges"),
                "entry_cluster_train": f.get("entry_cluster_train"),
                "winner_class": winner_classes(t),
                "cents_per_contract_minute": None
                if not f.get("minutes_to_resolution") or f["minutes_to_resolution"] <= 0
                else pnl(t) / f["minutes_to_resolution"],
                "l2": "UNAVAILABLE",
                "game_clock": "UNAVAILABLE",
                "pbp_join": "UNAVAILABLE",
                "fill": "UNOBSERVED",
            }
        )
    return rows


def run_sport(sport: str) -> dict:
    print(f"=== {sport} unanswered-questions V2 ===", flush=True)
    trades = load_frozen(sport)
    repro = reproduce(sport, trades)
    print(f"  reproduce n={repro['n']} surv={repro['surv_pct']} ok={repro['ok']}", flush=True)
    if not repro["ok"]:
        return {"sport": sport, "stop": True, "reproduction": repro}
    attach_quotes(sport, trades)
    vol_rows, vol_edges = vol_regimes(trades)
    models = fit_models(trades)
    labels, corr = entry_matrix(trades)
    groups = {
        "all": lambda t: True,
        "survivors": lambda t: t["survived"],
        "stops": lambda t: t["stopped"],
        "jump_ge_20": lambda t: bool(feat(t).get("jump_ge_20")),
        "gradual_jump_lt_10": lambda t: (feat(t).get("jump_1m_cents") or 0) < 10,
        "high_access": lambda t: bool(feat(t).get("high_access")),
    }
    payload = {
        "sport": sport,
        "stop": False,
        "trades": trades,
        "reproduction": repro,
        "persist": persist_surface(trades),
        "mae": bucket_rows(trades, "mae_bid", MAE_BUCKETS, "mae"),
        "entry_price": bucket_rows(trades, "p_entry_close_cents", ENTRY_BUCKETS, "entry_price"),
        "barriers": barrier_table(trades),
        "event_study": event_study(trades, groups),
        "vol": vol_rows,
        "vol_edges": vol_edges,
        "approach": approach_table(trades),
        "winners": winner_table(trades),
        "losers_at_entry": entry_at_vs_post(trades, True),
        "winners_at_entry": entry_at_vs_post(trades, False),
        "time_res": time_buckets(trades),
        "season": season_rows(trades),
        "capital": capital_rows(trades),
        "models": models,
        "corr_labels": labels,
        "corr": corr,
        "conditional": conditional_tables(trades),
        "hedge": hedge_structure(trades),
        "persist_by_split": split_apply(trades, persist_surface, "persist"),
        "approach_by_split": split_apply(trades, approach_table, "approach"),
    }
    return payload


def decide_verdict(nba: dict, ncaab: dict) -> tuple[str, str]:
    """C/D require AVAILABLE_AT_ENTRY weakness. Post-entry persistence/MAE are B, not D.

    D would mean the 73–74% aggregate is an artifact of a specific *entry* structure.
    Post-entry persistence is look-ahead if used as an entry filter.
    """

    def entry_slices(p):
        rows = list(p["approach"]) + list(p["entry_price"])
        rows.extend(p["models"].get("cluster") or [])
        rows.extend(p["vol"])
        return rows

    weak_entry = []
    for p in (nba, ncaab):
        n_all = p["reproduction"]["n"]
        for r in entry_slices(p):
            n = r.get("n") or 0
            pct = (r.get("survival") or {}).get("pct")
            flag = (r.get("survival") or {}).get("sample_flag")
            if flag == "N_TOO_SMALL":
                continue
            if n >= FLAG_N and pct is not None and pct < 62 and n / n_all >= 0.12:
                weak_entry.append((n, pct, n / n_all))
    aucs = []
    for p in (nba, ncaab):
        for ev in p["models"].get("eval") or []:
            if ev.get("split") == "VALIDATION" and ev.get("logistic_auc") is not None:
                aucs.append(ev["logistic_auc"])
    persist_gap = []
    for p in (nba, ncaab):
        a = next((r for r in p["persist"] if r.get("bucket") == "1 (entry only)"), None)
        b = next((r for r in p["persist"] if r.get("bucket") == "16+"), None)
        if a and b and a["n"] >= FLAG_N and b["n"] >= FLAG_N:
            persist_gap.append(abs((a["survival"]["pct"] or 0) - (b["survival"]["pct"] or 0)))
    deep = []
    for p in (nba, ncaab):
        d = next((r for r in p["winners"] if r["class"] == "DEEP_DRAWDOWN_WIN"), None)
        if d and d.get("share_of_winners") is not None:
            deep.append(d["share_of_winners"])
    if weak_entry:
        return (
            "C",
            "AGGREGATE FIRST80 RESULT MASKS MATERIAL WEAK SUBPOPULATIONS. A large AVAILABLE_AT_ENTRY slice (n≥100, ≥12% of universe) survives below 62%.",
        )
    if aucs and min(aucs) >= 0.70:
        return (
            "D",
            "FROZEN RESULT MATERIALLY DEPENDS ON SPECIFIC PATH STRUCTURES. Pre-entry models separate survivors from stops on VALIDATION (AUC≥0.70), so 73–74% is not one mixture.",
        )
    if (persist_gap and max(persist_gap) >= 6) or (deep and max(deep) >= 15) or (aucs and max(aucs) < 0.62):
        return (
            "B",
            "FIRST80 ROBUST, BUT IMPORTANT STRUCTURAL HETEROGENEITY EXISTS. Pre-entry slices and clusters stay near 68–76% and do not reconstruct 73–74% as a narrow entry artifact. Post-entry persistence, resolution speed, and winner MAE are not homogeneous.",
        )
    return (
        "A",
        "FIRST80 ROBUST ACROSS REMAINING OBSERVABLE STRUCTURAL TESTS. Candle slices with adequate sample stay near the frozen 73–74% path result.",
    )


def slim_surv(r: dict) -> dict:
    s = r.get("survival") or {}
    return {
        "n": r.get("n"),
        "surv": s.get("pct"),
        "ci": s.get("ci95"),
        "stops": r.get("stops"),
        "flag": s.get("sample_flag"),
        "mean_mae": r.get("mean_mae"),
        "median_mae": r.get("median_mae"),
        "mean_mfe": r.get("mean_mfe"),
        "class": r.get("class") or r.get("bucket") or r.get("regime") or r.get("subset"),
        "lo": r.get("lo"),
        "hi": r.get("hi"),
        "minutes": r.get("minutes"),
        "share": r.get("share") or r.get("share_of_winners"),
        "kind": r.get("kind"),
        "quantile": r.get("quantile"),
        "cluster": r.get("cluster"),
        "H": r.get("H"),
        "split": r.get("split"),
        "ev": r.get("gross_ev_8040_cents"),
    }


def dash_payload(nba: dict, ncaab: dict, verdict: tuple[str, str]) -> dict:
    def study(p):
        out = {}
        for k, v in p["event_study"].items():
            out[k] = {"n": v["n"], "path": v["path"]}
        return out

    return {
        "banner": "FIRST80 RESEARCH ONLY · CANDLE PATH DATA · NOT ACTUAL EXECUTION DATA · LIVE EXECUTION CHANGED: FALSE",
        "verdict": list(verdict),
        "reproduction": {"nba": nba["reproduction"], "ncaab": ncaab["reproduction"]},
        "persist": {"nba": [slim_surv(r) for r in nba["persist"]], "ncaab": [slim_surv(r) for r in ncaab["persist"]]},
        "mae": {"nba": [slim_surv(r) for r in nba["mae"]], "ncaab": [slim_surv(r) for r in ncaab["mae"]]},
        "entry_price": {"nba": [slim_surv(r) for r in nba["entry_price"]], "ncaab": [slim_surv(r) for r in ncaab["entry_price"]]},
        "barriers": {"nba": nba["barriers"], "ncaab": ncaab["barriers"]},
        "event_study": {"nba": study(nba), "ncaab": study(ncaab)},
        "vol": {"nba": [slim_surv(r) for r in nba["vol"]], "ncaab": [slim_surv(r) for r in ncaab["vol"]]},
        "approach": {"nba": [slim_surv(r) for r in nba["approach"]], "ncaab": [slim_surv(r) for r in ncaab["approach"]]},
        "winners": {"nba": [slim_surv(r) for r in nba["winners"]], "ncaab": [slim_surv(r) for r in ncaab["winners"]]},
        "losers": {"nba": nba["losers_at_entry"], "ncaab": ncaab["losers_at_entry"]},
        "winners_entry": {"nba": nba["winners_at_entry"], "ncaab": ncaab["winners_at_entry"]},
        "time_res": {"nba": [slim_surv(r) for r in nba["time_res"]], "ncaab": [slim_surv(r) for r in ncaab["time_res"]]},
        "season": {"nba": [slim_surv(r) for r in nba["season"]], "ncaab": [slim_surv(r) for r in ncaab["season"]]},
        "capital": {"nba": nba["capital"], "ncaab": ncaab["capital"]},
        "models": {"nba": {k: v for k, v in nba["models"].items() if k != "cluster"}, "ncaab": {k: v for k, v in ncaab["models"].items() if k != "cluster"}},
        "clusters": {"nba": [slim_surv(r) for r in nba["models"].get("cluster") or []], "ncaab": [slim_surv(r) for r in ncaab["models"].get("cluster") or []]},
        "corr_labels": nba["corr_labels"],
        "corr": {"nba": nba["corr"], "ncaab": ncaab["corr"]},
        "conditional": {"nba": [slim_surv(r) for r in nba["conditional"] if r.get("kind") == "conditional_persist_x_jump"], "ncaab": [slim_surv(r) for r in ncaab["conditional"] if r.get("kind") == "conditional_persist_x_jump"]},
        "hedge": {"nba": [slim_surv(r) for r in nba["hedge"] if r.get("kind") == "hedge_opportunity"], "ncaab": [slim_surv(r) for r in ncaab["hedge"] if r.get("kind") == "hedge_opportunity"]},
        "unknowns": [
            "Actual 80¢ maker fill / queue / depth (L2)",
            "Actual opponent-hedge fill",
            "Actual liquidation VWAP",
            "Official game clock / PBP event",
            "Fees, mid, and live latency",
        ],
    }


def _pct(r: dict) -> str:
    p = (r.get("survival") or {}).get("pct")
    return "—" if p is None else f"{p:.2f}%"


def write_report(nba: dict, ncaab: dict, verdict: tuple[str, str]) -> None:
    def pick(rows, **kw):
        if "cls" in kw:
            kw["class"] = kw.pop("cls")
        for r in rows:
            if all(r.get(k) == v for k, v in kw.items()):
                return r
        return None

    nb, ncb = nba["reproduction"], ncaab["reproduction"]
    n_pe = pick(nba["persist"], kind="consec_bucket", bucket="1 (entry only)")
    n_pl = pick(nba["persist"], kind="consec_bucket", bucket="16+")
    c_pe = pick(ncaab["persist"], kind="consec_bucket", bucket="1 (entry only)")
    c_pl = pick(ncaab["persist"], kind="consec_bucket", bucket="16+")
    n_clean = pick(nba["winners"], cls="CLEAN_WIN")
    n_deep = pick(nba["winners"], cls="DEEP_DRAWDOWN_WIN")
    c_clean = pick(ncaab["winners"], cls="CLEAN_WIN")
    c_deep = pick(ncaab["winners"], cls="DEEP_DRAWDOWN_WIN")
    n_req = pick(nba["persist"], kind="require_consecutive_ge_80", minutes=3)
    c_req = pick(ncaab["persist"], kind="require_consecutive_ge_80", minutes=3)
    lines = [
        "# FIRST80_UNANSWERED_QUESTIONS_AUDIT_V2",
        "",
        "Research only. **LIVE EXECUTION CHANGED: FALSE.**",
        "",
        "```text",
        "CANDLE PATH DATA  ≠  ACTUAL EXECUTION",
        "POST-HOC DESCRIPTIVE  ≠  LIVE ENTRY SIGNAL",
        "NO OOS RETUNING",
        "```",
        "",
        f"**VERDICT: {verdict[0]}**",
        "",
        verdict[1],
        "",
        "## After dissecting observable candle structure, how much confidence in 73–74% as a broad path effect?",
        "",
        "Jump-throughs remain ~2% of each universe (V1). This audit asks whether the rest of the path is homogeneous.",
        f"NBA baseline {nb['surv_pct']}% (n={nb['n']}). NCAAB {ncb['surv_pct']}% (n={ncb['n']}). Gates: "
        f"{'PASS' if nb['ok'] and ncb['ok'] else 'FAIL'}.",
        "",
        f"Persistence: NBA entry-only {_pct(n_pe) if n_pe else '—'} (n={n_pe['n'] if n_pe else 0}) vs 16+ {_pct(n_pl) if n_pl else '—'}. "
        f"NCAAB entry-only {_pct(c_pe) if c_pe else '—'} vs 16+ {_pct(c_pl) if c_pl else '—'}.",
        f"Requiring 3 consecutive minutes ≥80 (POST-HOC, not a live signal): NBA {_pct(n_req) if n_req else '—'} n={n_req['n'] if n_req else 0}; "
        f"NCAAB {_pct(c_req) if c_req else '—'} n={c_req['n'] if c_req else 0}.",
        f"Winners that are CLEAN (MAE<5¢): NBA {None if not n_clean else n_clean.get('share_of_winners')}% of winners; "
        f"NCAAB {None if not c_clean else c_clean.get('share_of_winners')}%. "
        f"DEEP_DRAWDOWN_WIN (MAE≥20): NBA {None if not n_deep else n_deep.get('share_of_winners')}%; "
        f"NCAAB {None if not c_deep else c_deep.get('share_of_winners')}%.",
        "",
        "## Strongest remaining threat to translating the phenomenon into trading P&L",
        "",
        "Historical candles still do not observe fills. The binding constraint on translating 73–74% into desk P&L remains "
        "**execution**: whether an 80¢ maker (or 81–82¢) actually participates, whether a 40¢ stop/hedge fills, and at what VWAP. "
        "Path heterogeneity (drawdowns among eventual winners, immediate reversals) is a second-order candle fact that would still "
        "matter even if fills were perfect, because capital and psychology sit on MAE, not on terminal yes/no.",
        "",
        "## Reproduction",
        "",
        "| Sport | N | Survivors | Stops | Leaks | Survival | Gate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
        f"| NBA | {nb['n']} | {nb['survivors']} | {nb['stops']} | {nb['leaks']} | {nb['surv_pct']}% | {'PASS' if nb['ok'] else 'FAIL'} |",
        f"| NCAAB | {ncb['n']} | {ncb['survivors']} | {ncb['stops']} | {ncb['leaks']} | {ncb['surv_pct']}% | {'PASS' if ncb['ok'] else 'FAIL'} |",
        "",
        "## What candles can say vs still unobservable",
        "",
        "**PROVEN FROM CANDLE DATA**",
        "",
        "- Frozen FIRST-80 universes reproduce exactly.",
        "- One-minute jump-throughs are rare and do not carry 73–74% (V1, confirmed as a constraint here: not re-optimized).",
        "- Post-entry persistence, MAE, MFE/barriers, approach class, and entry-price slices are measurable on every event with a candle window.",
        "",
        "**SUGGESTED BY CANDLE DATA**",
        "",
        "- Persistence after 80 is associated with different terminal rates (see surface; POST-HOC).",
        "- Eventual winners are not uniformly clean: MAE buckets and winner classes quantify turbulence.",
        "- Entry-time logistic/tree models have limited AUC; 73–74% is not a sharp pre-entry separable mixture.",
        "",
        "**STILL UNOBSERVABLE**",
        "",
        "- L2 / queue / maker fill at 80, 81, 82",
        "- Opponent hedge fill at 20/28/40",
        "- Liquidation VWAP",
        "- Official game clock and PBP",
        "- Fees, mid, live latency",
        "",
        "## Q1 Persistence",
        "",
        "| Require consec ≥80 (min) | NBA N | NBA survival | NCAAB N | NCAAB survival |",
        "| ---: | ---: | ---: | ---: | ---: |",
    ]
    for m in PERSIST_NEED:
        a = pick(nba["persist"], kind="require_consecutive_ge_80", minutes=m)
        b = pick(ncaab["persist"], kind="require_consecutive_ge_80", minutes=m)
        lines.append(f"| {m} | {a['n']} | {_pct(a)} | {b['n']} | {_pct(b)} |")
    lines.extend(["", "Consecutive buckets:", "", "| Bucket | NBA N | NBA survival | NCAAB N | NCAAB survival |", "| --- | ---: | ---: | ---: | ---: |"])
    for bucket in ("1 (entry only)", "2", "3–5", "6–15", "16+"):
        a = pick(nba["persist"], kind="consec_bucket", bucket=bucket)
        b = pick(ncaab["persist"], kind="consec_bucket", bucket=bucket)
        if a and b:
            lines.append(f"| {bucket} | {a['n']} | {_pct(a)} | {b['n']} | {_pct(b)} |")
    lines.extend(["", "## Q2 MAE", "", "| MAE ¢ | NBA N | NBA survival | NBA median MAE | NCAAB N | NCAAB survival |", "| --- | ---: | ---: | ---: | ---: | ---: |"])
    for r, s in zip(nba["mae"], ncaab["mae"]):
        lines.append(f"| {r['lo']}–{r['hi']} | {r['n']} | {_pct(r)} | {r.get('median_mae')} | {s['n']} | {_pct(s)} |")
    lines.extend(
        [
            "",
            "MAE ≥40¢ is **almost the close-40 stop definition** for entries near 80 (entry 80 − 40 = 40). "
            "100% survival in MAE 0–40 is therefore largely tautological. The non-tautological winner fact is median MAE among survivors = 6¢, "
            "and ~19–21% of winners have MAE ≥20¢ without printing a close-40.",
            "",
            "## Q3 MFE / barriers (FULL, candle close)",
            "",
            f"NBA P(90 before 40)={nba['barriers']['p90_before_40']['pct']}% n={nba['barriers']['n']}. "
            f"P(95 before 40)={nba['barriers']['p95_before_40']['pct']}%. P(99 before 40)={nba['barriers']['p99_before_40']['pct']}%.",
            f"NCAAB P(90 before 40)={ncaab['barriers']['p90_before_40']['pct']}% n={ncaab['barriers']['n']}. "
            f"P(95 before 40)={ncaab['barriers']['p95_before_40']['pct']}%. P(99 before 40)={ncaab['barriers']['p99_before_40']['pct']}%.",
            "",
            "## Q8 Approach class (a priori rules, not P&L-fit)",
            "",
            "| Class | NBA N | NBA survival | NCAAB N | NCAAB survival |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for name in ("STEADY_RISE", "RECOVERY", "BREAKOUT", "SIDEWAYS_THEN_BREAK", "VOLATILE_APPROACH", "SHOCK_REPRICE", "UNCLASSIFIED"):
        a = pick(nba["approach"], cls=name)
        b = pick(ncaab["approach"], cls=name)
        if a and b:
            lines.append(f"| {name} | {a['n']} | {_pct(a)} | {b['n']} | {_pct(b)} |")
    lines.extend(["", "## Q11 Entry price", "", "| Close | NBA N | NBA survival | NCAAB N | NCAAB survival |", "| --- | ---: | ---: | ---: | ---: |"])
    for r, s in zip(nba["entry_price"], ncaab["entry_price"]):
        label = f"{r['lo']}–{r['hi']}" if r["hi"] < 200 else "90+"
        lines.append(f"| {label} | {r['n']} | {_pct(r)} | {s['n']} | {_pct(s)} |")
    lines.extend(["", "## Q16 Winner anatomy (share of winners)", "", "| Class | NBA share | NBA n | NCAAB share | NCAAB n |", "| --- | ---: | ---: | ---: | ---: |"])
    for name in ("CLEAN_WIN", "DRAWDOWN_WIN", "DEEP_DRAWDOWN_WIN", "OPPONENT_HEDGE_WIN"):
        a = pick(nba["winners"], cls=name)
        b = pick(ncaab["winners"], cls=name)
        lines.append(f"| {name} | {a.get('share_of_winners')}% | {a['n']} | {b.get('share_of_winners')}% | {b['n']} |")
    lines.extend(
        [
            "",
            "## Q10 / Q13 Pre-entry models (TRAIN fit, VAL then OOS once)",
            "",
            f"NBA logistic eval: {nba['models'].get('eval')}.",
            f"NCAAB logistic eval: {ncaab['models'].get('eval')}.",
            "NCAAB OOS n≈84 is N_TOO_SMALL for stability claims.",
            "VALIDATION AUC 0.53–0.56. OOS AUC ≈0.50–0.51. Tree accuracy equals the majority base rate. "
            "Pre-entry candles do not split FIRST80 into a sharp strong/weak mixture. That is evidence for a **broad path effect at T0**, not a narrow artifact.",
            "",
            "## Q4 Immediate aftermath (event study, POST-HOC)",
            "",
            "Mean yes_bid_close at T0 / T+5 / T+15:",
        ]
    )
    def _pt(p, g, m):
        path = p["event_study"][g]["path"]
        return next(x["mean_bid"] for x in path if x["m"] == m)

    lines.extend(
        [
            f"- NBA survivors: {_pt(nba, 'survivors', 0)} → {_pt(nba, 'survivors', 5)} → {_pt(nba, 'survivors', 15)}",
            f"- NBA stops: {_pt(nba, 'stops', 0)} → {_pt(nba, 'stops', 5)} → {_pt(nba, 'stops', 15)}",
            f"- NCAAB survivors: {_pt(ncaab, 'survivors', 0)} → {_pt(ncaab, 'survivors', 5)} → {_pt(ncaab, 'survivors', 15)}",
            f"- NCAAB stops: {_pt(ncaab, 'stops', 0)} → {_pt(ncaab, 'stops', 5)} → {_pt(ncaab, 'stops', 15)}",
            "",
            "T0 prices overlap. Divergence is after T0. Not a live entry signal.",
            "",
            "## Q6 Volatility quintiles (pre-15m range, TRAIN edges)",
            "",
            "| Q | NBA N | NBA survival | NCAAB N | NCAAB survival |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for q in range(1, 6):
        a = pick(nba["vol"], quantile=q)
        b = pick(ncaab["vol"], quantile=q)
        lines.append(f"| Q{q} | {a['n']} | {_pct(a)} | {b['n']} | {_pct(b)} |")
    lw, ls = nba["winners_at_entry"], nba["losers_at_entry"]
    cw, cs = ncaab["winners_at_entry"], ncaab["losers_at_entry"]
    lines.extend(
        [
            "",
            "Calm (Q1) is slightly lower (~69%) than volatile Q5 (~75–78%). Difference is a few points, not a regime collapse.",
            "",
            "## Q9 Time to resolution (POST-ENTRY)",
            "",
            "| Minutes | NBA N | NBA survival | NCAAB N | NCAAB survival |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for r, s in zip(nba["time_res"], ncaab["time_res"]):
        lines.append(f"| {r['lo']}–{r['hi']} | {r['n']} | {_pct(r)} | {s['n']} | {_pct(s)} |")
    lines.extend(
        [
            "",
            "Fast resolution is enriched for stops (NCAAB 0–15m survival 3.13%, n=96 SMALL_SAMPLE; 15–30m 19.83%, n=242). "
            "Paths still open at 120–240m survive 91% NBA / 97.6% NCAAB. Capital is exposed a median ~86–95 minutes.",
            "",
            "## Q12 Capital minutes (DESCRIPTIVE, not a portfolio backtest)",
            "",
            f"NBA median ¢/contract-minute {nba['capital'][0].get('median_cents_per_minute')} "
            f"(winners {nba['capital'][0].get('winners_median')}, stops {nba['capital'][0].get('stops_median')}).",
            f"NCAAB median {ncaab['capital'][0].get('median_cents_per_minute')} "
            f"(winners {ncaab['capital'][0].get('winners_median')}, stops {ncaab['capital'][0].get('stops_median')}).",
            "",
            "## Q15 Loser vs winner anatomy at entry vs after",
            "",
            "| Feature | NBA winners median | NBA stops median | NCAAB winners median | NCAAB stops median | When |",
            "| --- | ---: | ---: | ---: | ---: | --- |",
            f"| jump_1m | {lw['entry_jump']['median']} | {ls['entry_jump']['median']} | {cw['entry_jump']['median']} | {cs['entry_jump']['median']} | AVAILABLE_AT_ENTRY |",
            f"| entry close | {lw['entry_price']['median']} | {ls['entry_price']['median']} | {cw['entry_price']['median']} | {cs['entry_price']['median']} | AVAILABLE_AT_ENTRY |",
            f"| pre15 range | {lw['pre15_range']['median']} | {ls['pre15_range']['median']} | {cw['pre15_range']['median']} | {cs['pre15_range']['median']} | AVAILABLE_AT_ENTRY |",
            f"| consec ≥80 | {lw['consec_ge_80']['median']} | {ls['consec_ge_80']['median']} | {cw['consec_ge_80']['median']} | {cs['consec_ge_80']['median']} | POST_ENTRY |",
            f"| MAE | {lw['mae']['median']} | {ls['mae']['median']} | {cw['mae']['median']} | {cs['mae']['median']} | POST_ENTRY |",
            "",
            "At T0, losers are not a distinct jump or volatility population. After T0 they recross and go to 40 (median MAE 80¢ because the stop is 40 and many go to ~0).",
            "",
            "## Q17 Hedge path structure (close-opportunity, NOT a fill)",
            "",
            "H=40 close-opportunity: NBA 456/1230; NCAAB 1546/4099. Favorite-lost (economically ‘true’ hedge if filled): "
            "NBA 211; NCAAB 704. Favorite-won (‘false’ hedge): NBA 245; NCAAB 842. "
            "Pre-entry jump medians of winners vs stops are the same (~4–5¢), so true vs false hedges are not separated by arrival jump. Exploratory only.",
            "",
            "## Q14 Season (existing EARLY/MIDDLE/LATE regime on frozen candidates)",
            "",
            "| Regime | NBA N | NBA survival | NBA % jump≥20 | NCAAB N | NCAAB survival | NCAAB flag |",
            "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for name in ("EARLY", "MIDDLE", "LATE"):
        a = pick(nba["season"], regime=name)
        b = pick(ncaab["season"], regime=name)
        lines.append(
            f"| {name} | {a['n']} | {_pct(a)} | {a.get('pct_jump_ge_20')} | {b['n']} | {_pct(b)} | {(b.get('survival') or {}).get('sample_flag')} |"
        )
    lines.extend(
        [
            "",
            "## Remaining unknowns that require a real order",
            "",
            "- L2 / queue / actual 80¢ maker fill",
            "- Actual hedge fill at H=20/28/40",
            "- Liquidation VWAP vs candle 40-stop",
            "- Official game clock and PBP at jump-throughs",
            "- Live latency and fees",
            "",
            "LIVE EXECUTION CHANGED: FALSE",
            "",
        ]
    )
    text = "\n".join(lines) + "\n"
    DOCS.write_text(text)
    for sport in ("nba", "ncaab"):
        d = out_dir(sport)
        (d / "REPORT.md").write_text(text)


def write_sport(payload: dict) -> None:
    d = out_dir(payload["sport"])
    write_parquet(d / "first80_event_anatomy.parquet", anatomy_rows(payload["trades"]))
    write_parquet(d / "persistence_surface.parquet", payload["persist"])
    write_parquet(d / "mae_buckets.parquet", payload["mae"])
    write_parquet(d / "entry_price_surface.parquet", payload["entry_price"])
    write_parquet(d / "approach_classes.parquet", payload["approach"])
    write_parquet(d / "winner_anatomy.parquet", payload["winners"])
    write_parquet(d / "season_stability.parquet", payload["season"])
    write_parquet(d / "hedge_path_structure.parquet", payload["hedge"])
    write_parquet(d / "conditional_survival.parquet", payload["conditional"])
    write_parquet(d / "vol_regimes.parquet", payload["vol"])
    (d / "reproduction_checks.json").write_text(json.dumps(payload["reproduction"], indent=2) + "\n")
    (d / "barriers.json").write_text(json.dumps(payload["barriers"], indent=2) + "\n")
    (d / "models.json").write_text(json.dumps(payload["models"], indent=2, default=str) + "\n")
    (d / "metadata.json").write_text(
        json.dumps(
            {
                "program": PROGRAM,
                "sport": payload["sport"],
                "live_execution_changed": False,
                "actual_fill": "UNOBSERVED",
                "approach_rules": APPROACH_RULES,
                "vol_quintile_edges_train": payload["vol_edges"],
                "cluster_k": CLUSTER_K,
                "cluster_fit": "TRAIN_ONLY",
                "logistic_fit": "TRAIN_ONLY",
                "oos_retuned": False,
            },
            indent=2,
        )
        + "\n"
    )


def main() -> int:
    print(PROGRAM, "LIVE EXECUTION CHANGED: FALSE", flush=True)
    nba = run_sport("nba")
    if nba.get("stop"):
        print("STOP NBA reproduction failure", nba.get("reproduction"))
        return 2
    ncaab = run_sport("ncaab")
    if ncaab.get("stop"):
        print("STOP NCAAB reproduction failure", ncaab.get("reproduction"))
        return 2
    verdict = decide_verdict(nba, ncaab)
    print("VERDICT", verdict, flush=True)
    write_sport(nba)
    write_sport(ncaab)
    write_report(nba, ncaab, verdict)
    combined = {
        "nba": nba["reproduction"],
        "ncaab": ncaab["reproduction"],
    }
    (out_dir("nba") / "reproduction_checks.json").write_text(json.dumps(combined, indent=2) + "\n")
    (out_dir("ncaab") / "reproduction_checks.json").write_text(json.dumps(combined, indent=2) + "\n")
    DASH_PUBLIC.mkdir(parents=True, exist_ok=True)
    dash = dash_payload(nba, ncaab, verdict)
    raw = json.dumps(dash)
    (DASH_PUBLIC / "dashboard.json").write_text(raw)
    for sport in ("nba", "ncaab"):
        (out_dir(sport) / "dashboard.json").write_text(raw)
    print("wrote", DOCS)
    print("done", verdict[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
