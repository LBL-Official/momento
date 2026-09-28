#!/usr/bin/env python3
"""FIRST80_OPPONENT_HEDGE_FRONTIER_V2

Test 3 of the FIRST-80 hedge research program.

Candle PRICE_OPPORTUNITY model. Not a maker fill. Not live.

Does not modify V1, liquidation v1, Game Path engines, FIRST01, Risk,
or live execution. LIVE EXECUTION CHANGED: FALSE.
"""

from __future__ import annotations

import json
import math
import random
import sys
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

NBA_SCRIPTS = Path("/Users/user/Desktop/Momento/apps/nba-data/scripts")
sys.path.insert(0, str(NBA_SCRIPTS))
import nba_80_40_execution_audit as A  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import first80_opponent_40_hedge_v1 as V1  # noqa: E402

PROGRAM = "FIRST80_OPPONENT_HEDGE_FRONTIER_V2"
ENTRY = 80
WIN = 20
MISS = -80
STOP = -40
H_MIN = 20
H_MAX = 60
H_ALL = list(range(H_MIN, H_MAX + 1))
H_COARSE = (20, 22, 24, 25, 26, 28, 30, 32, 34, 35, 36, 38, 40, 42, 44, 45, 46, 48, 50)
PERSIST_GRID = (0, 1, 2, 3, 5, 10, 15)
SPLIT_TRAIN_END = "2025-12-31"
SPLIT_VAL_END = "2026-03-15"

# A priori selection protocol. Frozen before any OOS inspection.
MISS_CEILING = 0.01
MIN_VAL_HEDGE_N = 30
MIN_VAL_TRADES = 40
STABILITY_REL_RANGE = 0.25
BANKROLL_CENTS = 5000
PER_GAME_CENTS = 625
BOOT_ITERS = 400
BOOT_SEED = 80
DESK_CONCURRENCY = (1, 2, 3, 5, 8, None)

V1_GATES = {
    "nba": {
        "n": 1230,
        "hedge": 456,
        "win": 774,
        "miss": 0,
        "ev": 5.1707,
        "stop_ev": 4.3902,
    },
    "ncaab": {
        "n": 4099,
        "hedge": 1546,
        "win": 2552,
        "miss": 1,
        "ev": 4.889,
        "stop_ev": 3.9034,
    },
}

DOCS = Path("/Users/user/Desktop/Momento/docs/research/FIRST80_OPPONENT_HEDGE_FRONTIER_V2.md")
DASH_PUBLIC = Path(
    "/Users/user/Desktop/Momento/frontend/first80-hedge-frontier-v2/public/data"
)


def e4(h: int) -> int:
    return h * 100


def split_of(game_date: str | None) -> str:
    if not game_date:
        return "UNSPLIT"
    if game_date <= SPLIT_TRAIN_END:
        return "TRAIN"
    if game_date <= SPLIT_VAL_END:
        return "VALIDATION"
    return "OOS"


def wilson(k: int, n: int) -> dict:
    p, lo, hi = A.wilson(k, n)
    return {"n": n, "k": k, "rate": None if p is None else p / 100.0, "pct": p, "ci95": [lo, hi]}


def quantile(vals: list[float], q: float) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    return s[min(len(s) - 1, max(0, int(round((len(s) - 1) * q))))]


def dist(vals: list[float]) -> dict | None:
    if not vals:
        return None
    return {
        "n": len(vals),
        "mean": round(sum(vals) / len(vals), 4),
        "p10": quantile(vals, 0.10),
        "p25": quantile(vals, 0.25),
        "median": quantile(vals, 0.50),
        "p75": quantile(vals, 0.75),
        "p90": quantile(vals, 0.90),
        "min": min(vals),
        "max": max(vals),
    }


def pnl_hedge(h: int, touched: bool, won: bool) -> int:
    """Lock is 100 − 80 − H = 20 − H, not −H (prompt algebra slip)."""
    if touched:
        return WIN - h
    return WIN if won else MISS


def stop_pnl(rec: dict) -> int:
    if rec.get("stop_close_triggered"):
        return STOP
    if rec["expiration_result_yes"]:
        return WIN
    return 0


def hold_pnl(rec: dict) -> int:
    return WIN if rec["expiration_result_yes"] else MISS


def prepare_trades(sport: str) -> tuple[dict, list[dict], dict]:
    cfg = V1.SPORTS[sport]
    games = V1.load_games(cfg)
    cands = json.loads(cfg["cands"].read_text())
    trades = [
        dict(c)
        for c in cands
        if c.get("status") == "FIRST_80" and c.get("expiration_result_yes") is not None
    ]
    for rec in trades:
        rec["dataset_split"] = split_of(rec.get("game_date"))
        rec["sport"] = sport
        g = games.get(rec.get("event_id"))
        rec["opponent_ticker"] = V1.opponent_of(g, rec["ticker"]) if g else None
        rec["opponent_available"] = rec["opponent_ticker"] is not None
        rec["hedge"] = {}
    return cfg, trades, games


def scan_all_H(cfg: dict, trades: list[dict]) -> None:
    candles = cfg["root"] / "normalized" / cfg["norm"] / "candles_1m"
    opp_win: dict[str, tuple[int, int]] = {}
    held_from: dict[str, int] = {}
    by_opp: dict[str, list[int]] = defaultdict(list)
    for i, rec in enumerate(trades):
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
        "yes_bid_close_e4",
        "yes_ask_close_e4",
        "volume_hundredths",
        "is_valid",
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
            vol = A._opt_int(get["volume_hundredths"][i].as_py())
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
            opp_quotes[ticker].append((t, bid_c, bid_h, ask_c))

    for opp, idxs in by_opp.items():
        quotes = opp_quotes.get(opp, [])
        quotes.sort(key=lambda x: x[0])
        close_map = first_touches(quotes, "close")
        wick_map = first_touches(quotes, "wick")
        for i in idxs:
            rec = trades[i]
            held_map = held_at.get(rec["ticker"], {})
            rec["hedge"] = {
                "close": attach_held(close_map, held_map, rec),
                "wick": attach_held(wick_map, held_map, rec),
            }


