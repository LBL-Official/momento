#!/usr/bin/env python3
"""Research-only dynamic policies, early-warning, portfolio, ruin stress.

SIMULATED exits use the next completed candle yes_bid_close. Not fills.
"""

from __future__ import annotations

import math
import pickle
import sys
from collections import defaultdict

import numpy as np
import pyarrow.parquet as pq

from common import (
    HAZARD_THRESHOLDS,
    OUT,
    PERSIST_N,
    Q_UNCONDITIONAL,
    SEED,
    e4_to_cents,
    ev_from_q,
    read_parquet_rows,
    utc_now,
    write_json,
)

ENTRY_CENTS = 80.0
R_CENTS = 20.0
PORTFOLIO = {
    "starting_bankroll": 10000.0,
    "position_fraction": 0.02,
    "constant_nominal": 200.0,
    "max_concurrent": 5,
    "fee_assumption": "UNVERIFIED_ASSUMPTION_ZERO_FEES",
    "label": "RESEARCH_ASSUMPTIONS_NOT_LIVE_ALLOCATION",
}
SURVIVAL_STRESS = [0.74, 0.725, 0.70, 0.68, 0.67, 0.66]


def r_hold(y40: int) -> float:
    return -2.0 if y40 else 1.0


def r_early(exit_cents: float | None) -> float | None:
    if exit_cents is None:
        return None
    return (exit_cents - ENTRY_CENTS) / R_CENTS


def next_bid(quotes, ticker, ts):
    series = quotes.get(ticker) or []
    for q in series:
        if q["ts"] > ts and q["bid_c"] is not None:
            return q["ts"], e4_to_cents(q["bid_c"])
    return None, None


def lead_bucket(minutes):
    if minutes is None:
        return None
    if minutes <= 2:
        return "0-2"
    if minutes <= 5:
        return "3-5"
    if minutes <= 10:
        return "6-10"
    if minutes <= 20:
        return "11-20"
    return "20+"


def walk_trade(states, thresh, persist, quotes, ticker, y40, barrier_ts, policy):
    """Return dict with exit kind, r_mult, warning metadata. SIMULATED."""
    streak = 0
    warn_i = None
    for i, s in enumerate(states):
        p = s["p"]
        if p is not None and p >= thresh:
            streak += 1
        else:
            streak = 0
        if streak >= persist:
            warn_i = i
            break
    if policy == 0 or warn_i is None:
        return {
            "exit_kind": "HOLD",
            "r": r_hold(y40),
            "warned": False,
            "warning_ts": None,
            "warning_p": None,
            "warning_bid_cents": None,
            "exit_ts": None,
            "exit_bid_cents": None,
            "lead_minutes": None,
            "price_kind": "OBSERVED_HOLD",
        }
    w = states[warn_i]
    xts, xc = next_bid(quotes, ticker, int(w["ts"]))
    lead = None
    if y40 and barrier_ts is not None:
        lead = (int(barrier_ts) - int(w["ts"])) / 60.0
    if policy in (1, 2):
        rr = r_early(xc)
        if rr is None:
            return {
                "exit_kind": "HOLD_UNOBSERVABLE_EXIT",
                "r": r_hold(y40),
                "warned": True,
                "warning_ts": int(w["ts"]),
                "warning_p": w["p"],
                "warning_bid_cents": e4_to_cents(w["bid_e4"]) if w.get("bid_e4") and np.isfinite(w["bid_e4"]) else None,
                "exit_ts": None,
                "exit_bid_cents": None,
                "lead_minutes": lead,
                "price_kind": "UNOBSERVABLE",
            }
        return {
            "exit_kind": "SIMULATED_EARLY_EXIT",
            "r": rr,
            "warned": True,
            "warning_ts": int(w["ts"]),
            "warning_p": w["p"],
            "warning_bid_cents": e4_to_cents(w["bid_e4"]) if w.get("bid_e4") and np.isfinite(w["bid_e4"]) else None,
            "exit_ts": xts,
            "exit_bid_cents": xc,
            "lead_minutes": lead,
            "price_kind": "SIMULATED_NEXT_CANDLE_YES_BID_CLOSE",
        }
    # policy 3: half off at warning, half hold
    rr = r_early(xc)
    if rr is None:
        return {
            "exit_kind": "HOLD_UNOBSERVABLE_EXIT",
            "r": r_hold(y40),
            "warned": True,
            "warning_ts": int(w["ts"]),
            "warning_p": w["p"],
            "lead_minutes": lead,
            "price_kind": "UNOBSERVABLE",
        }
    return {
        "exit_kind": "SIMULATED_HALF_REDUCE",
        "r": 0.5 * rr + 0.5 * r_hold(y40),
        "warned": True,
        "warning_ts": int(w["ts"]),
        "warning_p": w["p"],
        "warning_bid_cents": e4_to_cents(w["bid_e4"]) if w.get("bid_e4") and np.isfinite(w["bid_e4"]) else None,
        "exit_ts": xts,
        "exit_bid_cents": xc,
        "lead_minutes": lead,
        "price_kind": "SIMULATED_NEXT_CANDLE_YES_BID_CLOSE",
    }


