#!/usr/bin/env python3
"""FIRST80_HYBRID_CAUSAL_TIMELINE_AUDIT_V5

Strict T0→T3 audit of the V4 HYBRID persist≥5 rule.

Does not retune H. Does not modify V1–V4, FIRST01, Risk, or live.
LIVE EXECUTION CHANGED: FALSE.

V4 used full-path persist_min ≥ 5 to *select* a hedge, then locked 20−H
as if filled at H at first touch. That uses information after T1.

Causal rule (elapsed information only):

  T0  FIRST-80 candle (not a proven maker fill)
  T1  first later opponent yes_bid_close ≥ H
  T2  K subsequent qualifying bars still ≥ H  (K=5 for V4)
  T3  hedge decision = T2
  If favorite close-40 prints at or before T3, take 80→40 instead.

Lock at T3 is 20 − P_T2 (candle bid close), not 20−H.
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
V4 = _load("first80_optimal_v4_engine", HERE / "first80_opponent_hedge_optimal_v4.py")

PROGRAM = "FIRST80_HYBRID_CAUSAL_TIMELINE_AUDIT_V5"
WIN = 20
SPLITS = ("TRAIN", "VALIDATION", "OOS", "FULL")
DOCS = Path("/Users/user/Desktop/Momento/docs/research/FIRST80_HYBRID_CAUSAL_TIMELINE_AUDIT_V5.md")

# Frozen V4 HYBRID. Do not reselect on VAL/OOS.
V4_RULE = {
    "nba": {"h": 26, "k": 5, "v4_full_ev": 6.6878, "v4_stop_ev": 4.3902},
    "ncaab": {"h": 22, "k": 5, "v4_full_ev": 6.8261, "v4_stop_ev": 3.9034},
}
# Diagnostics only. Not new policy.
EXTRA = (("h40_k5", 40, 5), ("h40_k0", 40, 0))


def out_dir(sport: str) -> Path:
    cfg = V1.SPORTS[sport]
    return cfg["root"] / "derived" / cfg["norm"] / "first80_hybrid_causal_timeline_audit_v5"


def e4(h: int) -> int:
    return h * 100


def cents(e: int | None) -> int | None:
    if e is None:
        return None
    return e // 100


def lock_from(px_cents: int) -> int:
    return WIN - px_cents


def scan_with_quotes(cfg: dict, trades: list[dict]) -> None:
    """V2 scan plus raw qualifying opponent quotes for the T1→T2 walk."""
    V2.scan_all_H(cfg, trades)
    candles = cfg["root"] / "normalized" / cfg["norm"] / "candles_1m"
    opp_win: dict[str, tuple[int, int]] = {}
    by_opp: dict[str, list[int]] = defaultdict(list)
    for i, rec in enumerate(trades):
        rec["path_quotes"] = []
        if not rec.get("opponent_ticker"):
            continue
        ts0 = int(rec["first_80_timestamp"])
        end = rec.get("close_ts")
        ts1 = int(end) if end is not None else 2**31
        opp_win[rec["opponent_ticker"]] = (ts0, ts1)
        by_opp[rec["opponent_ticker"]].append(i)

    needed = set(opp_win)
    files = [p for p in candles.rglob("*.parquet") if p.stem in needed]
    print(f"  quote files {len(files)}", flush=True)
    opp_quotes: dict[str, list[tuple]] = defaultdict(list)
    cols = [
        "end_period_ts",
        "yes_bid_close_e4",
        "yes_ask_close_e4",
        "volume_hundredths",
        "is_valid",
    ]
    for n_file, path in enumerate(files, 1):
        if n_file % 500 == 0 or n_file == 1:
            print(f"  quotes {n_file}/{len(files)}", flush=True)
        table = pq.read_table(path, columns=cols)
        get = {c: table.column(c) for c in cols}
        ticker = path.stem
        win = opp_win.get(ticker)
        if win is None:
            continue
        ts0, ts1 = win
        had_q = False
        for i in range(table.num_rows):
            if not get["is_valid"][i].as_py():
                continue
            t = int(get["end_period_ts"][i].as_py())
            if t <= ts0 or t > ts1:
                continue
            bid_c = A._opt_int(get["yes_bid_close_e4"][i].as_py())
            ask_c = A._opt_int(get["yes_ask_close_e4"][i].as_py())
            vol = A._opt_int(get["volume_hundredths"][i].as_py())
            if not A.quality(bid_c, ask_c, vol, had_q):
                continue
            had_q = True
            opp_quotes[ticker].append((t, bid_c, ask_c))
    for opp, idxs in by_opp.items():
        quotes = sorted(opp_quotes.get(opp, []), key=lambda x: x[0])
        for i in idxs:
            trades[i]["path_quotes"] = quotes


def walk(rec: dict, h: int, k: int) -> dict:
    """Elapsed-only persist. k subsequent qualifying bars ≥ H after T1."""
    t0 = int(rec["first_80_timestamp"])
    fav40 = rec.get("first_40_close_ts")
    fav40_i = int(fav40) if fav40 is not None else None
    quotes = rec.get("path_quotes") or []
    thresh = e4(h)
    t1_idx = None
    for i, (t, bid, _ask) in enumerate(quotes):
        if bid is not None and bid >= thresh:
            t1_idx = i
            break
    base = {
        "h": h,
        "k": k,
        "t0": t0,
        "t1": None,
        "t2": None,
        "t3": None,
        "fav40": fav40_i,
        "persist_at_decision": 0,
        "t1_bid_cents": None,
        "t2_bid_cents": None,
        "t2_ask_cents": None,
        "wall_s_t1_t2": None,
        "bars_t1_t2": None,
        "t2_minus_h_cents": None,
        "decision": "NO_T1",
        "lookahead_free": True,
    }
    if t1_idx is None:
        return base
    t1, bid1, ask1 = quotes[t1_idx]
    base["t1"] = t1
    base["t1_bid_cents"] = cents(bid1)
    if fav40_i is not None and fav40_i <= t1:
        base["decision"] = "STOP_AT_OR_BEFORE_T1"
        return base
    if k <= 0:
        base["t2"] = t1
        base["t3"] = t1
        base["t2_bid_cents"] = cents(bid1)
        base["t2_ask_cents"] = cents(ask1)
        base["persist_at_decision"] = 0
        base["wall_s_t1_t2"] = 0
        base["bars_t1_t2"] = 0
        base["t2_minus_h_cents"] = (cents(bid1) or h) - h
        base["decision"] = "HEDGE_AT_T3"
        return base

    persist = 0
    for j in range(t1_idx + 1, len(quotes)):
        t, bid, ask = quotes[j]
        if fav40_i is not None and fav40_i <= t:
            base["decision"] = "STOP_DURING_WAIT"
            base["persist_at_decision"] = persist
            base["t3"] = fav40_i
            return base
        if bid is None:
            continue
        if bid >= thresh:
            persist += 1
            if persist >= k:
                base["t2"] = t
                base["t3"] = t
                base["t2_bid_cents"] = cents(bid)
                base["t2_ask_cents"] = cents(ask)
                base["persist_at_decision"] = persist
                base["wall_s_t1_t2"] = t - t1
                base["bars_t1_t2"] = persist
                base["t2_minus_h_cents"] = (cents(bid) or h) - h
                base["decision"] = "HEDGE_AT_T3"
                return base
        else:
            base["decision"] = "PERSIST_FAIL"
            base["persist_at_decision"] = persist
            base["t3"] = t
            return base
    base["decision"] = "END_BEFORE_K"
    base["persist_at_decision"] = persist
    return base


def pnl_causal(rec: dict, w: dict, price: str) -> int:
    sp = V2.stop_pnl(rec)
    if w["decision"] != "HEDGE_AT_T3":
        return sp
    if price == "H":
        px = w["h"]
    elif price == "T2_BID":
        px = w["t2_bid_cents"]
    elif price == "T2_ASK":
        px = w["t2_ask_cents"] if w["t2_ask_cents"] is not None else w["t2_bid_cents"]
    else:
        raise ValueError(price)
    if px is None:
        return sp
    return lock_from(int(px))


def v4_lookahead_touch(rec: dict, h: int, k: int) -> bool:
    return V4.touched(rec, h, k, False, None)


def summarize_book(trades: list[dict], walks: list[dict], book: str, h: int, k: int) -> dict:
    n = len(trades)
    pnls = []
    stops = []
    n_hedge = n_better = n_worse = n_equal = 0
    decisions = defaultdict(int)
    overshoot = []
    wall = []
    race = 0
    v4_yes_causal_no = 0
    for rec, w in zip(trades, walks):
        sp = V2.stop_pnl(rec)
        if book == "v4_lookahead":
            p = V4.pnl_book(rec, h, v4_lookahead_touch(rec, h, k), "hybrid")
            hedged = v4_lookahead_touch(rec, h, k)
        else:
            p = pnl_causal(rec, w, book)
            hedged = w["decision"] == "HEDGE_AT_T3"
        pnls.append(p)
        stops.append(sp)
        decisions[w["decision"]] += 1
        if hedged:
            n_hedge += 1
            if w.get("t2_minus_h_cents") is not None:
                overshoot.append(float(w["t2_minus_h_cents"]))
            if w.get("wall_s_t1_t2") is not None:
                wall.append(float(w["wall_s_t1_t2"]) / 60.0)
        if w["decision"] == "STOP_DURING_WAIT":
            race += 1
        if v4_lookahead_touch(rec, h, k) and w["decision"] != "HEDGE_AT_T3":
            v4_yes_causal_no += 1
        d = p - sp
        if d > 0:
            n_better += 1
        elif d < 0:
            n_worse += 1
        else:
            n_equal += 1
    ev = sum(pnls) / n if n else 0.0
    ev_s = sum(stops) / n if n else 0.0
    return {
        "book": book,
        "h": h,
        "k": k,
        "n": n,
        "ev_cents": round(ev, 4),
        "stop_ev_cents": round(ev_s, 4),
        "delta_vs_stop_cents": round(ev - ev_s, 4),
        "beats_stop": ev > ev_s,
        "n_hedge": n_hedge,
        "n_better": n_better,
        "n_worse": n_worse,
        "n_equal": n_equal,
        "decisions": dict(decisions),
        "n_stop_during_wait": race,
        "n_v4_hedge_but_causal_abort": v4_yes_causal_no,
        "t2_overshoot_vs_H_cents": dist(overshoot),
        "wait_t1_t2_min": dist(wall),
        "fill_status": "NOT_ACTUAL_FILL",
        "causal": book != "v4_lookahead",
    }


def dist(vals: list[float]) -> dict | None:
    if not vals:
        return None
    s = sorted(vals)
    n = len(s)
    return {
        "n": n,
        "mean": round(sum(s) / n, 4),
        "median": s[n // 2],
        "p90": s[min(n - 1, int(0.9 * (n - 1)))],
        "max": s[-1],
    }


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

    def cell(v):
        if isinstance(v, dict):
            return json.dumps(v, default=str)
        return v

    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist([{k: cell(r.get(k)) for k in keys} for r in rows]), path)


def run_sport(sport: str) -> dict:
    print(f"=== {sport} V5 causal timeline ===", flush=True)
    cfg, trades, _games = V2.prepare_trades(sport)
    gate = V4_RULE[sport]
    if len(trades) != V2.V1_GATES[sport]["n"]:
        return {"sport": sport, "stop": True, "reason": "universe mismatch"}
    scan_with_quotes(cfg, trades)
    h, k = gate["h"], gate["k"]
    v4_full = V4.summarize(trades, h, k, False, None, "hybrid")
    ok = (
        v4_full["ev_cents"] == gate["v4_full_ev"]
        and v4_full["stop_ev_cents"] == gate["v4_stop_ev"]
    )
    print(f"  V4 reproduce EV={v4_full['ev_cents']} ok={ok}", flush=True)
    if not ok:
        return {"sport": sport, "stop": True, "reproduction": v4_full, "expected": gate}

    rules = [("v4_hybrid", h, k)] + [(name, hh, kk) for name, hh, kk in EXTRA]
    ledgers = []
    books_by_split: dict[str, dict] = {}
    walks_primary = [walk(rec, h, k) for rec in trades]

    for rec, w in zip(trades, walks_primary):
        ledgers.append(
            {
                "sport": sport,
                "event_id": rec.get("event_id"),
                "ticker": rec.get("ticker"),
                "game_date": rec.get("game_date"),
                "dataset_split": rec.get("dataset_split"),
                "path_class": V4.classify_trade(rec),
                "pnl_stop": V2.stop_pnl(rec),
                "pnl_v4_lookahead": V4.pnl_book(rec, h, v4_lookahead_touch(rec, h, k), "hybrid"),
                "pnl_causal_H": pnl_causal(rec, w, "H"),
                "pnl_causal_T2_bid": pnl_causal(rec, w, "T2_BID"),
                "pnl_causal_T2_ask": pnl_causal(rec, w, "T2_ASK"),
                **{f"w_{kk}": w.get(kk) for kk in (
                    "decision", "t0", "t1", "t2", "t3", "fav40",
                    "t1_bid_cents", "t2_bid_cents", "t2_ask_cents",
                    "wall_s_t1_t2", "t2_minus_h_cents", "persist_at_decision",
                )},
                "v4_lookahead_hedge": v4_lookahead_touch(rec, h, k),
                "label": "CANDLE_PROXY_NOT_FILL",
            }
        )

    book_names = ("v4_lookahead", "H", "T2_BID", "T2_ASK")
    for split in SPLITS:
        subset = []
        sub_w = []
        for rec, w in zip(trades, walks_primary):
            if split == "FULL" or rec.get("dataset_split") == split:
                subset.append(rec)
                sub_w.append(w)
        books_by_split[split] = {
            b: summarize_book(subset, sub_w, b, h, k) for b in book_names
        }

    extra_full = {}
    extra_walks = {}
    for name, hh, kk in EXTRA:
        ww = [walk(rec, hh, kk) for rec in trades]
        extra_walks[name] = ww
        extra_full[name] = {
            b: summarize_book(trades, ww, b, hh, kk) for b in book_names
        }

    payload = {
        "sport": sport,
        "rule": gate,
        "reproduction": {"ok": True, "v4_full": v4_full},
        "by_split": books_by_split,
        "extra_full": extra_full,
        "ledger": ledgers,
        "live_execution_changed": False,
    }
    d = out_dir(sport)
    d.mkdir(parents=True, exist_ok=True)
    write_parquet(d / "trade_timeline.parquet", ledgers)
    write_parquet(
        d / "book_metrics.parquet",
        [
            {"dataset_split": split, **row}
            for split, books in books_by_split.items()
            for row in books.values()
        ],
    )
    slim = {k: v for k, v in payload.items() if k != "ledger"}
    (d / "summary.json").write_text(json.dumps(slim, indent=2, default=str) + "\n")
    (d / "metadata.json").write_text(
        json.dumps(
            {
                "program": PROGRAM,
                "sport": sport,
                "live_execution_changed": False,
                "v4_rule_frozen": True,
                "causal_lock": "20 - P_T2 (bid or ask candle close)",
                "v4_lock": "20 - H using full-path persist_min (lookahead)",
            },
            indent=2,
        )
        + "\n"
    )
    print(
        f"  causal T2_BID FULL {books_by_split['FULL']['T2_BID']['ev_cents']} "
        f"vs stop {books_by_split['FULL']['T2_BID']['stop_ev_cents']} "
        f"abort_vs_v4={books_by_split['FULL']['T2_BID']['n_v4_hedge_but_causal_abort']}",
        flush=True,
    )
    return payload


def _row(p: dict, split: str, book: str) -> str:
    r = p["by_split"][split][book]
    return (
        f"{r['ev_cents']:+.2f}¢ vs 80/40 {r['stop_ev_cents']:+.2f} "
        f"(Δ {r['delta_vs_stop_cents']:+.2f}; hedge {r['n_hedge']}; "
        f"worse {r['n_worse']})"
    )


def _diag(label: str, r: dict) -> str:
    return (
        f"- {label}: EV {r['ev_cents']:+.2f} Δ {r['delta_vs_stop_cents']:+.2f} "
        f"hedge {r['n_hedge']} worse {r['n_worse']} beats_stop={r['beats_stop']}"
    )


def write_report(nba: dict, ncaab: dict) -> None:
    def beats(p, book):
        return all(p["by_split"][s][book]["beats_stop"] for s in ("VALIDATION", "OOS", "FULL"))

    t2_ok = beats(nba, "T2_BID") and beats(ncaab, "T2_BID")
    t2_full_nba = nba["by_split"]["FULL"]["T2_BID"]
    t2_full_ncaab = ncaab["by_split"]["FULL"]["T2_BID"]
    v4_edge_gone = (not t2_full_nba["beats_stop"]) or (not t2_full_ncaab["beats_stop"])
    if v4_edge_gone:
        verdict, why = (
            "C",
            "After a causal T2 decision and lock at T2 bid, HYBRID no longer "
            "beats 80→40 on at least one sport FULL sample. V4’s persist≥5 "
            "mean was not a causal T3 result.",
        )
    elif t2_ok:
        verdict, why = (
            "B",
            "Causal wait-then-hedge still beats 80→40 on VAL/OOS/FULL at T2 bid, "
            "but fills remain unobserved and T2 price is not H.",
        )
    else:
        verdict, why = (
            "B",
            "Causal T2 bid beats 80→40 on FULL but not on every split. "
            "Fills unobserved. Do not promote.",
        )

    nb = nba["by_split"]["FULL"]
    nc = ncaab["by_split"]["FULL"]
    lines = [
        "# FIRST80_HYBRID_CAUSAL_TIMELINE_AUDIT_V5",
        "",
        "Research only. **LIVE EXECUTION CHANGED: FALSE.**",
        "",
        "```text",
        "CANDLE PRICE_OPPORTUNITY  ≠  ACTUAL MAKER FILL",
        "V4 persist≥5 + lock 20−H  =  LOOKAHEAD unless restated at T3",
        "```",
        "",
        f"**Verdict: {verdict}** — {why}",
        "",
        "Does not retune H. Does not change FIRST01, Risk, or live execution.",
        "",
        "## Question",
        "",
        "Is V4 HYBRID (`persist ≥ 5`, lock `20−H`) a **causal post-entry trigger**,",
        "or a full-path filter that peeks past the decision time?",
        "",
        "## Timeline (required)",
        "",
        "```text",
        "T0  FIRST-80 candle on favorite          (fill still unobserved)",
        "T1  opponent yes_bid_close first ≥ H",
        "T2  K subsequent qualifying bars still ≥ H",
        "T3  hedge decision  =  T2",
        "```",
        "",
        "Only bars with `t ≤ T3` may decide whether we hedge.",
        "If favorite `close-40` prints at or before T3, HYBRID takes **80→40**,",
        "not the hedge. That race is live-relevant and was invisible in V4.",
        "",
        "K counts **subsequent qualifying 1-minute bars**, the same object as",
        "V2 `persist_min`. That is not always 300 wall-clock seconds if bars",
        "are missing or fail the tradable-quality filter.",
        "",
        "## Three locks on the same T3 event",
        "",
        "| Book | When we hedge | Lock | Status |",
        "|---|---|---|---|",
        "| V4 lookahead | full-path persist≥K, ignore 40-race | 20−H | LOOKAHEAD |",
        "| Causal lock H | T3 reached, 40-race respected | 20−H | elapsed persist; optimistic price |",
        "| Causal T2 bid | T3 reached, 40-race respected | 20 − bid_close(T2) | elapsed persist + then-price |",
        "| Causal T2 ask | same | 20 − ask_close(T2) | worse if you take |",
        "",
        "Frozen rule: NBA **H=26 K=5**. NCAAB **H=22 K=5**. Not reselected.",
        "",
        "## Reproduction (V4 lookahead)",
        "",
        f"- NBA FULL {nb['v4_lookahead']['ev_cents']} vs expected {V4_RULE['nba']['v4_full_ev']}",
        f"- NCAAB FULL {nc['v4_lookahead']['ev_cents']} vs expected {V4_RULE['ncaab']['v4_full_ev']}",
        "",
        "## FULL sample — V4 selected HYBRID",
        "",
        "| Book | NBA EV | NBA vs 80→40 | NBA worse | NCAAB EV | NCAAB vs 80→40 | NCAAB worse |",
        "|---|---:|---:|---:|---:|---:|---:|",
        f"| V4 lookahead | {nb['v4_lookahead']['ev_cents']:+.2f} | {nb['v4_lookahead']['delta_vs_stop_cents']:+.2f} | {nb['v4_lookahead']['n_worse']} | {nc['v4_lookahead']['ev_cents']:+.2f} | {nc['v4_lookahead']['delta_vs_stop_cents']:+.2f} | {nc['v4_lookahead']['n_worse']} |",
        f"| Causal lock H | {nb['H']['ev_cents']:+.2f} | {nb['H']['delta_vs_stop_cents']:+.2f} | {nb['H']['n_worse']} | {nc['H']['ev_cents']:+.2f} | {nc['H']['delta_vs_stop_cents']:+.2f} | {nc['H']['n_worse']} |",
        f"| Causal T2 bid | {nb['T2_BID']['ev_cents']:+.2f} | {nb['T2_BID']['delta_vs_stop_cents']:+.2f} | {nb['T2_BID']['n_worse']} | {nc['T2_BID']['ev_cents']:+.2f} | {nc['T2_BID']['delta_vs_stop_cents']:+.2f} | {nc['T2_BID']['n_worse']} |",
        f"| Causal T2 ask | {nb['T2_ASK']['ev_cents']:+.2f} | {nb['T2_ASK']['delta_vs_stop_cents']:+.2f} | {nb['T2_ASK']['n_worse']} | {nc['T2_ASK']['ev_cents']:+.2f} | {nc['T2_ASK']['delta_vs_stop_cents']:+.2f} | {nc['T2_ASK']['n_worse']} |",
        "",
        "### What V4 was hiding",
        "",
        f"- NBA: V4 would hedge but causal aborts (mostly 40-race during wait): "
        f"**{nb['T2_BID']['n_v4_hedge_but_causal_abort']}**. "
        f"STOP_DURING_WAIT={nb['T2_BID']['n_stop_during_wait']}.",
        f"- NCAAB: **{nc['T2_BID']['n_v4_hedge_but_causal_abort']}** aborts. "
        f"STOP_DURING_WAIT={nc['T2_BID']['n_stop_during_wait']}.",
        "",
        f"- NBA T2 bid vs H overshoot (hedged only): {nb['T2_BID']['t2_overshoot_vs_H_cents']}",
        f"- NCAAB T2 bid vs H overshoot: {nc['T2_BID']['t2_overshoot_vs_H_cents']}",
        f"- NBA wait T1→T2 minutes: {nb['T2_BID']['wait_t1_t2_min']}",
        f"- NCAAB wait T1→T2 minutes: {nc['T2_BID']['wait_t1_t2_min']}",
        "",
        "## Splits (causal T2 bid — the honest HYBRID trigger)",
        "",
        "| Split | NBA | NCAAB |",
        "|---|---|---|",
        f"| TRAIN | {_row(nba, 'TRAIN', 'T2_BID')} | {_row(ncaab, 'TRAIN', 'T2_BID')} |",
        f"| VAL | {_row(nba, 'VALIDATION', 'T2_BID')} | {_row(ncaab, 'VALIDATION', 'T2_BID')} |",
        f"| OOS | {_row(nba, 'OOS', 'T2_BID')} | {_row(ncaab, 'OOS', 'T2_BID')} |",
        f"| FULL | {_row(nba, 'FULL', 'T2_BID')} | {_row(ncaab, 'FULL', 'T2_BID')} |",
        "",
        "## Decisions (FULL, V4 H/K)",
        "",
        f"- NBA: {nb['T2_BID']['decisions']}",
        f"- NCAAB: {nc['T2_BID']['decisions']}",
        "",
        "## Diagnostics (not selected)",
        "",
        _diag("NBA H=40 K=5", nba["extra_full"]["h40_k5"]["T2_BID"]),
        _diag("NCAAB H=40 K=5", ncaab["extra_full"]["h40_k5"]["T2_BID"]),
        _diag("NBA H=40 K=0", nba["extra_full"]["h40_k0"]["T2_BID"]),
        _diag("NCAAB H=40 K=0", ncaab["extra_full"]["h40_k0"]["T2_BID"]),
        "",
        "## What this does not prove",
        "",
        "- 80¢ maker fill at T0",
        "- Maker fill at H or at T2",
        "- That a post-only bid rests while opponent ask < H",
        "- Live/paper resting-order telemetry",
        "",
        "Next object, if this causal book still has a portfolio edge: **paper",
        "resting-order telemetry**, not another H search.",
        "",
        "Code: `apps/ncaab-data/scripts/first80_hybrid_causal_timeline_audit_v5.py`",
        "Artifacts: `.../derived/{nba,ncaab}/first80_hybrid_causal_timeline_audit_v5/`",
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
        print("STOP NBA", json.dumps(nba, indent=2, default=str)[:3000])
        return 2
    ncaab = run_sport("ncaab")
    if ncaab.get("stop"):
        print("STOP NCAAB", json.dumps(ncaab, indent=2, default=str)[:3000])
        return 2
    write_report(nba, ncaab)
    print(
        json.dumps(
            {
                "program": PROGRAM,
                "nba_full": nba["by_split"]["FULL"],
                "ncaab_full": ncaab["by_split"]["FULL"],
                "live_execution_changed": False,
            },
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