def first_touches(quotes: list[tuple], path: str) -> dict[int, dict]:
    """First PRICE_OPPORTUNITY at each H plus persistence / geometry proxies."""
    out: dict[int, dict] = {}
    ring: deque = deque(maxlen=16)
    prev_close = None
    pending = set(H_ALL)
    persist_open: dict[int, int] = {}
    persist_done: dict[int, int] = {}
    max_after: dict[int, int] = {}
    bars_after: dict[int, int] = {}
    above_run: dict[int, int] = {}

    for idx, (t, bid_c, bid_h, ask_c) in enumerate(quotes):
        px = bid_c if path == "close" else bid_h
        ring.append((t, bid_c))
        if px is None:
            prev_close = bid_c if bid_c is not None else prev_close
            continue
        already_open = list(persist_open)
        hit_now = [h for h in list(pending) if px >= e4(h)]
        for h in hit_now:
            pending.remove(h)
            last5 = [b for _, b in list(ring)[-6:-1] if b is not None]
            vel = None
            if last5:
                vel = (bid_c - last5[0]) / 100.0 if bid_c is not None else None
            jump = prev_close is not None and prev_close < e4(h) - 1000
            gradual = False
            if len(last5) >= 3:
                tail = last5[-3:]
                gradual = tail[0] < tail[1] < tail[2] < e4(h) and not jump
            vol5 = None
            if len(last5) >= 3:
                m = sum(last5) / len(last5)
                vol5 = (sum((x - m) ** 2 for x in last5) / len(last5)) ** 0.5 / 100.0
            out[h] = {
                "ts": t,
                "opp_bid_e4": bid_c,
                "opp_high_e4": bid_h,
                "opp_ask_e4": ask_c,
                "prev_opp_bid_e4": prev_close,
                "jump_10c": bool(jump),
                "gradual": bool(gradual),
                "velocity_cents": None if vel is None else round(vel, 4),
                "vol5_pre": None if vol5 is None else round(vol5, 4),
                "label": "PRICE_OPPORTUNITY",
                "fill_status": "NOT_ACTUAL_FILL",
            }
            persist_open[h] = 0
            above_run[h] = 1
            max_after[h] = px
            bars_after[h] = 0
        for h in already_open:
            bars_after[h] = bars_after.get(h, 0) + 1
            if px > max_after.get(h, px):
                max_after[h] = px
            if px >= e4(h):
                persist_open[h] += 1
                above_run[h] = above_run.get(h, 0) + 1
            elif h in persist_open:
                persist_done[h] = persist_open[h]
                del persist_open[h]
        prev_close = bid_c if bid_c is not None else prev_close

    for h, rec in out.items():
        rec["persist_min"] = persist_done.get(h, persist_open.get(h, 0))
        rec["max_opp_after_e4"] = max_after.get(h)
        rec["bars_after"] = bars_after.get(h, 0)
        rec["regime"] = regime_of(rec)
    return out


def regime_of(rec: dict) -> str:
    if rec.get("jump_10c"):
        return "C_LARGE_UPWARD_JUMP"
    if rec.get("persist_min", 0) >= 5:
        return "A_PERSISTENT_ABOVE"
    if rec.get("persist_min", 0) == 0:
        return "B_IMMEDIATE_REVERSAL"
    if rec.get("gradual"):
        return "D_GRADUAL_APPROACH"
    if rec.get("vol5_pre") is not None and rec["vol5_pre"] >= 3:
        return "E_HIGH_VOLATILITY_CROSSING"
    return "A_PERSISTENT_ABOVE" if rec.get("persist_min", 0) >= 2 else "D_GRADUAL_APPROACH"


def attach_held(hmap: dict[int, dict], held_map: dict[int, int], rec: dict) -> dict[int, dict]:
    out = {}
    for h, row in hmap.items():
        d = dict(row)
        d["held_bid_e4"] = held_map.get(d["ts"])
        if d["held_bid_e4"] is not None and d.get("opp_bid_e4") is not None:
            d["complement_e4"] = d["held_bid_e4"] + d["opp_bid_e4"]
        else:
            d["complement_e4"] = None
        fav40 = rec.get("first_40_close_ts")
        d["dt_fav40_minus_hedge_s"] = None if not fav40 else int(fav40) - int(d["ts"])
        d["dt_entry_to_hedge_s"] = int(d["ts"]) - int(rec["first_80_timestamp"])
        close_ts = rec.get("close_ts")
        d["dt_hedge_to_close_s"] = None if close_ts is None else int(close_ts) - int(d["ts"])
        out[h] = d
    return out


def reproduce_v1(sport: str, trades: list[dict]) -> dict:
    gate = V1_GATES[sport]
    n = len(trades)
    hedge = win = miss = 0
    pnls = []
    stops = []
    for rec in trades:
        row = rec.get("hedge", {}).get("close", {}).get(40)
        touched = row is not None
        if touched:
            hedge += 1
        elif rec["expiration_result_yes"]:
            win += 1
        else:
            miss += 1
        pnls.append(pnl_hedge(40, touched, rec["expiration_result_yes"]))
        stops.append(stop_pnl(rec))
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
        "observed": {
            "n": n,
            "hedge": hedge,
            "win": win,
            "miss": miss,
            "ev": ev,
            "stop_ev": stop_ev,
        },
        "expected": gate,
        "label": "CANDLE PRICE_OPPORTUNITY — NOT ACTUAL_FILL",
    }