def summarize(results):
    rs = [r["r"] for r in results if r["r"] is not None]
    n = len(rs)
    mean_r = float(np.mean(rs)) if rs else None
    warned = [r for r in results if r["warned"]]
    tp = [r for r in warned if r.get("y40")]
    fp = [r for r in warned if not r.get("y40")]
    barriers = [r for r in results if r.get("y40")]
    leads = [r["lead_minutes"] for r in tp if r.get("lead_minutes") is not None]
    buckets = defaultdict(int)
    for x in leads:
        buckets[lead_bucket(x)] += 1
    return {
        "n": n,
        "mean_R": mean_r,
        "ev_vs_hold_unit": mean_r,
        "n_warned": len(warned),
        "true_barrier_warnings": len(tp),
        "false_warnings": len(fp),
        "precision": None if not warned else len(tp) / len(warned),
        "recall": None if not barriers else len(tp) / len(barriers),
        "mean_lead_minutes": None if not leads else float(np.mean(leads)),
        "lead_buckets": dict(buckets),
        "mean_warning_price_cents": (
            None
            if not warned
            else float(
                np.nanmean(
                    [r["warning_bid_cents"] for r in warned if r.get("warning_bid_cents") is not None]
                )
            )
        ),
        "false_exit_mean_R": None if not fp else float(np.mean([r["r"] for r in fp])),
        "true_exit_mean_R": None if not tp else float(np.mean([r["r"] for r in tp])),
        "hold_mean_R_on_same": float(np.mean([r_hold(int(r["y40"])) for r in results])),
    }


def apply_policy(trades, by_tid, quotes, thresh, persist, policy, split=None):
    out = []
    for tr in trades:
        if split and tr["dataset_split"] != split:
            continue
        tid = tr["trade_id"]
        states = by_tid.get(tid) or []
        y40 = int(tr["Y_40_CLOSE"])
        rec = walk_trade(
            states,
            thresh,
            persist,
            quotes,
            tr["ticker"],
            y40,
            tr.get("first_40_close_ts"),
            policy,
        )
        rec["trade_id"] = tid
        rec["y40"] = y40
        rec["game_date"] = tr["game_date"]
        rec["entry_ts"] = tr["entry_decision_time"]
        rec["split"] = tr["dataset_split"]
        rec["close_ts"] = tr.get("close_ts")
        rec["barrier_ts"] = tr.get("first_40_close_ts")
        out.append(rec)
    return out


def max_dd(equity_curve):
    peak = equity_curve[0] if equity_curve else 0
    m = 0.0
    for x in equity_curve:
        peak = max(peak, x)
        if peak > 0:
            m = max(m, (peak - x) / peak)
    return m


def chrono_portfolio(results, trades_by_id, mode="fractional"):
    start = PORTFOLIO["starting_bankroll"]
    frac = PORTFOLIO["position_fraction"]
    nominal = PORTFOLIO["constant_nominal"]
    max_c = PORTFOLIO["max_concurrent"]
    items = sorted(results, key=lambda r: (r.get("entry_ts") or 0, r["trade_id"]))
    equity = start
    peak = start
    curve = [start]
    open_pos = []  # (exit_ts, reserved)
    daily = defaultdict(float)
    worst_day = 0.0
    concurrent_peak = 0
    for rec in items:
        et = rec["entry_ts"]
        open_pos = [p for p in open_pos if p[0] is None or p[0] > et]
        concurrent_peak = max(concurrent_peak, len(open_pos))
        if len(open_pos) >= max_c or equity <= 0:
            curve.append(equity)
            continue
        if mode == "fixed":
            stake = min(nominal, equity)
        elif mode == "capped_frac":
            stake = min(equity * frac, start * frac)
        else:
            stake = equity * frac
        if stake <= 0:
            curve.append(equity)
            continue
        pnl = stake * rec["r"]
        equity = equity + pnl
        peak = max(peak, equity)
        curve.append(equity)
        daily[rec.get("game_date")] += pnl
        xt = rec.get("exit_ts")
        if rec["exit_kind"] == "HOLD":
            xt = rec.get("barrier_ts") if rec["y40"] else rec.get("close_ts")
        open_pos.append((xt, stake))
    days = list(daily.values())
    if days:
        worst_day = float(min(days))
    xs = np.array(days, dtype=float) if days else np.array([0.0])
    sharpe = None
    if len(xs) >= 2 and xs.std(ddof=1) > 0:
        sharpe = float(xs.mean() / xs.std(ddof=1) * math.sqrt(365))
    sortino = None
    neg = xs[xs < 0]
    if len(xs) >= 2 and len(neg):
        ds = float(np.sqrt(np.mean(neg**2)))
        if ds > 0:
            sortino = float(xs.mean() / ds * math.sqrt(365))
    wins = sum(1 for r in items if r["r"] > 0)
    losses = sum(1 for r in items if r["r"] < 0)
    gp = sum(r["r"] for r in items if r["r"] > 0)
    gl = -sum(r["r"] for r in items if r["r"] < 0)
    return {
        "mode": mode,
        "terminal": equity,
        "max_dd": max_dd(curve),
        "sharpe_daily_ann": sharpe,
        "sortino_daily_ann": sortino,
        "sharpe_reliability": "LOW_SHORT_SAMPLE",
        "worst_day": worst_day,
        "profit_factor": None if gl <= 0 else gp / gl,
        "n_taken": len(items),
        "concurrent_peak": concurrent_peak,
        "calmar_proxy": None if max_dd(curve) <= 0 else ((equity / start) - 1) / max_dd(curve),
        "assumptions": PORTFOLIO,
    }


