#!/usr/bin/env python3
"""FIRST80_OPPONENT_HEDGE_OPTIMAL_V4

Re-run the opponent-hedge candle book vs frozen 80→40, trade by trade.

Does not modify V1–V3, liquidation, Game Path, FIRST01, Risk, or live.
LIVE EXECUTION CHANGED: FALSE.
CANDLE PRICE_OPPORTUNITY ≠ ACTUAL MAKER FILL.

Constraint the prompt asked for — every trade's P&L ≥ 80→40 — is
impossible for any non-lookahead hedge: a false hedge turns +20 into
20−H. The only book that satisfies it is ORACLE (hedge iff the favorite
also printed close-40). That uses future information. It is an upper
bound, not a policy.

Executable books:
  REPLACE  hedge opportunity → lock 20−H, else hold +20/−80
  HYBRID   hedge opportunity → lock 20−H, else keep 80→40

Selection (a priori, VALIDATION only, OOS once):
  maximize HYBRID mean P&L
  subject to HYBRID EV > 80→40 EV
  tie-break: fewer trades with delta<0, then lower H
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path

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
V2 = _load("first80_frontier_v2_engine", HERE / "first80_opponent_hedge_frontier_v2.py")

PROGRAM = "FIRST80_OPPONENT_HEDGE_OPTIMAL_V4"
WIN, STOP, MISS, ENTRY = 20, -40, -80, 80
H_ALL = list(range(20, 61))
PERSIST_GRID = (0, 2, 5)
HELD_MAX_GRID = (None, 60, 55)
JUMP_GRID = (False, True)
SPLITS = ("TRAIN", "VALIDATION", "OOS", "FULL")
MIN_VAL_TRADES = 40
MIN_VAL_HEDGE_N = 30
DOCS = Path("/Users/user/Desktop/Momento/docs/research/FIRST80_OPPONENT_HEDGE_OPTIMAL_V4.md")


def out_dir(sport: str) -> Path:
    cfg = V1.SPORTS[sport]
    return cfg["root"] / "derived" / cfg["norm"] / "first80_opponent_hedge_optimal_v4"


def lock_pnl(h: int) -> int:
    return WIN - h


def stop_pnl(rec: dict) -> int:
    return V2.stop_pnl(rec)


def hold_pnl(rec: dict) -> int:
    return V2.hold_pnl(rec)


def touched(rec: dict, h: int, persist: int, no_jump: bool, held_max: int | None) -> bool:
    row = rec.get("hedge", {}).get("close", {}).get(h)
    if row is None:
        return False
    if int(row.get("persist_min") or 0) < persist:
        return False
    if no_jump and row.get("jump_10c"):
        return False
    if held_max is not None:
        hb = row.get("held_bid_e4")
        if hb is None or (hb / 100.0) > held_max:
            return False
    return True


def pnl_book(rec: dict, h: int, is_touch: bool, book: str) -> int:
    sp = stop_pnl(rec)
    if book == "replace":
        return lock_pnl(h) if is_touch else hold_pnl(rec)
    if book == "hybrid":
        return lock_pnl(h) if is_touch else sp
    if book == "oracle":
        # Hedge only overlapping close-40 stops. Weakly dominates 80→40.
        if is_touch and rec.get("stop_close_triggered"):
            return lock_pnl(h)
        return sp
    raise ValueError(book)


def classify_trade(rec: dict) -> str:
    if rec.get("stop_close_triggered"):
        return "STOP"
    if rec["expiration_result_yes"]:
        return "SURVIVOR"
    return "LEAK"


def summarize(trades: list[dict], h: int, persist: int, no_jump: bool, held_max, book: str) -> dict:
    n = len(trades)
    if n == 0:
        return {"n": 0, "h": h, "book": book}
    pnls = []
    stops = []
    holds = []
    n_touch = n_better = n_worse = n_equal = 0
    false_h = prot = 0
    by_cls = defaultdict(lambda: {"n": 0, "better": 0, "worse": 0, "equal": 0, "pnl": 0, "stop": 0})
    for rec in trades:
        is_t = touched(rec, h, persist, no_jump, held_max)
        p = pnl_book(rec, h, is_t, book)
        s = stop_pnl(rec)
        ho = hold_pnl(rec)
        pnls.append(p)
        stops.append(s)
        holds.append(ho)
        d = p - s
        used = is_t and rec.get("stop_close_triggered") if book == "oracle" else is_t
        if used:
            n_touch += 1
            if rec["expiration_result_yes"]:
                false_h += 1
            else:
                prot += 1
        if d > 0:
            n_better += 1
        elif d < 0:
            n_worse += 1
        else:
            n_equal += 1
        cls = classify_trade(rec)
        bucket = by_cls[cls]
        bucket["n"] += 1
        bucket["pnl"] += p
        bucket["stop"] += s
        if d > 0:
            bucket["better"] += 1
        elif d < 0:
            bucket["worse"] += 1
        else:
            bucket["equal"] += 1
    ev = sum(pnls) / n
    ev_s = sum(stops) / n
    ev_h = sum(holds) / n
    return {
        "h": h,
        "persist_min": persist,
        "no_jump": no_jump,
        "held_max": held_max,
        "book": book,
        "n": n,
        "hedge_opportunities": n_touch,
        "false_hedges": false_h,
        "protected_losses": prot,
        "ev_cents": round(ev, 4),
        "stop_ev_cents": round(ev_s, 4),
        "hold_ev_cents": round(ev_h, 4),
        "delta_vs_stop_cents": round(ev - ev_s, 4),
        "beats_stop": ev > ev_s,
        "n_better": n_better,
        "n_worse": n_worse,
        "n_equal": n_equal,
        "frac_worse": round(n_worse / n, 6),
        "lock_cents": lock_pnl(h),
        "path_classes": {k: dict(v) for k, v in by_cls.items()},
        "status": "CANDLE_PRICE_OPPORTUNITY",
        "fill_status": "NOT_ACTUAL_FILL",
        "lookahead": book == "oracle",
    }


def grid_keys():
    for h in H_ALL:
        for persist in PERSIST_GRID:
            for no_jump in JUMP_GRID:
                for held_max in HELD_MAX_GRID:
                    yield h, persist, no_jump, held_max


def select_hybrid(val: list[dict]) -> dict:
    """VALIDATION only. OOS must not enter this function's candidates."""
    eligible = []
    for row in val:
        if row["book"] != "hybrid":
            continue
        if row["n"] < MIN_VAL_TRADES:
            continue
        if row["hedge_opportunities"] < MIN_VAL_HEDGE_N:
            continue
        if not row["beats_stop"]:
            continue
        eligible.append(row)
    protocol = {
        "split": "VALIDATION only",
        "book": "HYBRID",
        "objective": "max EV s.t. EV > 80/40 EV",
        "tie_break": "min n_worse, then lower H",
        "oos": "evaluate once after freeze",
        "path": "close",
    }
    if not eligible:
        return {"selected": None, "reason": "NO_ELIGIBLE_POLICY", "protocol": protocol}
    eligible.sort(key=lambda r: (-r["ev_cents"], r["n_worse"], r["h"], r["persist_min"]))
    best = eligible[0]
    uncond = [
        r
        for r in eligible
        if r["persist_min"] == 0 and not r["no_jump"] and r["held_max"] is None
    ]
    uncond.sort(key=lambda r: (-r["ev_cents"], r["n_worse"], r["h"]))
    return {
        "selected": slim_policy(best),
        "unconditional_h_star": slim_policy(uncond[0]) if uncond else None,
        "eligible_n": len(eligible),
        "reason": "MAX_VAL_HYBRID_EV_BEATS_STOP",
        "protocol": protocol,
    }