def metrics_for(
    trades: list[dict],
    h: int,
    path: str,
    persist_min: int = 0,
) -> dict:
    n = len(trades)
    if n == 0:
        return {"n": 0, "h": h, "path": path, "persist_min": persist_min}
    opp = false = prot = miss = 0
    pnls = []
    t_hedge = []
    t_lead = []
    persist = []
    regimes = defaultdict(int)
    held = []
    comps = []
    for rec in trades:
        row = rec.get("hedge", {}).get(path, {}).get(h)
        touched = row is not None and row.get("persist_min", 0) >= persist_min
        won = bool(rec["expiration_result_yes"])
        if touched:
            opp += 1
            if won:
                false += 1
            else:
                prot += 1
            t_hedge.append(row["dt_entry_to_hedge_s"] / 60.0)
            if row.get("dt_fav40_minus_hedge_s") is not None:
                t_lead.append(row["dt_fav40_minus_hedge_s"] / 60.0)
            persist.append(row.get("persist_min") or 0)
            regimes[row.get("regime") or "UNKNOWN"] += 1
            if row.get("held_bid_e4") is not None:
                held.append(row["held_bid_e4"] / 100.0)
            if row.get("complement_e4") is not None:
                comps.append(row["complement_e4"] / 100.0)
        elif not won:
            miss += 1
        pnls.append(pnl_hedge(h, touched, won))
    losses = sum(1 for r in trades if not r["expiration_result_yes"])
    ev = sum(pnls) / n
    reserved = ENTRY + h
    p_opp = opp / n
    return {
        "h": h,
        "path": path,
        "persist_min": persist_min,
        "status": "PRICE_OPPORTUNITY",
        "fill_status": "NOT_ACTUAL_FILL",
        "n": n,
        "hedge_opportunities": opp,
        "false_hedges": false,
        "protected_losses": prot,
        "catastrophic_misses": miss,
        "losses": losses,
        "no_hedge_wins": n - opp - miss,
        "p_opportunity": wilson(opp, n),
        "p_false_hedge": wilson(false, n),
        "p_protected": wilson(prot, n),
        "p_miss": wilson(miss, n),
        "precision_loss": wilson(prot, opp) if opp else wilson(0, 0),
        "recall_loss": wilson(prot, losses) if losses else wilson(0, 0),
        "p_yes_given_hedge": wilson(false, opp) if opp else wilson(0, 0),
        "gross_ev_cents": round(ev, 4),
        "gross_ev_R": round(ev / WIN, 4),
        "reserved_capital_cents": reserved,
        "ev_per_reserved": round(ev / reserved, 6),
        "conditional_avg_capital_cents": round(ENTRY + p_opp * h, 4),
        "ev_per_conditional_capital": round(ev / (ENTRY + p_opp * h), 6)
        if (ENTRY + p_opp * h)
        else None,
        "fee_max_total_cents": round(ev, 4),
        "hedge_fee_max_if_entry_zero": None if opp == 0 else round(ev / p_opp, 4),
        "net_ev_symbolic": "GrossEV - EntryFee - P(opp)*HedgeFee",
        "time_to_hedge_min": dist(t_hedge),
        "hedge_leads_fav40_min": dist(t_lead),
        "persist_min_dist": dist([float(x) for x in persist]),
        "held_bid_at_H_cents": dist(held),
        "complement_sum_cents": dist(comps),
        "regimes": dict(regimes),
        "p_persist_ge": {
            str(x): round(sum(1 for p in persist if p >= x) / opp, 4) if opp else None
            for x in PERSIST_GRID
        },
    }


def frontier_table(trades: list[dict], path: str, persist_min: int = 0) -> list[dict]:
    return [metrics_for(trades, h, path, persist_min) for h in H_ALL]


def split_trades(trades: list[dict], split: str) -> list[dict]:
    if split == "FULL":
        return trades
    return [t for t in trades if t.get("dataset_split") == split]


def stability(rows: list[dict], h: int) -> dict:
    by_h = {r["h"]: r["ev_per_reserved"] for r in rows}
    nb = [by_h[x] for x in range(h - 2, h + 3) if x in by_h]
    if not nb:
        return {"flag": "INSUFFICIENT", "range": None}
    lo, hi = min(nb), max(nb)
    mid = by_h.get(h)
    rel = None if not mid else (hi - lo) / abs(mid) if mid else None
    spike = rel is not None and rel > STABILITY_REL_RANGE
    return {
        "neighborhood": nb,
        "range": round(hi - lo, 6),
        "rel_range": None if rel is None else round(rel, 4),
        "flag": "THRESHOLD_OVERFIT_RISK" if spike else "STABLE_PLATEAU",
    }


def select_policy(val_rows: list[dict], val_n: int) -> dict:
    """TRAIN may be inspected; only VALIDATION chooses. OOS unseen here."""
    eligible = []
    for r in val_rows:
        miss = r["p_miss"]["rate"]
        if miss is None:
            continue
        if val_n < MIN_VAL_TRADES:
            continue
        if r["hedge_opportunities"] < MIN_VAL_HEDGE_N:
            continue
        if miss > MISS_CEILING:
            continue
        eligible.append(r)
    if not eligible:
        return {
            "selected_h": None,
            "reason": "NO_ELIGIBLE_H",
            "protocol": selection_protocol(),
        }
    scored = sorted(eligible, key=lambda r: (-r["ev_per_reserved"], r["h"]))
    raw = scored[0]
    stab = stability(val_rows, raw["h"])
    chosen = raw
    if stab["flag"] == "THRESHOLD_OVERFIT_RISK":
        by_h = {r["h"]: r for r in val_rows}
        smooth = []
        for r in eligible:
            nb = [
                by_h[x]["ev_per_reserved"]
                for x in range(r["h"] - 2, r["h"] + 3)
                if x in by_h
            ]
            smooth.append((sum(nb) / len(nb), r))
        smooth.sort(key=lambda x: (-x[0], x[1]["h"]))
        chosen = smooth[0][1]
    return {
        "selected_h": chosen["h"],
        "path": "close",
        "persist_min": 0,
        "capital_architecture": "A_RESERVED",
        "raw_argmax_h": raw["h"],
        "stability": stab,
        "val_metrics": {
            "gross_ev_cents": chosen["gross_ev_cents"],
            "ev_per_reserved": chosen["ev_per_reserved"],
            "p_miss": chosen["p_miss"],
            "hedge_opportunities": chosen["hedge_opportunities"],
        },
        "protocol": selection_protocol(),
        "eligible_n": len(eligible),
    }


def selection_protocol() -> dict:
    return {
        "split": f"TRAIN game_date<={SPLIT_TRAIN_END}; VAL {SPLIT_TRAIN_END}<d<={SPLIT_VAL_END}; OOS after {SPLIT_VAL_END}",
        "path": "close",
        "persist_min": 0,
        "objective": "max VALIDATION ev_per_reserved_capital (80+H)",
        "miss_ceiling": MISS_CEILING,
        "min_val_hedge_n": MIN_VAL_HEDGE_N,
        "min_val_trades": MIN_VAL_TRADES,
        "stability": f"5-point neighborhood rel range > {STABILITY_REL_RANGE} => THRESHOLD_OVERFIT_RISK, use smoothed plateau",
        "oos": "evaluate exactly once after freeze",
    }