def block_bootstrap(results, n_mc=400):
    rng = np.random.default_rng(SEED)
    by_week = defaultdict(list)
    for r in results:
        wk = (r.get("game_date") or "")[:8]  # YYYY-WW-ish: use YYYY-MM as block
        by_week[wk].append(r["r"])
    blocks = [np.array(v, dtype=float) for v in by_week.values() if v]
    if not blocks:
        return {}
    start = PORTFOLIO["starting_bankroll"]
    frac = PORTFOLIO["position_fraction"]
    terminals = []
    dds = []
    for _ in range(n_mc):
        equity = start
        peak = start
        mdd = 0.0
        idx = rng.integers(0, len(blocks), size=len(blocks))
        for j in idx:
            for rr in blocks[j]:
                stake = equity * frac
                equity = equity + stake * rr
                peak = max(peak, equity)
                if peak > 0:
                    mdd = max(mdd, (peak - equity) / peak)
                if equity <= 0:
                    break
        terminals.append(equity)
        dds.append(mdd)
    terminals = np.array(terminals)
    dds = np.array(dds)
    return {
        "n_mc": n_mc,
        "block": "calendar_month",
        "median_terminal": float(np.median(terminals)),
        "p5_terminal": float(np.quantile(terminals, 0.05)),
        "p_dd_10": float(np.mean(dds >= 0.10)),
        "p_dd_20": float(np.mean(dds >= 0.20)),
        "p_dd_30": float(np.mean(dds >= 0.30)),
        "p_ruin": float(np.mean(np.array(terminals) <= 0.05 * start)),
        "median_max_dd": float(np.median(dds)),
    }


def ruin_stress(n_trades, n_mc=400):
    rng = np.random.default_rng(SEED)
    start = PORTFOLIO["starting_bankroll"]
    frac = PORTFOLIO["position_fraction"]
    out = {}
    for surv in SURVIVAL_STRESS:
        q = 1.0 - surv
        terms = []
        dds = []
        ruins = 0
        for _ in range(n_mc):
            equity = start
            peak = start
            mdd = 0.0
            for _t in range(n_trades):
                y40 = int(rng.random() < q)
                rr = r_hold(y40)
                equity = equity + equity * frac * rr
                peak = max(peak, equity)
                if peak > 0:
                    mdd = max(mdd, (peak - equity) / peak)
                if equity <= 1:
                    ruins += 1
                    break
            terms.append(equity)
            dds.append(mdd)
        terms = np.array(terms)
        dds = np.array(dds)
        out[str(surv)] = {
            "assumed_survival": surv,
            "assumed_q": q,
            "median_terminal": float(np.median(terms)),
            "p5_terminal": float(np.quantile(terms, 0.05)),
            "p_dd_10": float(np.mean(dds >= 0.10)),
            "p_dd_20": float(np.mean(dds >= 0.20)),
            "p_dd_30": float(np.mean(dds >= 0.30)),
            "p_ruin": ruins / n_mc,
            "note": "IID Bernoulli stress; not a forecast. Trades are not IID in live.",
        }
    return out


