#!/usr/bin/env python3
"""NCAAB FIRST-80, first-exit 90¢ or stop — no hold to expiration.

Research only. Same FIRST-80 entry as the NBA/NCAAB close-path audit.
Exit is whichever barrier prints first: yes_bid_close >= 90 or <= stop.
Default stop is 50¢ (`--stop 50`). Paths that never print either barrier
are NOT assigned settlement P&L.

Does not change live FIRST01. Does not invent L2 or fills.
Same-minute 90-and-stop on wicks is AMBIGUOUS (intra-minute order unknown).
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
NBA_SCRIPTS = Path("/Users/user/Desktop/Momento/apps/nba-data/scripts")
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(NBA_SCRIPTS))
import nba_80_40_execution_audit as A  # noqa: E402
import ncaab_80_40_execution_audit as N  # noqa: E402

ROOT = N.ROOT
NORM = N.NORM


def _stop_cents_from_argv(default: int = 50) -> int:
    if "--stop" in sys.argv:
        i = sys.argv.index("--stop")
        if i + 1 < len(sys.argv):
            return int(sys.argv[i + 1])
    return default


STOP_CENTS = _stop_cents_from_argv(50)
HIT90 = 9000
HIT_STOP = STOP_CENTS * 100  # cents → E4
WIN_CENTS = 10  # 80 → 90
LOSS_CENTS = 80 - STOP_CENTS  # 80 → stop
OUT = ROOT / "derived" / "ncaab" / f"first80_90_{STOP_CENTS}_exit_audit"
# +1R remains the 80→100 unit (20¢).
R_CENTS = A.R_CENTS
BE_P = LOSS_CENTS / (WIN_CENTS + LOSS_CENTS)
OUTCOME_STOP = f"EXIT_{STOP_CENTS}"


def wilson(k: int, n: int, z: float = 1.96):
    if n <= 0:
        return None, None, None
    p = k / n
    z2 = z * z
    den = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / den
    rad = z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n) / den
    return round(p * 100, 4), round(max(0.0, center - rad) * 100, 4), round(
        min(1.0, center + rad) * 100, 4
    )


def ev_cents(p: float) -> float:
    return p * WIN_CENTS - (1.0 - p) * LOSS_CENTS


def ev_R(p: float) -> float:
    return ev_cents(p) / R_CENTS


def first_close_barrier(rows: list[dict], f80: dict) -> dict:
    """First tradable bid_close >= 90 or <= stop, including the entry bar."""
    out = {"exit_90": None, "exit_40": None, "tie": False}
    seq = [f80] + [q for q in rows if q["ts"] > f80["ts"]]
    had_q = True
    for q in seq:
        if q is not f80 and not A.quality(q["bid_c"], q["ask_c"], q["vol"], had_q):
            continue
        had_q = True
        hit90 = q["bid_c"] is not None and q["bid_c"] >= HIT90
        hit40 = q["bid_c"] is not None and q["bid_c"] <= HIT_STOP
        if hit90 and hit40:
            out["tie"] = True
            out["exit_90"] = q
            out["exit_40"] = q
            return out
        if hit90:
            out["exit_90"] = q
            return out
        if hit40:
            out["exit_40"] = q
            return out
    return out


def first_wick_barrier(rows: list[dict], f80: dict) -> dict:
    """First bid_high >= 90 or bid_low <= stop. Same-bar both sides = tie."""
    out = {"exit_90": None, "exit_40": None, "tie": False}
    seq = [f80] + [q for q in rows if q["ts"] > f80["ts"]]
    for q in seq:
        hit90 = q["bid_h"] is not None and q["bid_h"] >= HIT90
        hit40 = q["bid_l"] is not None and q["bid_l"] <= HIT_STOP
        if hit90 and hit40:
            out["tie"] = True
            out["exit_90"] = q
            out["exit_40"] = q
            return out
        if hit90:
            out["exit_90"] = q
            return out
        if hit40:
            out["exit_40"] = q
            return out
    return out


def classify(bar: dict) -> str:
    if bar["tie"]:
        return "TIE_SAME_MINUTE"
    if bar["exit_90"] is not None:
        return "EXIT_90"
    if bar["exit_40"] is not None:
        return OUTCOME_STOP
    return "NO_BARRIER"


def pnl_cents(outcome: str) -> int | None:
    if outcome == "EXIT_90":
        return WIN_CENTS
    if outcome == OUTCOME_STOP:
        return -LOSS_CENTS
    return None


def scan(markets, games):
    games_by_event = {g["event_id"]: g for g in games}
    meta = {}
    for m in markets:
        g = games_by_event.get(m["event_id"], {})
        start = g.get("game_window_start")
        end = m["close_ts"]
        gw_end = g.get("game_window_end")
        if end is None:
            end = gw_end
        elif gw_end is not None:
            end = min(end, gw_end)
        meta[m["ticker"]] = (start, end)

    files = sorted((NORM / "candles_1m").rglob("*.parquet"))
    cols = [
        "ticker",
        "end_period_ts",
        "yes_bid_open_e4",
        "yes_bid_high_e4",
        "yes_bid_low_e4",
        "yes_bid_close_e4",
        "yes_ask_close_e4",
        "price_low_e4",
        "price_high_e4",
        "price_close_e4",
        "volume_hundredths",
        "is_valid",
    ]
    first80 = {}
    close_bar = {}
    wick_bar = {}
    for n_file, path in enumerate(files, 1):
        if n_file % 500 == 0 or n_file == 1:
            print(f"scan {n_file}/{len(files)} first80={len(first80)}", flush=True)
        table = pq.read_table(path, columns=cols)
        get = {c: table.column(c) for c in cols}
        by_ticker = defaultdict(list)
        for i in range(table.num_rows):
            if not get["is_valid"][i].as_py():
                continue
            ticker = get["ticker"][i].as_py()
            t = int(get["end_period_ts"][i].as_py())
            start, end = meta.get(ticker, (None, None))
            if start is not None and t < start:
                continue
            if end is not None and t > end:
                continue
            by_ticker[ticker].append(
                {
                    "ts": t,
                    "bid_h": A._opt_int(get["yes_bid_high_e4"][i].as_py()),
                    "bid_l": A._opt_int(get["yes_bid_low_e4"][i].as_py()),
                    "bid_c": A._opt_int(get["yes_bid_close_e4"][i].as_py()),
                    "ask_c": A._opt_int(get["yes_ask_close_e4"][i].as_py()),
                    "px_h": A._opt_int(get["price_high_e4"][i].as_py()),
                    "px_l": A._opt_int(get["price_low_e4"][i].as_py()),
                    "px_c": A._opt_int(get["price_close_e4"][i].as_py()),
                    "vol": A._opt_int(get["volume_hundredths"][i].as_py()),
                }
            )
        for ticker, rows in by_ticker.items():
            rows.sort(key=lambda r: r["ts"])
            had_q = False
            seen_below = False
            f80 = None
            for q in rows:
                if not A.quality(q["bid_c"], q["ask_c"], q["vol"], had_q):
                    continue
                had_q = True
                if q["bid_c"] < A.HIT80:
                    seen_below = True
                if f80 is None and q["bid_c"] >= A.HIT80 and seen_below:
                    f80 = q
            if not f80:
                continue
            first80[ticker] = f80
            close_bar[ticker] = first_close_barrier(rows, f80)
            wick_bar[ticker] = first_wick_barrier(rows, f80)
    return {"first80": first80, "close": close_bar, "wick": wick_bar}


def build_rows(markets, games, scanned, mode: str):
    by_event = defaultdict(list)
    for m in markets:
        by_event[m["event_id"]].append(m)
    games_by_event = {g["event_id"]: g for g in games}
    bars = scanned["close"] if mode == "close" else scanned["wick"]
    rows = []
    for event_id, ms in sorted(by_event.items()):
        g = games_by_event.get(event_id, {})
        hits = []
        for m in ms:
            q = scanned["first80"].get(m["ticker"])
            if q:
                hits.append((q["ts"], m["ticker"], m, q))
        hits.sort(key=lambda x: (x[0], x[1]))
        rec = {
            "event_id": event_id,
            "game_id": g.get("game_id") or event_id,
            "event_ticker": g.get("event_ticker"),
            "season_phase": g.get("season_phase"),
            "game_date": g.get("game_date"),
            "dataset_split": A.dataset_split(g.get("game_date")),
            "regime": A.season_regime(g.get("game_date")),
            "status": "NO_FIRST_80",
            "barrier_mode": mode,
        }
        if not hits:
            rows.append(rec)
            continue
        if len([h for h in hits if h[0] == hits[0][0]]) > 1:
            rec["status"] = "TIE_SAME_MINUTE_ENTRY"
            rows.append(rec)
            continue
        ts, ticker, m0, q = hits[0]
        bar = bars.get(ticker, {"exit_90": None, "exit_40": None, "tie": False})
        outcome = classify(bar)
        won = A.settled_yes(m0)
        e90 = bar.get("exit_90")
        e40 = bar.get("exit_40")
        rec.update(
            {
                "status": "FIRST_80",
                "market_id": m0["market_id"],
                "ticker": ticker,
                "team": m0["team"],
                "first_80_timestamp": ts,
                "first_80_utc": A.iso(ts),
                "maker_fill_confidence": A.maker_fill_confidence(q),
                "outcome": outcome,
                "exit_90_ts": None if e90 is None else e90["ts"],
                "exit_40_ts": None if e40 is None else e40["ts"],
                "same_bar_as_entry": (
                    (e90 is not None and e90["ts"] == ts)
                    or (e40 is not None and e40["ts"] == ts)
                ),
                "expiration_result_yes": won,
                "gross_pnl_cents": pnl_cents(outcome),
                "historical_fill_unknown": True,
                "orderbook_depth_available": False,
            }
        )
        rows.append(rec)
    return rows


def summarize(trades: list[dict], label: str) -> dict:
    decided = [t for t in trades if t.get("gross_pnl_cents") is not None]
    n90 = sum(1 for t in decided if t["outcome"] == "EXIT_90")
    n40 = sum(1 for t in decided if t["outcome"] == OUTCOME_STOP)
    n = len(decided)
    wr, lo, hi = wilson(n90, n)
    pnls = [t["gross_pnl_cents"] for t in decided]
    ev = None if n == 0 else round(sum(pnls) / n, 4)
    evr = None if n == 0 else round((sum(pnls) / n) / R_CENTS, 4)
    return {
        "label": label,
        "decided": n,
        "exit_90": n90,
        "exit_40": n40,
        "no_barrier": sum(1 for t in trades if t.get("outcome") == "NO_BARRIER"),
        "tie_same_minute": sum(1 for t in trades if t.get("outcome") == "TIE_SAME_MINUTE"),
        "p_90_pct": wr,
        "p_90_ci95": [lo, hi],
        "breakeven_pct": round(BE_P * 100, 4),
        "gross_ev_cents": ev,
        "gross_ev_R_vs_20c": evr,
        "gross_pnl_cents": sum(pnls) if decided else 0,
        "win_cents": WIN_CENTS,
        "loss_cents": LOSS_CENTS,
        "sample_size": n,
    }


def by_split(first80_rows: list[dict]) -> dict:
    out = {}
    for split in ("IN_SAMPLE", "VALIDATION", "OOS"):
        sub = [t for t in first80_rows if t.get("dataset_split") == split]
        out[split] = summarize(sub, split)
    return out


def write_report(summary: dict) -> None:
    c = summary["close"]
    w = summary["wick"]
    lines = [
        f"# NCAAB FIRST-80, first-exit 90 or {STOP_CENTS} — no expiration hold",
        "",
        "Research only. Not a fill. Not live FIRST01. L2 not invented.",
        "",
        "Entry: same FIRST-80 as the hold-to-settlement audit.",
        f"Exit: first `yes_bid_close ≥ 90¢` or `yes_bid_close ≤ {STOP_CENTS}¢`.",
        "If neither barrier prints, the path is **NO_BARRIER** (no settlement P&L).",
        f"If a wick path prints both 90-high and {STOP_CENTS}-low in the same minute, **TIE**",
        "(intra-minute order unknown).",
        "",
        f"Payoff if decided: **+{WIN_CENTS}¢** at 90, **−{LOSS_CENTS}¢** at {STOP_CENTS}. "
        f"Breakeven **{BE_P:.0%}** (hold-to-100 breakeven is 66.67%).",
        "",
        "## Close-path (primary)",
        "",
        f"- Settled FIRST-80 games: {summary['first80_settled']:,}",
        f"- EXIT_90: {c['exit_90']:,}",
        f"- {OUTCOME_STOP}: {c['exit_40']:,}",
        f"- NO_BARRIER: {c['no_barrier']:,}",
        f"- TIE (close both, should be ~0): {c['tie_same_minute']:,}",
        f"- P(90 | decided): **{c['p_90_pct']}%** CI {c['p_90_ci95']}",
        f"- Gross EV: **{c['gross_ev_cents']}¢ / trade** ({c['gross_ev_R_vs_20c']} R vs 20¢ unit)",
        "",
        f"## Wick sensitivity (bid_high 90 / bid_low {STOP_CENTS})",
        "",
        f"- EXIT_90: {w['exit_90']:,}  {OUTCOME_STOP}: {w['exit_40']:,}  "
        f"TIE: {w['tie_same_minute']:,}  NO_BARRIER: {w['no_barrier']:,}",
        f"- P(90 | decided): {w['p_90_pct']}% CI {w['p_90_ci95']}",
        f"- Gross EV: {w['gross_ev_cents']}¢ / trade ({w['gross_ev_R_vs_20c']} R)",
        "",
        f"Wick ties are excluded from EV. Do not assume 90 printed before {STOP_CENTS}.",
        "",
        "## Splits (close-path, a priori NBA calendar cuts)",
        "",
    ]
    for split, v in summary["splits_close"].items():
        lines.append(
            f"- **{split}**: decided={v['decided']:,} p90={v['p_90_pct']}% "
            f"EV={v['gross_ev_cents']}¢ no_barrier={v['no_barrier']:,}"
        )
    lines.extend(
        [
            "",
            "## What this is not",
            "",
            f"- Not an executed 90 maker/taker fill or {STOP_CENTS} IOC fill.",
            "- Not hold-to-expiration (that audit is separate).",
            "- Fees UNRESOLVED. KXNCAAMBGAME maker multiplier UNKNOWN.",
            "",
        ]
    )
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n")


def main() -> int:
    print("loading markets/games", flush=True)
    markets = N.load_markets()
    games = N.load_games()
    scanned = scan(markets, games)
    print(f"scan done first80_tickers={len(scanned['first80'])}", flush=True)

    close_rows = build_rows(markets, games, scanned, "close")
    wick_rows = build_rows(markets, games, scanned, "wick")
    first_c = [
        r
        for r in close_rows
        if r["status"] == "FIRST_80" and r.get("expiration_result_yes") is not None
    ]
    first_w = [
        r
        for r in wick_rows
        if r["status"] == "FIRST_80" and r.get("expiration_result_yes") is not None
    ]
    s_close = summarize(first_c, "close")
    s_wick = summarize(first_w, "wick")

    summary = {
        "sport": "ncaab",
        "series": "KXNCAAMBGAME",
        "season": "2025-2026",
        "rule": f"FIRST-80 entry; first of close-90 or close-{STOP_CENTS}; no expiration hold",
        "payoff": {
            "entry_e4": A.HIT80,
            "take_e4": HIT90,
            "stop_e4": HIT_STOP,
            "win_cents": WIN_CENTS,
            "loss_cents": LOSS_CENTS,
            "breakeven": BE_P,
            "hold_to_expiration": False,
        },
        "first80_settled": len(first_c),
        "no_first_80": sum(1 for r in close_rows if r["status"] == "NO_FIRST_80"),
        "close": s_close,
        "wick": s_wick,
        "splits_close": by_split(first_c),
        "splits_wick": by_split(first_w),
        "live_execution_changed": False,
        "l2_invented": False,
        "fills_invented": False,
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (OUT / "ledger_close.json").write_text(
        json.dumps(
            [
                {
                    "event_ticker": r.get("event_ticker"),
                    "ticker": r.get("ticker"),
                    "game_date": r.get("game_date"),
                    "dataset_split": r.get("dataset_split"),
                    "outcome": r.get("outcome"),
                    "gross_pnl_cents": r.get("gross_pnl_cents"),
                    "first_80_utc": r.get("first_80_utc"),
                    "exit_90_ts": r.get("exit_90_ts"),
                    "exit_40_ts": r.get("exit_40_ts"),
                    "same_bar_as_entry": r.get("same_bar_as_entry"),
                }
                for r in first_c
            ]
        )
        + "\n"
    )
    write_report(summary)
    print(json.dumps({"out": str(OUT), **{k: summary[k] for k in ("first80_settled", "close", "wick")}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