def block_bootstrap(trades: list[dict], h: int, path: str, iters: int) -> dict:
    if not trades:
        return {"iters": 0}
    by_date: dict[str, list[dict]] = defaultdict(list)
    for t in trades:
        by_date[t.get("game_date") or "NA"].append(t)
    dates = list(by_date)
    rng = random.Random(BOOT_SEED + h)
    evs = []
    for _ in range(iters):
        sample = []
        for _d in dates:
            sample.extend(by_date[rng.choice(dates)])
        if not sample:
            continue
        evs.append(metrics_for(sample, h, path)["gross_ev_cents"])
    evs.sort()

    def q(p):
        if not evs:
            return None
        return evs[min(len(evs) - 1, int((len(evs) - 1) * p))]

    return {
        "method": "game_date_block_bootstrap",
        "iters": len(evs),
        "mean": None if not evs else round(sum(evs) / len(evs), 4),
        "p025": q(0.025),
        "p975": q(0.975),
        "label": "HISTORICAL RESAMPLE — NOT A FORECAST",
    }


def desk_sim(
    trades: list[dict],
    kind: str,
    h: int | None,
    max_conc: int | None,
    architecture: str,
) -> dict:
    """HISTORICAL PATH SIMULATION. NOT A FORECAST."""
    ordered = sorted(
        trades, key=lambda t: (t.get("first_80_timestamp") or 0, t.get("ticker") or "")
    )
    cash = BANKROLL_CENTS
    reserved = 0
    equity = BANKROLL_CENTS
    peak = BANKROLL_CENTS
    max_dd = 0
    open_pos: list[tuple[int, int]] = []
    skipped_cap = 0
    skipped_conc = 0
    taken = 0
    week_pnl: dict[str, int] = defaultdict(int)
    month_pnl: dict[str, int] = defaultdict(int)
    peak_reserved = 0

    def release(now: int):
        nonlocal reserved, cash, equity, peak, max_dd
        keep = []
        for rel, cap, pnl in open_pos:
            if rel <= now:
                cash += cap + pnl
                reserved -= cap
            else:
                keep.append((rel, cap, pnl))
        open_pos[:] = keep
        equity = cash + reserved
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)

    for rec in ordered:
        now = int(rec["first_80_timestamp"])
        release(now)
        close_ts = int(rec["close_ts"]) if rec.get("close_ts") is not None else now + 1
        extra = 0
        if kind == "hedge":
            row = rec.get("hedge", {}).get("close", {}).get(h)
            touched = row is not None
            pnl_1 = pnl_hedge(h, touched, rec["expiration_result_yes"])
            exit_ts = close_ts
            if architecture == "A_RESERVED":
                unit = ENTRY + h
                qty = PER_GAME_CENTS // unit
                cost = qty * unit
            else:
                qty = PER_GAME_CENTS // ENTRY
                cost = qty * ENTRY
                extra = qty * h if touched else 0
        elif kind == "stop":
            pnl_1 = stop_pnl(rec)
            exit_ts = close_ts
            qty = PER_GAME_CENTS // ENTRY
            cost = qty * ENTRY
        else:
            pnl_1 = hold_pnl(rec)
            exit_ts = close_ts
            qty = PER_GAME_CENTS // ENTRY
            cost = qty * ENTRY
        if qty < 1:
            skipped_cap += 1
            continue
        if max_conc is not None and len(open_pos) >= max_conc:
            skipped_conc += 1
            continue
        need = cost + (extra if architecture == "B_CONDITIONAL" else 0)
        if architecture == "B_CONDITIONAL":
            need = cost
        if cash < need:
            skipped_cap += 1
            continue
        cash -= cost
        reserved += cost
        deployed = cost
        if extra:
            if cash >= extra:
                cash -= extra
                reserved += extra
                deployed += extra
            else:
                pnl_1 = hold_pnl(rec)
        peak_reserved = max(peak_reserved, reserved)
        pnl = qty * pnl_1
        open_pos.append((exit_ts, deployed, pnl))
        equity = cash + reserved
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
        taken += 1
        gd = rec.get("game_date") or "NA"
        week_pnl[_iso_week(gd)] += pnl
        month_pnl[gd[:7] if gd != "NA" else "NA"] += pnl
    release(2**31)

    worst_week = min(week_pnl.values()) if week_pnl else 0
    worst_month = min(month_pnl.values()) if month_pnl else 0
    return {
        "kind": kind,
        "h": h,
        "architecture": architecture if kind == "hedge" else None,
        "max_concurrent": max_conc if max_conc is not None else "unlimited",
        "initial_bankroll_cents": BANKROLL_CENTS,
        "per_game_cents": PER_GAME_CENTS,
        "terminal_bankroll_cents": equity,
        "max_drawdown_cents": max_dd,
        "worst_week_pnl_cents": worst_week,
        "worst_month_pnl_cents": worst_month,
        "taken": taken,
        "skipped_capital": skipped_cap,
        "skipped_concurrency": skipped_conc,
        "peak_reserved_cents": peak_reserved,
        "return_on_initial": round((equity - BANKROLL_CENTS) / BANKROLL_CENTS, 4),
        "label": "HISTORICAL PATH SIMULATION — NOT A FORECAST",
    }


def _iso_week(gd: str) -> str:
    if not gd or gd == "NA":
        return "NA"
    try:
        d = datetime.strptime(gd, "%Y-%m-%d")
        y, w, _ = d.isocalendar()
        return f"{y}-W{w:02d}"
    except ValueError:
        return gd


def write_parquet(rows: list[dict], path: Path) -> None:
    if not rows:
        pq.write_table(pa.table({"empty": pa.array([], type=pa.int64())}), path)
        return
    keys = sorted({k for r in rows for k in r})
    cols = {}
    for k in keys:
        vals = [r.get(k) for r in rows]
        if all(isinstance(v, bool) for v in vals if v is not None) and any(
            isinstance(v, bool) for v in vals
        ):
            cols[k] = pa.array(vals, type=pa.bool_())
        elif all(isinstance(v, int) and not isinstance(v, bool) for v in vals if v is not None):
            cols[k] = pa.array(vals, type=pa.int64())
        elif all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals if v is not None):
            cols[k] = pa.array(
                [None if v is None else float(v) for v in vals], type=pa.float64()
            )
        else:
            cols[k] = pa.array(
                [None if v is None else json.dumps(v) if isinstance(v, (dict, list)) else str(v) for v in vals]
            )
    pq.write_table(pa.table(cols), path)