def select_oracle(val: list[dict]) -> dict:
    rows = [
        r
        for r in val
        if r["book"] == "oracle"
        and r["persist_min"] == 0
        and not r["no_jump"]
        and r["held_max"] is None
        and r["n"] >= MIN_VAL_TRADES
        and r["beats_stop"]
    ]
    rows.sort(key=lambda r: (-r["ev_cents"], r["h"]))
    return {
        "selected": slim_policy(rows[0]) if rows else None,
        "note": "LOOKAHEAD. Uses stop_close_triggered. Not tradable.",
        "protocol": {
            "book": "ORACLE",
            "rule": "hedge iff opponent close≥H AND favorite close-40",
            "objective": "max VAL EV among weakly-dominating books",
        },
    }


def slim_policy(r: dict) -> dict:
    keys = (
        "h",
        "persist_min",
        "no_jump",
        "held_max",
        "book",
        "ev_cents",
        "stop_ev_cents",
        "delta_vs_stop_cents",
        "n_better",
        "n_worse",
        "n_equal",
        "hedge_opportunities",
        "false_hedges",
        "protected_losses",
        "lock_cents",
        "lookahead",
    )
    return {k: r[k] for k in keys}


def match_policy(rows: list[dict], sel: dict | None) -> dict | None:
    if not sel:
        return None
    for r in rows:
        if (
            r["h"] == sel["h"]
            and r["persist_min"] == sel["persist_min"]
            and r["no_jump"] == sel["no_jump"]
            and r["held_max"] == sel["held_max"]
            and r["book"] == sel["book"]
        ):
            return r
    return None