def main() -> int:
    trades = read_parquet_rows(OUT / "first80_trades.parquet")
    pred = pq.read_table(OUT / "predictions.parquet")
    panel = pq.read_table(OUT / "features_panel.parquet")
    quotes = pickle.loads((OUT / "_quotes_cache.pkl").read_bytes())
    # join p_selected onto states
    pmap = {}
    tids = pred.column("trade_id").to_pylist()
    sts = pred.column("state_timestamp").to_pylist()
    ps = pred.column("p_selected").to_pylist()
    for a, b, c in zip(tids, sts, ps):
        pmap[(a, int(b))] = c
    ptids = panel.column("trade_id").to_pylist()
    psts = panel.column("state_timestamp").to_pylist()
    bid = panel.column("yes_bid_close_e4").to_pylist() if "yes_bid_close_e4" in panel.column_names else [None] * panel.num_rows
    by_tid = defaultdict(list)
    for tid, ts, b in zip(ptids, psts, bid):
        ts = int(ts)
        by_tid[tid].append({"ts": ts, "p": pmap.get((tid, ts)), "bid_e4": b})
    for tid in by_tid:
        by_tid[tid].sort(key=lambda x: x["ts"])

    hold_val = apply_policy(trades, by_tid, quotes, 9.0, 99, 0, split="VALIDATION")
    hold_oos = apply_policy(trades, by_tid, quotes, 9.0, 99, 0, split="OOS")
    hold_all = apply_policy(trades, by_tid, quotes, 9.0, 99, 0)

    grid = []
    best = None
    for policy in (1, 2, 3):
        for thresh in HAZARD_THRESHOLDS:
            for persist in PERSIST_N:
                if policy == 1 and persist != 1:
                    continue
                recs = apply_policy(trades, by_tid, quotes, thresh, persist, policy, split="VALIDATION")
                sm = summarize(recs)
                sm.update({"policy": policy, "thresh": thresh, "persist": persist})
                grid.append(sm)
                key = (sm["mean_R"] if sm["mean_R"] is not None else -9e9, -(sm.get("n_warned") or 0))
                if best is None or key > best[0]:
                    best = (key, sm)

    frozen = best[1] if best else {"policy": 0, "thresh": 9.0, "persist": 99}
    # Freeze even if worse than hold — VAL selection is explicit; OOS may reject.
    oos_pol = apply_policy(
        trades,
        by_tid,
        quotes,
        frozen["thresh"],
        frozen["persist"],
        frozen["policy"],
        split="OOS",
    )
    val_pol = apply_policy(
        trades,
        by_tid,
        quotes,
        frozen["thresh"],
        frozen["persist"],
        frozen["policy"],
        split="VALIDATION",
    )
    all_pol = apply_policy(
        trades, by_tid, quotes, frozen["thresh"], frozen["persist"], frozen["policy"]
    )

    val_hold_s = summarize(hold_val)
    oos_hold_s = summarize(hold_oos)
    val_pol_s = summarize(val_pol)
    oos_pol_s = summarize(oos_pol)

    port_hold = {
        "fixed": chrono_portfolio(hold_all, {}, "fixed"),
        "fractional": chrono_portfolio(hold_all, {}, "fractional"),
        "capped_frac": chrono_portfolio(hold_all, {}, "capped_frac"),
    }
    port_pol = {
        "fixed": chrono_portfolio(all_pol, {}, "fixed"),
        "fractional": chrono_portfolio(all_pol, {}, "fractional"),
        "capped_frac": chrono_portfolio(all_pol, {}, "capped_frac"),
    }

    write_json(
        OUT / "portfolio_simulation.json",
        {
            "written_utc": utc_now(),
            "research_only": True,
            "not_fills": True,
            "exit_quote": "SIMULATED next completed candle yes_bid_close",
            "same_bar_limitation": "SAME_BAR_1M_LIMITATION",
            "hold_ev_formula": "1-3q on terminal 80/40, not on simulated early exits",
            "frozen_policy": {
                "policy": frozen["policy"],
                "thresh": frozen["thresh"],
                "persist": frozen["persist"],
                "selected_on": "VALIDATION mean_R",
            },
            "grid_validation": grid,
            "validation": {"hold": val_hold_s, "policy": val_pol_s},
            "oos": {"hold": oos_hold_s, "policy": oos_pol_s},
            "early_warning_oos": {
                "lead_buckets": oos_pol_s.get("lead_buckets"),
                "mean_lead_minutes": oos_pol_s.get("mean_lead_minutes"),
                "precision": oos_pol_s.get("precision"),
                "recall": oos_pol_s.get("recall"),
                "false_exit_mean_R": oos_pol_s.get("false_exit_mean_R"),
            },
            "portfolio_hold": port_hold,
            "portfolio_policy": port_pol,
            "block_bootstrap_hold": block_bootstrap(hold_all),
            "block_bootstrap_policy": block_bootstrap(all_pol),
            "ruin_stress_iid": ruin_stress(len(trades)),
            "unconditional_q": Q_UNCONDITIONAL,
            "unconditional_ev": ev_from_q(Q_UNCONDITIONAL),
        },
    )
    print(
        f"policy freeze P{frozen['policy']} t={frozen['thresh']} N={frozen['persist']} "
        f"VAL mean_R={val_pol_s['mean_R']} OOS mean_R={oos_pol_s['mean_R']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