def flatten_metrics(sport: str, split: str, rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        out.append(
            {
                "sport": sport,
                "split": split,
                "h": r["h"],
                "path": r["path"],
                "persist_min": r["persist_min"],
                "n": r["n"],
                "hedge_opportunities": r["hedge_opportunities"],
                "false_hedges": r["false_hedges"],
                "protected_losses": r["protected_losses"],
                "catastrophic_misses": r["catastrophic_misses"],
                "gross_ev_cents": r["gross_ev_cents"],
                "ev_per_reserved": r["ev_per_reserved"],
                "p_opportunity": r["p_opportunity"]["rate"],
                "p_false": r["p_false_hedge"]["rate"],
                "p_miss": r["p_miss"]["rate"],
                "precision_loss": r["precision_loss"]["rate"],
                "recall_loss": r["recall_loss"]["rate"],
            }
        )
    return out


def trade_path_rows(sport: str, trades: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    paths = []
    plaus = []
    tth = []
    for rec in trades:
        for path in ("close", "wick"):
            for h, row in rec.get("hedge", {}).get(path, {}).items():
                base = {
                    "sport": sport,
                    "ticker": rec["ticker"],
                    "opponent_ticker": rec.get("opponent_ticker"),
                    "game_date": rec.get("game_date"),
                    "dataset_split": rec.get("dataset_split"),
                    "won": rec["expiration_result_yes"],
                    "stop_close": rec.get("stop_close_triggered"),
                    "path": path,
                    "h": h,
                    "ts": row.get("ts"),
                    "dt_entry_s": row.get("dt_entry_to_hedge_s"),
                    "dt_lead_fav40_s": row.get("dt_fav40_minus_hedge_s"),
                    "persist_min": row.get("persist_min"),
                    "held_bid_e4": row.get("held_bid_e4"),
                    "opp_bid_e4": row.get("opp_bid_e4"),
                    "complement_e4": row.get("complement_e4"),
                    "regime": row.get("regime"),
                    "jump_10c": row.get("jump_10c"),
                    "fill_status": "NOT_ACTUAL_FILL",
                }
                paths.append(base)
                plaus.append(
                    {
                        **base,
                        "label": "FILL_PLAUSIBILITY_PROXY",
                        "velocity_cents": row.get("velocity_cents"),
                        "vol5_pre": row.get("vol5_pre"),
                        "max_opp_after_e4": row.get("max_opp_after_e4"),
                    }
                )
                tth.append(
                    {
                        "sport": sport,
                        "path": path,
                        "h": h,
                        "dt_entry_min": None
                        if row.get("dt_entry_to_hedge_s") is None
                        else row["dt_entry_to_hedge_s"] / 60.0,
                        "dt_lead_fav40_min": None
                        if row.get("dt_fav40_minus_hedge_s") is None
                        else row["dt_fav40_minus_hedge_s"] / 60.0,
                    }
                )
    return paths, plaus, tth


def run_sport(sport: str) -> dict:
    print(f"== {sport} ==", flush=True)
    cfg, trades, _games = prepare_trades(sport)
    assert len(trades) == V1_GATES[sport]["n"], (sport, len(trades))
    scan_all_H(cfg, trades)
    repro = reproduce_v1(sport, trades)
    print(f"  reproduce H=40: {repro['ok']} {repro['observed']}", flush=True)
    if not repro["ok"]:
        return {"sport": sport, "reproduction": repro, "halted": True}

    splits = {
        "FULL": trades,
        "TRAIN": split_trades(trades, "TRAIN"),
        "VALIDATION": split_trades(trades, "VALIDATION"),
        "OOS": split_trades(trades, "OOS"),
    }
    split_counts = {k: len(v) for k, v in splits.items()}
    print(f"  splits {split_counts}", flush=True)

    frontiers = {}
    flat = []
    for split, rows in splits.items():
        frontiers[split] = {
            "close": frontier_table(rows, "close", 0),
            "wick": frontier_table(rows, "wick", 0),
        }
        flat.extend(flatten_metrics(sport, split, frontiers[split]["close"]))
        flat.extend(flatten_metrics(sport, split, frontiers[split]["wick"]))

    persist_surface = []
    for h in H_COARSE:
        for x in PERSIST_GRID:
            persist_surface.append(metrics_for(trades, h, "close", x))

    policy = select_policy(frontiers["VALIDATION"]["close"], split_counts["VALIDATION"])
    h_star = policy["selected_h"]
    print(f"  frozen H*={h_star} from VALIDATION only", flush=True)

    oos_eval = None
    if h_star is not None:
        oos_eval = {
            "TRAIN": metrics_for(splits["TRAIN"], h_star, "close"),
            "VALIDATION": metrics_for(splits["VALIDATION"], h_star, "close"),
            "OOS": metrics_for(splits["OOS"], h_star, "close"),
            "FULL": metrics_for(splits["FULL"], h_star, "close"),
        }

    boots = {}
    for label, hh in (("H40", 40), ("H30", 30), ("H35", 35), ("H45", 45), ("HSTAR", h_star)):
        if hh is None:
            continue
        boots[label] = {
            "FULL": block_bootstrap(trades, hh, "close", BOOT_ITERS),
            "OOS": block_bootstrap(splits["OOS"], hh, "close", min(BOOT_ITERS, 200)),
        }

    desk = []
    for conc in DESK_CONCURRENCY:
        desk.append(desk_sim(trades, "hold", None, conc, "A_RESERVED"))
        desk.append(desk_sim(trades, "stop", None, conc, "A_RESERVED"))
        for hh in (30, 35, 40, 45, h_star):
            if hh is None:
                continue
            desk.append(desk_sim(trades, "hedge", hh, conc, "A_RESERVED"))
            desk.append(desk_sim(trades, "hedge", hh, conc, "B_CONDITIONAL"))

    paths, plaus, tth = trade_path_rows(sport, trades)
    out = cfg["root"] / "derived" / cfg["norm"] / "first80_opponent_hedge_frontier_v2"
    out.mkdir(parents=True, exist_ok=True)
    write_parquet(flat, out / "threshold_metrics.parquet")
    write_parquet(paths, out / "trade_level_paths.parquet")
    write_parquet(plaus, out / "fill_plausibility_proxy.parquet")
    write_parquet(tth, out / "time_to_hedge.parquet")
    write_parquet(
        [
            {
                "sport": sport,
                "h": r["h"],
                "arch": "A_RESERVED",
                "reserved": r["reserved_capital_cents"],
                "ev": r["gross_ev_cents"],
                "ev_per_reserved": r["ev_per_reserved"],
                "cond_cap": r["conditional_avg_capital_cents"],
                "ev_per_cond": r["ev_per_conditional_capital"],
            }
            for r in frontiers["FULL"]["close"]
        ],
        out / "capital_economics.parquet",
    )
    write_parquet(flat, out / "frontier_results.parquet")
    boot_rows = []
    for k, v in boots.items():
        for sp, b in v.items():
            boot_rows.append({"key": k, "split": sp, **b})
    write_parquet(boot_rows, out / "bootstrap_results.parquet")

    payload = {
        "program": PROGRAM,
        "sport": sport,
        "live_execution_changed": False,
        "architecture_c_portfolio_margin": "UNAVAILABLE",
        "actual_fill_experiment": "NOT_RUN",
        "split_counts": split_counts,
        "reproduction": repro,
        "policy": policy,
        "oos_eval": {
            k: {
                "n": v["n"],
                "gross_ev_cents": v["gross_ev_cents"],
                "ev_per_reserved": v["ev_per_reserved"],
                "hedge_opportunities": v["hedge_opportunities"],
                "false_hedges": v["false_hedges"],
                "protected_losses": v["protected_losses"],
                "catastrophic_misses": v["catastrophic_misses"],
                "p_miss": v["p_miss"],
                "recall_loss": v["recall_loss"],
                "precision_loss": v["precision_loss"],
            }
            for k, v in (oos_eval or {}).items()
        },
        "frontiers": {
            split: {
                path: [
                    {
                        "h": r["h"],
                        "n": r["n"],
                        "hedge_opportunities": r["hedge_opportunities"],
                        "false_hedges": r["false_hedges"],
                        "protected_losses": r["protected_losses"],
                        "catastrophic_misses": r["catastrophic_misses"],
                        "no_hedge_wins": r["no_hedge_wins"],
                        "gross_ev_cents": r["gross_ev_cents"],
                        "ev_per_reserved": r["ev_per_reserved"],
                        "ev_per_conditional_capital": r["ev_per_conditional_capital"],
                        "p_opportunity": r["p_opportunity"],
                        "p_false_hedge": r["p_false_hedge"],
                        "p_miss": r["p_miss"],
                        "precision_loss": r["precision_loss"],
                        "recall_loss": r["recall_loss"],
                        "time_to_hedge_min": r["time_to_hedge_min"],
                        "hedge_leads_fav40_min": r["hedge_leads_fav40_min"],
                        "p_persist_ge": r["p_persist_ge"],
                        "regimes": r["regimes"],
                        "held_bid_at_H_cents": r["held_bid_at_H_cents"],
                        "fee_max_total_cents": r["fee_max_total_cents"],
                    }
                    for r in frontiers[split][path]
                ]
                for path in ("close", "wick")
            }
            for split in frontiers
        },
        "persist_surface": [
            {
                "h": r["h"],
                "persist_min": r["persist_min"],
                "hedge_opportunities": r["hedge_opportunities"],
                "false_hedges": r["false_hedges"],
                "protected_losses": r["protected_losses"],
                "catastrophic_misses": r["catastrophic_misses"],
                "gross_ev_cents": r["gross_ev_cents"],
                "ev_per_reserved": r["ev_per_reserved"],
            }
            for r in persist_surface
        ],
        "bootstrap": boots,
        "desk": desk,
        "comparators": {
            "hold_full_ev": round(sum(hold_pnl(t) for t in trades) / len(trades), 4),
            "stop_full_ev": round(sum(stop_pnl(t) for t in trades) / len(trades), 4),
        },
    }
    (out / "reproduction_checks.json").write_text(json.dumps(repro, indent=2) + "\n")
    (out / "metadata.json").write_text(
        json.dumps(
            {
                "program": PROGRAM,
                "sport": sport,
                "live_execution_changed": False,
                "splits": split_counts,
                "selection": selection_protocol(),
                "candle_proxy": True,
                "actual_fill": "NOT_RUN",
            },
            indent=2,
        )
        + "\n"
    )
    (out / "summary.json").write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def comparison_rows(nba: dict, ncaab: dict) -> list[dict]:
    rows = []
    for sport, payload in (("nba", nba), ("ncaab", ncaab)):
        full = payload["frontiers"]["FULL"]["close"]
        by_h = {r["h"]: r for r in full}
        h_star = payload["policy"]["selected_h"]
        hold = payload["comparators"]["hold_full_ev"]
        stop = payload["comparators"]["stop_full_ev"]
        rows.append(
            {
                "strategy": "Hold to expiration",
                "sport": sport,
                "h": None,
                "gross_ev": hold,
                "reserved": 80,
                "ev_cap": hold / 80,
            }
        )
        rows.append(
            {
                "strategy": "80/40 reactive stop proxy",
                "sport": sport,
                "h": None,
                "gross_ev": stop,
                "reserved": 80,
                "ev_cap": stop / 80,
            }
        )
        for hh, name in ((30, "Opponent H=30"), (35, "Opponent H=35"), (40, "Opponent H=40"), (45, "Opponent H=45"), (h_star, "Selected H*")):
            if hh is None or hh not in by_h:
                continue
            r = by_h[hh]
            rows.append(
                {
                    "strategy": name,
                    "sport": sport,
                    "h": hh,
                    "opportunity_rate": r["p_opportunity"]["rate"],
                    "false_hedges": r["false_hedges"],
                    "protected": r["protected_losses"],
                    "miss": r["catastrophic_misses"],
                    "gross_ev": r["gross_ev_cents"],
                    "reserved": 80 + hh,
                    "ev_cap": r["ev_per_reserved"],
                    "recall": r["recall_loss"]["rate"],
                    "precision": r["precision_loss"]["rate"],
                }
            )
    return rows


def write_report(nba: dict, ncaab: dict) -> None:
    hn = ncaab["policy"]["selected_h"]
    hb = nba["policy"]["selected_h"]
    def ev(p, split, h):
        if h is None:
            return None
        for r in p["frontiers"][split]["close"]:
            if r["h"] == h:
                return r["gross_ev_cents"]
        return None

    def miss(p, split, h):
        for r in p["frontiers"][split]["close"]:
            if r["h"] == h:
                return r["catastrophic_misses"], r["p_miss"]["pct"]
        return None, None

    n40 = next(r for r in ncaab["frontiers"]["FULL"]["close"] if r["h"] == 40)
    b40 = next(r for r in nba["frontiers"]["FULL"]["close"] if r["h"] == 40)
    nstar = next((r for r in ncaab["frontiers"]["FULL"]["close"] if r["h"] == hn), None)
    bstar = next((r for r in nba["frontiers"]["FULL"]["close"] if r["h"] == hb), None)

    # Verdict logic (pre-specified):
    # A if both sports H* in [30,50], OOS EV>0, miss OOS <= 1%, not spike, reserved EV >= stop
    # D if per-contract better but reserved worse than stop
    # B if economics ok but fills unobserved (default when A fails only on execution)
    # C if H* jumps or OOS collapses
    # E if no improvement vs 80/40 after capital+uncertainty
    verdict, why = decide_verdict(nba, ncaab)

    lines = [
        "# FIRST80_OPPONENT_HEDGE_FRONTIER_V2",
        "",
        "Research only. **LIVE EXECUTION CHANGED: FALSE.**",
        "",
        "```text",
        "CANDLE PRICE_OPPORTUNITY  ≠  ACTUAL MAKER FILL",
        "ACTUAL FILL EXPERIMENT: NOT_RUN",
        "Architecture C (portfolio margin): UNAVAILABLE",
        "```",
        "",
        f"**Verdict: {verdict}** — {why}",
        "",
        "Test 3. Does not modify V1, liquidation v1, Game Path V1–V4, FIRST01, Risk, or live execution.",
        "",
        "## Question 1 — Does H=40 reproduce?",
        "",
        f"- NCAAB: {ncaab['reproduction']['ok']} observed {ncaab['reproduction']['observed']}",
        f"- NBA: {nba['reproduction']['ok']} observed {nba['reproduction']['observed']}",
        "",
        "Gate required 1,546 / 2,552 / 1 / +4.89¢ and 456 / 774 / 0 / +5.17¢.",
        "",
        "## Question 2 — Is there a robust hedge-price frontier?",
        "",
        f"NCAAB H=40 close: opp {n40['hedge_opportunities']}, EV {n40['gross_ev_cents']}¢, miss {n40['catastrophic_misses']}, recall {n40['recall_loss']['pct']}%.",
        f"NBA H=40 close: opp {b40['hedge_opportunities']}, EV {b40['gross_ev_cents']}¢, miss {b40['catastrophic_misses']}, recall {b40['recall_loss']['pct']}%.",
        "",
        "Full 20–60¢ close frontiers are in `summary.json` / the dashboard. Wick remains a diagnostic.",
        "",
        "## Question 3 — False hedges vs catastrophic misses",
        "",
        "Higher H → fewer opportunities, more misses, fewer false hedges, more negative lock (−H).",
        "Lower H → more protection, more false locks, smaller per-lock loss.",
        "",
        "## Question 4 — Cross-sport H*",
        "",
        f"- NCAAB selected H* = **{hn}** (VALIDATION only). Stability: {ncaab['policy'].get('stability', {}).get('flag')}",
        f"- NBA selected H* = **{hb}** (VALIDATION only). Stability: {nba['policy'].get('stability', {}).get('flag')}",
        "",
        "## Question 5 — TRAIN → VAL → OOS",
        "",
        "### NCAAB H*",
        "",
        _split_table(ncaab),
        "",
        "### NBA H*",
        "",
        _split_table(nba),
        "",
        "## Question 6 — Capital",
        "",
        "Architecture A reserves 80+H at entry. Per-contract EV can beat 80/40 while",
        "EV / reserved capital and $6.25-sized contract count do not.",
        "Architecture B funds H only on opportunity (research only; live Risk cannot).",
        "Architecture C portfolio offset: **UNAVAILABLE** (not verified in-repo or in official docs used here).",
        "",
        "## Question 7 — Fill plausibility",
        "",
        "Regimes are PROXY / NOT ACTUAL FILL: persistent-above, immediate reversal,",
        "jump ≥10¢, gradual approach, high pre-cross vol. See `fill_plausibility_proxy.parquet`.",
        "",
        "## Question 8 — Live telemetry required",
        "",
        "T_submit, T_ack, first touch, first/last fill, VWAP, remaining qty, cancel,",
        "bid/ask/depth if available. Object: P(ActualMakerFill | H, path, persist, vol).",
        "Status: **NOT_RUN**.",
        "",
        "## Selection protocol (a priori)",
        "",
        json.dumps(selection_protocol(), indent=2),
        "",
        "## Comparison (FULL close path)",
        "",
        "| Strategy | Sport | H | Opp rate | False | Protected | Miss | Gross EV ¢ | Reserved | EV/cap |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in comparison_rows(nba, ncaab):
        lines.append(
            f"| {r['strategy']} | {r['sport']} | {r.get('h') if r.get('h') is not None else '—'} | "
            f"{_fmt(r.get('opportunity_rate'))} | {r.get('false_hedges', '—')} | "
            f"{r.get('protected', '—')} | {r.get('miss', '—')} | {r['gross_ev']} | "
            f"{r['reserved']} | {round(r['ev_cap'], 5)} |"
        )
    lines.extend(
        [
            "",
            "Code: `apps/ncaab-data/scripts/first80_opponent_hedge_frontier_v2.py`",
            "Dashboard: `frontend/first80-hedge-frontier-v2/`",
            "Artifacts: `.../derived/{nba,ncaab}/first80_opponent_hedge_frontier_v2/`",
            "",
        ]
    )
    DOCS.write_text("\n".join(lines) + "\n")
    for sport, payload in (("ncaab", ncaab), ("nba", nba)):
        out = V1.SPORTS[sport]["root"] / "derived" / V1.SPORTS[sport]["norm"] / "first80_opponent_hedge_frontier_v2"
        (out / "REPORT.md").write_text("\n".join(lines) + "\n")


def _fmt(x):
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.4f}"
    return x


def _split_table(payload: dict) -> str:
    ev = payload.get("oos_eval") or {}
    if not ev:
        return "_no H*_"
    lines = ["| Split | n | Opp | False | Protected | Miss | EV ¢ | EV/reserved |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for k in ("TRAIN", "VALIDATION", "OOS"):
        v = ev[k]
        lines.append(
            f"| {k} | {v['n']} | {v['hedge_opportunities']} | {v['false_hedges']} | "
            f"{v['protected_losses']} | {v['catastrophic_misses']} | {v['gross_ev_cents']} | "
            f"{v['ev_per_reserved']} |"
        )
    return "\n".join(lines)


def decide_verdict(nba: dict, ncaab: dict) -> tuple[str, str]:
    hn = ncaab["policy"]["selected_h"]
    hb = nba["policy"]["selected_h"]
    if hn is None or hb is None:
        return "E", "VALIDATION selected no eligible H on at least one sport."
    n_oos = ncaab["oos_eval"]["OOS"]
    b_oos = nba["oos_eval"]["OOS"]
    n_flag = ncaab["policy"].get("stability", {}).get("flag")
    b_flag = nba["policy"].get("stability", {}).get("flag")
    n40 = next(r for r in ncaab["frontiers"]["FULL"]["close"] if r["h"] == 40)
    b40 = next(r for r in nba["frontiers"]["FULL"]["close"] if r["h"] == 40)
    ns = next(r for r in ncaab["frontiers"]["FULL"]["close"] if r["h"] == hn)
    bs = next(r for r in nba["frontiers"]["FULL"]["close"] if r["h"] == hb)
    stop_n = ncaab["comparators"]["stop_full_ev"]
    stop_b = nba["comparators"]["stop_full_ev"]
    oos_pos = n_oos["gross_ev_cents"] > 0 and b_oos["gross_ev_cents"] > 0
    miss_ok = (n_oos["p_miss"]["rate"] or 0) <= MISS_CEILING and (b_oos["p_miss"]["rate"] or 0) <= MISS_CEILING
    replicate = abs(hn - hb) <= 8
    reserved_beats_stop = ns["ev_per_reserved"] >= stop_n / 80 and bs["ev_per_reserved"] >= stop_b / 80
    contract_beats = ns["gross_ev_cents"] >= n40["gross_ev_cents"] - 0.5
    spike = n_flag == "THRESHOLD_OVERFIT_RISK" or b_flag == "THRESHOLD_OVERFIT_RISK"
    oos_collapse = n_oos["gross_ev_cents"] < 0 or b_oos["gross_ev_cents"] < 0
    if oos_collapse or (not replicate and abs(hn - hb) > 15):
        return "C", "H* is unstable across splits or sports, or OOS EV is negative."
    both_reserved_lose = (
        ns["ev_per_reserved"] < stop_n / 80 and bs["ev_per_reserved"] < stop_b / 80
    )
    if both_reserved_lose and ns["gross_ev_cents"] > stop_n:
        return "D", "Per-contract hedge EV beats 80/40 but reserved-capital efficiency loses on both sports."
    if oos_pos and miss_ok and replicate and not spike and reserved_beats_stop:
        return "A", "Stable region, OOS positive both sports, miss under ceiling, reserved capital viable."
    if oos_pos and miss_ok:
        return "B", "Candle economics survive VAL→OOS with near-100% loss recall; maker fills are unobserved and reserved-capital ranking vs 80/40 is not uniform across sports."
    if contract_beats:
        return "B", "Historical candle opportunity economics are usable; execution and/or capital remain unresolved."
    return "E", "No material robust improvement versus 80/40 after uncertainty and capital."


def write_dashboard_json(nba: dict, ncaab: dict) -> None:
    DASH_PUBLIC.mkdir(parents=True, exist_ok=True)
    slim = {
        "program": PROGRAM,
        "banner": "CANDLE PROXY — NOT MAKER FILL DATA",
        "live_execution_changed": False,
        "verdict": decide_verdict(nba, ncaab),
        "policy": {"nba": nba["policy"], "ncaab": ncaab["policy"]},
        "reproduction": {"nba": nba["reproduction"], "ncaab": ncaab["reproduction"]},
        "split_counts": {"nba": nba["split_counts"], "ncaab": ncaab["split_counts"]},
        "oos_eval": {"nba": nba["oos_eval"], "ncaab": ncaab["oos_eval"]},
        "comparators": {"nba": nba["comparators"], "ncaab": ncaab["comparators"]},
        "frontiers": {"nba": nba["frontiers"], "ncaab": ncaab["frontiers"]},
        "persist_surface": {"nba": nba["persist_surface"], "ncaab": ncaab["persist_surface"]},
        "desk": {"nba": nba["desk"], "ncaab": ncaab["desk"]},
        "bootstrap": {"nba": nba["bootstrap"], "ncaab": ncaab["bootstrap"]},
        "comparison": comparison_rows(nba, ncaab),
        "coarse_h": list(H_COARSE),
        "h_all": H_ALL,
    }
    (DASH_PUBLIC / "dashboard.json").write_text(json.dumps(slim) + "\n")
    combined = V1.SPORTS["ncaab"]["root"] / "derived/ncaab/first80_opponent_hedge_frontier_v2"
    (combined / "dashboard.json").write_text(json.dumps(slim) + "\n")


def main() -> int:
    nba = run_sport("nba")
    if nba.get("halted"):
        print("REPRODUCTION FAILED NBA — STOP", json.dumps(nba["reproduction"], indent=2))
        return 2
    ncaab = run_sport("ncaab")
    if ncaab.get("halted"):
        print("REPRODUCTION FAILED NCAAB — STOP", json.dumps(ncaab["reproduction"], indent=2))
        return 2
    write_report(nba, ncaab)
    write_dashboard_json(nba, ncaab)
    v, why = decide_verdict(nba, ncaab)
    print(
        json.dumps(
            {
                "program": PROGRAM,
                "verdict": v,
                "why": why,
                "nba_H_star": nba["policy"]["selected_h"],
                "ncaab_H_star": ncaab["policy"]["selected_h"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