def trade_ledger(trades: list[dict], hybrid: dict, oracle: dict) -> list[dict]:
    out = []
    for rec in trades:
        h_h = hybrid["h"]
        h_o = oracle["h"]
        t_h = touched(rec, h_h, hybrid["persist_min"], hybrid["no_jump"], hybrid["held_max"])
        t_o = touched(rec, h_o, 0, False, None)
        sp = stop_pnl(rec)
        ho = hold_pnl(rec)
        p_hy = pnl_book(rec, h_h, t_h, "hybrid")
        p_rp = pnl_book(rec, h_h, t_h, "replace")
        p_or = pnl_book(rec, h_o, t_o, "oracle")
        p40 = pnl_book(rec, 40, touched(rec, 40, 0, False, None), "replace")
        out.append(
            {
                "sport": rec["sport"],
                "event_id": rec.get("event_id"),
                "ticker": rec.get("ticker"),
                "game_date": rec.get("game_date"),
                "dataset_split": rec.get("dataset_split"),
                "path_class": classify_trade(rec),
                "won": bool(rec["expiration_result_yes"]),
                "stop_close_triggered": bool(rec.get("stop_close_triggered")),
                "pnl_hold": ho,
                "pnl_stop_80_40": sp,
                "pnl_replace_h40": p40,
                "pnl_hybrid_selected": p_hy,
                "pnl_replace_selected": p_rp,
                "pnl_oracle_selected": p_or,
                "delta_hybrid_vs_stop": p_hy - sp,
                "delta_replace_h40_vs_stop": p40 - sp,
                "delta_oracle_vs_stop": p_or - sp,
                "hybrid_touched": t_h,
                "oracle_touched_and_stopped": bool(t_o and rec.get("stop_close_triggered")),
                "selected_hybrid_h": h_h,
                "selected_oracle_h": h_o,
                "label": "CANDLE_PROXY_NOT_FILL",
            }
        )
    return out


def _cell(v):
    if isinstance(v, dict):
        return json.dumps(v, default=str)
    return v


def write_parquet(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    keys = []
    seen = set()
    for r in rows:
        for k in r:
            if k not in seen:
                seen.add(k)
                keys.append(k)
    norm = [{k: _cell(r.get(k)) for k in keys} for r in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(norm), path)


def reproduce_v1(sport: str, trades: list[dict]) -> dict:
    r = V2.reproduce_v1(sport, trades)
    # Per-trade identity: REPLACE H=40 mean == V1 EV.
    pnls = [
        pnl_book(t, 40, touched(t, 40, 0, False, None), "replace") for t in trades
    ]
    ev = round(sum(pnls) / len(pnls), 4)
    r["per_trade_replace_h40_ev"] = ev
    r["per_trade_matches_v1"] = ev == r["observed"]["ev"]
    return r


def oracle_dominance_ok(trades: list[dict], h: int) -> bool:
    for rec in trades:
        t = touched(rec, h, 0, False, None)
        p = pnl_book(rec, h, t, "oracle")
        if p < stop_pnl(rec):
            return False
    return True


def run_sport(sport: str) -> dict:
    print(f"=== {sport} V4 ===", flush=True)
    cfg, trades, _games = V2.prepare_trades(sport)
    if len(trades) != V2.V1_GATES[sport]["n"]:
        return {"sport": sport, "stop": True, "reason": "universe mismatch", "n": len(trades)}
    V2.scan_all_H(cfg, trades)
    repro = reproduce_v1(sport, trades)
    print(f"  V1 reproduce {repro['observed']} ok={repro['ok']} per_trade={repro['per_trade_matches_v1']}", flush=True)
    if not repro["ok"] or not repro["per_trade_matches_v1"]:
        return {"sport": sport, "stop": True, "reproduction": repro}

    split_map = {s: V2.split_trades(trades, s) for s in SPLITS}
    grid_rows = []
    for split, subset in split_map.items():
        for h, persist, no_jump, held_max in grid_keys():
            for book in ("replace", "hybrid", "oracle"):
                if book == "oracle" and (persist != 0 or no_jump or held_max is not None):
                    continue
                row = summarize(subset, h, persist, no_jump, held_max, book)
                row["sport"] = sport
                row["dataset_split"] = split
                grid_rows.append(row)

    val_rows = [r for r in grid_rows if r["dataset_split"] == "VALIDATION"]
    hybrid_sel = select_hybrid(val_rows)
    oracle_sel = select_oracle(val_rows)
    print(
        f"  hybrid* {hybrid_sel.get('selected')} oracle* {oracle_sel.get('selected')}",
        flush=True,
    )
    if not hybrid_sel.get("selected") or not oracle_sel.get("selected"):
        return {
            "sport": sport,
            "stop": True,
            "reason": "no VAL policy beat 80/40",
            "hybrid": hybrid_sel,
            "oracle": oracle_sel,
        }

    h_star = hybrid_sel["selected"]
    o_star = oracle_sel["selected"]
    if not oracle_dominance_ok(trades, o_star["h"]):
        return {"sport": sport, "stop": True, "reason": "oracle failed pathwise check"}

    by_split = {}
    for split, subset in split_map.items():
        rows = [r for r in grid_rows if r["dataset_split"] == split]
        by_split[split] = {
            "hybrid": match_policy(rows, h_star),
            "oracle": match_policy(rows, o_star),
            "replace_h40": summarize(subset, 40, 0, False, None, "replace"),
            "hybrid_h40": summarize(subset, 40, 0, False, None, "hybrid"),
            "uncond": match_policy(rows, hybrid_sel.get("unconditional_h_star")),
            "n": len(subset),
        }

    ledger = trade_ledger(trades, h_star, o_star)
    n_or_worse = sum(1 for r in ledger if r["delta_oracle_vs_stop"] < 0)
    n_hy_worse = sum(1 for r in ledger if r["delta_hybrid_vs_stop"] < 0)
    payload = {
        "sport": sport,
        "reproduction": repro,
        "hybrid_selection": hybrid_sel,
        "oracle_selection": oracle_sel,
        "by_split": by_split,
        "grid": grid_rows,
        "ledger": ledger,
        "full_oracle_n_worse": n_or_worse,
        "full_hybrid_n_worse": n_hy_worse,
        "live_execution_changed": False,
    }
    write_sport(payload)
    return payload


def write_sport(payload: dict) -> None:
    sport = payload["sport"]
    d = out_dir(sport)
    d.mkdir(parents=True, exist_ok=True)
    write_parquet(d / "policy_grid.parquet", payload["grid"])
    write_parquet(d / "trade_ledger.parquet", payload["ledger"])
    slim = {
        "program": PROGRAM,
        "sport": sport,
        "live_execution_changed": False,
        "actual_fill": "UNOBSERVED",
        "reproduction": payload["reproduction"],
        "hybrid_selection": payload["hybrid_selection"],
        "oracle_selection": payload["oracle_selection"],
        "by_split": payload["by_split"],
        "full_oracle_n_worse": payload["full_oracle_n_worse"],
        "full_hybrid_n_worse": payload["full_hybrid_n_worse"],
    }
    (d / "summary.json").write_text(json.dumps(slim, indent=2, default=str) + "\n")
    (d / "reproduction_checks.json").write_text(
        json.dumps(payload["reproduction"], indent=2) + "\n"
    )
    (d / "metadata.json").write_text(
        json.dumps(
            {
                "program": PROGRAM,
                "sport": sport,
                "live_execution_changed": False,
                "lock": "20-H",
                "books": ["replace", "hybrid", "oracle"],
                "oracle": "LOOKAHEAD — hedge only if favorite close-40",
                "splits": "TRAIN<=2025-12-31; VAL through 2026-03-15; OOS after",
            },
            indent=2,
        )
        + "\n"
    )


def _ev(p: dict, split: str, book: str) -> str:
    row = p["by_split"][split][book]
    if row is None:
        return "n/a"
    return (
        f"{row['ev_cents']:+.2f}¢  (vs 80/40 {row['stop_ev_cents']:+.2f}, "
        f"Δ {row['delta_vs_stop_cents']:+.2f}; "
        f"better {row['n_better']} / worse {row['n_worse']} / equal {row['n_equal']})"
    )


def write_report(nba: dict, ncaab: dict) -> None:
    hb = nba["hybrid_selection"]["selected"]
    hn = ncaab["hybrid_selection"]["selected"]
    ob = nba["oracle_selection"]["selected"]
    on = ncaab["oracle_selection"]["selected"]
    oos_nba = nba["by_split"]["OOS"]["hybrid"]
    oos_ncaab = ncaab["by_split"]["OOS"]["hybrid"]
    oos_ok = bool(
        oos_nba
        and oos_ncaab
        and oos_nba["beats_stop"]
        and oos_ncaab["beats_stop"]
    )
    if nba["full_oracle_n_worse"] or ncaab["full_oracle_n_worse"]:
        verdict, why = "D", "Oracle book had a worse trade — identity failed."
    elif not oos_ok:
        verdict, why = (
            "C",
            "VALIDATION hybrid beat 80→40 but OOS hybrid did not on at least one sport.",
        )
    else:
        verdict, why = (
            "B",
            "HYBRID candle EV beats 80→40 on VAL and OOS, but some trades are worse "
            "(false hedges). ORACLE weakly dominates every trade and is lookahead. "
            "Fills remain unobserved.",
        )

    def pol(r):
        return (
            f"H={r['h']}, persist≥{r['persist_min']}, no_jump={r['no_jump']}, "
            f"held_max={r['held_max']}, lock={r['lock_cents']}¢"
        )

    lines = [
        "# FIRST80_OPPONENT_HEDGE_OPTIMAL_V4",
        "",
        "Research only. **LIVE EXECUTION CHANGED: FALSE.**",
        "",
        "```text",
        "CANDLE PRICE_OPPORTUNITY  ≠  ACTUAL MAKER FILL",
        "ORACLE BOOK              =  LOOKAHEAD (favorite close-40 already known)",
        "```",
        "",
        f"**Verdict: {verdict}** — {why}",
        "",
        "Does not modify V1–V3, FIRST01, Risk, or live execution.",
        "",
        "## What “each trade better” can and cannot mean",
        "",
        "For a single FIRST-80 trade, 80→40 Model A pays **+20** if the favorite",
        "never prints close-40 and wins, and **−40** if it does.",
        "",
        "A hedge fill at H locks **20−H** (H=40 → **−20**).",
        "",
        "| This trade’s 80→40 path | Hedge fills | Hedge vs 80→40 |",
        "|---|---|---|",
        "| Survivor (+20) | yes (false hedge) | **worse** by H¢ |",
        "| Survivor (+20) | no | equal |",
        "| Stop (−40) | yes | **better** by (20−H)−(−40) = 60−H |",
        "| Stop (−40) | no | equal if HYBRID; worse if REPLACE (falls to −80) |",
        "",
        "So **no resting-opponent rule that can fire on a survivor is better on every trade.**",
        "That is an identity, not a tuning failure.",
        "",
        "This test therefore reports two books:",
        "",
        "1. **HYBRID (executable candle proxy)** — rest opponent at H; if the",
        "   opportunity never prints, keep 80→40. Selected on VALIDATION to",
        "   maximize mean P&L subject to beating 80→40. Some trades are worse.",
        "2. **ORACLE (lookahead upper bound)** — take the hedge **only** on trades",
        "   that also printed favorite close-40. Then no trade is worse than",
        "   80→40. This uses future information. It is **not** a live rule.",
        "",
        "## Selection protocol (frozen before OOS)",
        "",
        "- Universes: frozen FIRST-80 (NBA 1,230 / NCAAB 4,099)",
        "- Path: opponent `yes_bid_close ≥ H` after entry (V1/V2 close proxy)",
        "- Grid: H=20..60, persist ∈ {0,2,5}, skip CLASS-E jump yes/no,",
        "  held favorite at touch ≤ {none, 60, 55}",
        "- TRAIN / VAL / OOS: same calendar cuts as V2",
        "- Choose HYBRID on **VALIDATION only**; score OOS once",
        "- Per-trade P&L is the unit. Mean EV is the mean of those P&Ls.",
        "",
        "## Reproduction",
        "",
        f"- NBA: {nba['reproduction']['observed']} per_trade={nba['reproduction']['per_trade_matches_v1']}",
        f"- NCAAB: {ncaab['reproduction']['observed']} per_trade={ncaab['reproduction']['per_trade_matches_v1']}",
        "",
        "## Selected HYBRID (executable proxy)",
        "",
        f"- NBA: `{pol(hb)}`",
        f"- NCAAB: `{pol(hn)}`",
        "",
        "VAL picked **persist ≥ 5 minutes** on both sports. That is a candle",
        "filter (opponent close stays ≥ H), not a fill. It raises mean EV by",
        "skipping many one-bar touches, including some real stops. Treat it as",
        "a VAL-fit gate, not a production parameter.",
        "",
        "| Split | NBA HYBRID vs 80→40 | NCAAB HYBRID vs 80→40 |",
        "|---|---|---|",
        f"| TRAIN | {_ev(nba, 'TRAIN', 'hybrid')} | {_ev(ncaab, 'TRAIN', 'hybrid')} |",
        f"| VAL | {_ev(nba, 'VALIDATION', 'hybrid')} | {_ev(ncaab, 'VALIDATION', 'hybrid')} |",
        f"| OOS | {_ev(nba, 'OOS', 'hybrid')} | {_ev(ncaab, 'OOS', 'hybrid')} |",
        f"| FULL | {_ev(nba, 'FULL', 'hybrid')} | {_ev(ncaab, 'FULL', 'hybrid')} |",
        "",
        f"FULL trades with HYBRID **worse** than 80→40: NBA **{nba['full_hybrid_n_worse']}**, "
        f"NCAAB **{ncaab['full_hybrid_n_worse']}** (false hedges).",
        "",
        "## H=40 REPLACE (V1 book) vs 80→40, per trade",
        "",
        "| Sport | REPLACE H=40 EV | 80→40 EV | Δ | worse trades |",
        "|---|---:|---:|---:|---:|",
        f"| NBA | {nba['by_split']['FULL']['replace_h40']['ev_cents']:+.2f} | "
        f"{nba['by_split']['FULL']['replace_h40']['stop_ev_cents']:+.2f} | "
        f"{nba['by_split']['FULL']['replace_h40']['delta_vs_stop_cents']:+.2f} | "
        f"{nba['by_split']['FULL']['replace_h40']['n_worse']} |",
        f"| NCAAB | {ncaab['by_split']['FULL']['replace_h40']['ev_cents']:+.2f} | "
        f"{ncaab['by_split']['FULL']['replace_h40']['stop_ev_cents']:+.2f} | "
        f"{ncaab['by_split']['FULL']['replace_h40']['delta_vs_stop_cents']:+.2f} | "
        f"{ncaab['by_split']['FULL']['replace_h40']['n_worse']} |",
        "",
        "Mean EV is higher. Individual false-hedge trades are not.",
        "",
        "## ORACLE (lookahead; every trade ≥ 80→40)",
        "",
        f"- NBA: `{pol(ob)}` — FULL n_worse={nba['full_oracle_n_worse']}",
        f"- NCAAB: `{pol(on)}` — FULL n_worse={ncaab['full_oracle_n_worse']}",
        "",
        "| Split | NBA ORACLE vs 80→40 | NCAAB ORACLE vs 80→40 |",
        "|---|---|---|",
        f"| TRAIN | {_ev(nba, 'TRAIN', 'oracle')} | {_ev(ncaab, 'TRAIN', 'oracle')} |",
        f"| VAL | {_ev(nba, 'VALIDATION', 'oracle')} | {_ev(ncaab, 'VALIDATION', 'oracle')} |",
        f"| OOS | {_ev(nba, 'OOS', 'oracle')} | {_ev(ncaab, 'OOS', 'oracle')} |",
        f"| FULL | {_ev(nba, 'FULL', 'oracle')} | {_ev(ncaab, 'FULL', 'oracle')} |",
        "",
        "Oracle EV is the value of a **perfect** “only hedge the stops” gate.",
        "Candles do not provide that gate at T+0, and a 40¢ bid still cannot rest",
        "while the opponent ask is ~20¢.",
        "",
        "## Unconditional H* (HYBRID, persist=0, no extra gate)",
        "",
        f"- NBA: {nba['hybrid_selection'].get('unconditional_h_star')}",
        f"- NCAAB: {ncaab['hybrid_selection'].get('unconditional_h_star')}",
        "",
        "## What this does not prove",
        "",
        "- Maker fills at H",
        "- That a post-only bid at H rests when opponent ask < H",
        "- Fees, two-market risk booking, live FIRST01",
        "",
        "Code: `apps/ncaab-data/scripts/first80_opponent_hedge_optimal_v4.py`",
        "Artifacts: `.../derived/{nba,ncaab}/first80_opponent_hedge_optimal_v4/`",
        "",
        "LIVE EXECUTION CHANGED: FALSE",
        "",
    ]
    text = "\n".join(lines)
    DOCS.write_text(text)
    for sport in ("nba", "ncaab"):
        dest = out_dir(sport) / "REPORT.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)


def main() -> int:
    nba = run_sport("nba")
    if nba.get("stop"):
        print("STOP NBA", json.dumps(nba, indent=2, default=str)[:4000])
        return 2
    ncaab = run_sport("ncaab")
    if ncaab.get("stop"):
        print("STOP NCAAB", json.dumps(ncaab, indent=2, default=str)[:4000])
        return 2
    write_report(nba, ncaab)
    print(
        json.dumps(
            {
                "program": PROGRAM,
                "nba_hybrid": nba["hybrid_selection"]["selected"],
                "ncaab_hybrid": ncaab["hybrid_selection"]["selected"],
                "nba_oracle": nba["oracle_selection"]["selected"],
                "ncaab_oracle": ncaab["oracle_selection"]["selected"],
                "nba_hybrid_n_worse": nba["full_hybrid_n_worse"],
                "ncaab_hybrid_n_worse": ncaab["full_hybrid_n_worse"],
                "live_execution_changed": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
