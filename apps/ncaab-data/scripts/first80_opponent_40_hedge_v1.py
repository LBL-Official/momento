#!/usr/bin/env python3
"""FIRST80_OPPONENT_40_HEDGE_V1

After FIRST-80 on one YES, rest a 40¢ maker bid on the opponent YES.

Candle proxy (ESTIMATED, not a fill):
  first later tradable opponent yes_bid_close ≥ 40¢.

P&L if that proxy hits: locked −20¢ (80 + 40 − 100), settlement unused.
If it never hits: +20¢ on YES settlement, −80¢ on NO settlement.

Research only. LIVE EXECUTION CHANGED: FALSE.
Does not change FIRST01 / Risk / Execution. Does not invent L2.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import pyarrow.parquet as pq

NBA_SCRIPTS = Path("/Users/user/Desktop/Momento/apps/nba-data/scripts")
sys.path.insert(0, str(NBA_SCRIPTS))
import nba_80_40_execution_audit as A  # noqa: E402

PROGRAM = "FIRST80_OPPONENT_40_HEDGE_V1"
HIT40 = 4000
ENTRY = 80
HEDGE_PX = 40
LOCK_PNL = 100 - ENTRY - HEDGE_PX  # 100 − 80 − 40 = −20
WIN_PNL = 20
MISS_LOSS = -80
STOP_PNL = -40

SPORTS = {
    "nba": {
        "root": Path(
            "/Users/user/Desktop/Momento/Backtesting Suite/Data/NBA/2025-2026/warehouse"
        ),
        "norm": "nba",
        "games": "nba_games.parquet",
        "cands": Path(
            "/Users/user/Desktop/Momento/Backtesting Suite/Data/NBA/2025-2026/warehouse"
        )
        / "derived/nba/first80_execution_audit/candidates.json",
        "out": Path(
            "/Users/user/Desktop/Momento/Backtesting Suite/Data/NBA/2025-2026/warehouse"
        )
        / "derived/nba/first80_opponent_40_hedge_v1",
        "expected": 1230,
    },
    "ncaab": {
        "root": Path(
            "/Users/user/Desktop/Momento/Backtesting Suite/Data/NCAAB/2025-2026/warehouse"
        ),
        "norm": "ncaab",
        "games": "ncaab_games.parquet",
        "cands": Path(
            "/Users/user/Desktop/Momento/Backtesting Suite/Data/NCAAB/2025-2026/warehouse"
        )
        / "derived/ncaab/first80_execution_audit/candidates.json",
        "out": Path(
            "/Users/user/Desktop/Momento/Backtesting Suite/Data/NCAAB/2025-2026/warehouse"
        )
        / "derived/ncaab/first80_opponent_40_hedge_v1",
        "expected": 4099,
    },
}
DOCS = Path("/Users/user/Desktop/Momento/docs/research/ncaab/FIRST80_OPPONENT_40_HEDGE_V1.md")


def wilson(k: int, n: int):
    p, lo, hi = A.wilson(k, n)
    return {"n": n, "k": k, "pct": p, "ci95": [lo, hi]}


def pair_tickers(game: dict) -> list[str]:
    home = game.get("home_market_ticker")
    away = game.get("away_market_ticker")
    if home and away:
        return [str(home), str(away)]
    raw = game.get("market_tickers")
    if isinstance(raw, str):
        return [x.strip() for x in raw.split(",") if x.strip()]
    if isinstance(raw, list):
        return [str(x) for x in raw]
    return []


def load_games(cfg: dict) -> dict[str, dict]:
    path = cfg["root"] / "normalized" / cfg["norm"] / "games" / cfg["games"]
    t = pq.read_table(path)
    names = t.column_names
    out = {}
    for i in range(t.num_rows):
        row = {n: t.column(n)[i].as_py() for n in names}
        out[row["event_id"]] = row
    return out


def opponent_of(game: dict, held: str) -> str | None:
    pair = pair_tickers(game)
    others = [t for t in pair if t != held]
    if len(others) == 1:
        return others[0]
    return None


def scan_hedges(cfg: dict, trades: list[dict], games: dict) -> None:
    """Fill hedge_* fields on each trade from opponent (and held) candles."""
    candles = cfg["root"] / "normalized" / cfg["norm"] / "candles_1m"
    opp_entry: dict[str, tuple[int, int]] = {}
    held_entry: dict[str, int] = {}
    by_opp: dict[str, list[int]] = defaultdict(list)
    for i, rec in enumerate(trades):
        rec["opponent_ticker"] = None
        rec["opponent_available"] = False
        rec["hedge_close"] = False
        rec["hedge_wick"] = False
        rec["hedge_ask_le_40"] = False
        rec["hedge_close_ts"] = None
        rec["hedge_wick_ts"] = None
        rec["hedge_opp_bid_close_e4"] = None
        rec["hedge_opp_ask_close_e4"] = None
        rec["held_bid_at_hedge_e4"] = None
        rec["complement_sum_e4"] = None
        g = games.get(rec.get("event_id"))
        if not g:
            rec["opponent_status"] = "GAME_MISSING"
            continue
        opp = opponent_of(g, rec["ticker"])
        if not opp:
            rec["opponent_status"] = "OPPONENT_UNAVAILABLE"
            continue
        rec["opponent_ticker"] = opp
        rec["opponent_available"] = True
        rec["opponent_status"] = "OK"
        ts = int(rec["first_80_timestamp"])
        end = rec.get("close_ts")
        end_i = int(end) if end is not None else None
        opp_entry[opp] = (ts, end_i if end_i is not None else 2**31)
        held_entry[rec["ticker"]] = ts
        by_opp[opp].append(i)

    needed = set(opp_entry) | set(held_entry)
    first_close: dict[str, dict] = {}
    first_wick: dict[str, dict] = {}
    first_ask: dict[str, dict] = {}
    held_at: dict[str, dict[int, int]] = defaultdict(dict)
    files = [p for p in candles.rglob("*.parquet") if p.stem in needed]
    print(f"  candle files {len(files)} / needed {len(needed)}", flush=True)
    cols = [
        "ticker",
        "end_period_ts",
        "yes_bid_high_e4",
        "yes_bid_close_e4",
        "yes_ask_close_e4",
        "volume_hundredths",
        "is_valid",
    ]
    for n_file, path in enumerate(files, 1):
        if n_file % 400 == 0 or n_file == 1:
            print(f"  scan {n_file}/{len(files)}", flush=True)
        table = pq.read_table(path, columns=cols)
        get = {c: table.column(c) for c in cols}
        had_q = False
        ticker = path.stem
        entry_end = opp_entry.get(ticker)
        held_ts0 = held_entry.get(ticker)
        for i in range(table.num_rows):
            if not get["is_valid"][i].as_py():
                continue
            t = int(get["end_period_ts"][i].as_py())
            bid_c = A._opt_int(get["yes_bid_close_e4"][i].as_py())
            ask_c = A._opt_int(get["yes_ask_close_e4"][i].as_py())
            bid_h = A._opt_int(get["yes_bid_high_e4"][i].as_py())
            vol = A._opt_int(get["volume_hundredths"][i].as_py())
            if held_ts0 is not None and t >= held_ts0 and bid_c is not None:
                held_at[ticker][t] = bid_c
            if entry_end is None:
                continue
            ts0, ts1 = entry_end
            if t <= ts0 or t > ts1:
                continue
            if not A.quality(bid_c, ask_c, vol, had_q):
                continue
            had_q = True
            q = {
                "ts": t,
                "bid_c": bid_c,
                "ask_c": ask_c,
                "bid_h": bid_h,
            }
            if ticker not in first_close and bid_c is not None and bid_c >= HIT40:
                first_close[ticker] = q
            if ticker not in first_wick and bid_h is not None and bid_h >= HIT40:
                first_wick[ticker] = q
            if ticker not in first_ask and ask_c is not None and ask_c <= HIT40:
                first_ask[ticker] = q

    for opp, idxs in by_opp.items():
        fc = first_close.get(opp)
        fw = first_wick.get(opp)
        fa = first_ask.get(opp)
        for i in idxs:
            rec = trades[i]
            if fc:
                rec["hedge_close"] = True
                rec["hedge_close_ts"] = fc["ts"]
                rec["hedge_opp_bid_close_e4"] = fc["bid_c"]
                rec["hedge_opp_ask_close_e4"] = fc["ask_c"]
                rec["held_bid_at_hedge_e4"] = held_at.get(rec["ticker"], {}).get(fc["ts"])
                if rec["held_bid_at_hedge_e4"] is not None:
                    rec["complement_sum_e4"] = rec["held_bid_at_hedge_e4"] + fc["bid_c"]
            if fw:
                rec["hedge_wick"] = True
                rec["hedge_wick_ts"] = fw["ts"]
            if fa:
                rec["hedge_ask_le_40"] = True


def classify(rec: dict, hedge: bool) -> str:
    if hedge:
        return "HEDGE_LOCK"
    if rec["expiration_result_yes"]:
        return "NO_HEDGE_WIN"
    return "NO_HEDGE_LOSS"


def pnl_cents(outcome: str) -> int:
    return {
        "HEDGE_LOCK": LOCK_PNL,
        "NO_HEDGE_WIN": WIN_PNL,
        "NO_HEDGE_LOSS": MISS_LOSS,
    }[outcome]


def baseline_pnl(rec: dict) -> int:
    if rec.get("stop_close_triggered"):
        return STOP_PNL
    if rec["expiration_result_yes"]:
        return WIN_PNL
    return 0  # LOSS_NO_STOP: same as frozen 80/40 book (2 NCAAB leaks)


def summarize(sport: str, trades: list[dict], mode: str) -> dict:
    n = len(trades)
    hedge_key = "hedge_close" if mode == "close" else "hedge_wick"
    outcomes = [classify(t, bool(t.get(hedge_key))) for t in trades]
    locks = sum(1 for o in outcomes if o == "HEDGE_LOCK")
    wins = sum(1 for o in outcomes if o == "NO_HEDGE_WIN")
    misses = sum(1 for o in outcomes if o == "NO_HEDGE_LOSS")
    pnls = [pnl_cents(o) for o in outcomes]
    ev = sum(pnls) / n
    base = [baseline_pnl(t) for t in trades]
    base_ev = sum(base) / n

    hedge_then_yes = sum(
        1 for t, o in zip(trades, outcomes) if o == "HEDGE_LOCK" and t["expiration_result_yes"]
    )
    hedge_then_no = locks - hedge_then_yes
    stop = sum(1 for t in trades if t.get("stop_close_triggered"))
    hedge_and_stop = sum(
        1 for t in trades if t.get(hedge_key) and t.get("stop_close_triggered")
    )
    hedge_not_stop = sum(
        1 for t in trades if t.get(hedge_key) and not t.get("stop_close_triggered")
    )
    stop_not_hedge = sum(
        1 for t in trades if t.get("stop_close_triggered") and not t.get(hedge_key)
    )
    missing_opp = sum(1 for t in trades if not t.get("opponent_available"))

    held_at = [
        t["held_bid_at_hedge_e4"]
        for t in trades
        if t.get(hedge_key) and t.get("held_bid_at_hedge_e4") is not None
    ]
    comps = [
        t["complement_sum_e4"]
        for t in trades
        if t.get(hedge_key) and t.get("complement_sum_e4") is not None
    ]

    def dist_cents(vals):
        if not vals:
            return None
        s = sorted(v / 100.0 for v in vals)
        return {
            "n": len(s),
            "mean": round(sum(s) / len(s), 4),
            "median": round(s[len(s) // 2], 4),
            "p10": round(s[int(0.10 * (len(s) - 1))], 4),
            "p90": round(s[int(0.90 * (len(s) - 1))], 4),
            "min": round(s[0], 4),
            "max": round(s[-1], 4),
        }

    return {
        "sport": sport,
        "mode": mode,
        "status": "ESTIMATED",
        "n": n,
        "missing_opponent": missing_opp,
        "hedge_locks": locks,
        "no_hedge_wins": wins,
        "no_hedge_losses": misses,
        "p_hedge": wilson(locks, n),
        "p_miss_loss": wilson(misses, n),
        "p_no_hedge_win": wilson(wins, n),
        "hedge_then_settled_yes": hedge_then_yes,
        "hedge_then_settled_no": hedge_then_no,
        "p_yes_given_hedge": wilson(hedge_then_yes, locks) if locks else None,
        "overlap_close_stop": {
            "baseline_stops": stop,
            "hedge_and_stop": hedge_and_stop,
            "hedge_not_stop": hedge_not_stop,
            "stop_not_hedge": stop_not_hedge,
        },
        "gross_ev_cents": round(ev, 4),
        "gross_ev_R": round(ev / WIN_PNL, 4),
        "baseline_80_40_ev_cents": round(base_ev, 4),
        "pnl_sum_cents": sum(pnls),
        "held_bid_at_hedge_cents": dist_cents(held_at),
        "complement_sum_cents": dist_cents(comps),
        "payoff": {
            "hedge_lock": LOCK_PNL,
            "no_hedge_win": WIN_PNL,
            "no_hedge_loss": MISS_LOSS,
            "note": "80+40−100=−20 if both legs fill. Missed hedge + NO settlement = −80.",
        },
    }


def write_sport_report(summary: dict, path: Path) -> None:
    c = summary["close"]
    w = summary["wick"]
    ov = c["overlap_close_stop"]
    lines = [
        f"# {PROGRAM} — {summary['sport'].upper()}",
        "",
        "40¢ opponent bid is ESTIMATED from candles. Not a fill. L2 UNAVAILABLE.",
        "LIVE EXECUTION CHANGED: FALSE.",
        "",
        f"Settled FIRST-80: {c['n']:,}  |  opponent missing: {c['missing_opponent']}",
        "",
        "## Close-path hedge (opponent yes_bid_close ≥ 40)",
        "",
        f"| | N | % |",
        f"|---|---:|---:|",
        f"| Hedge lock (−20¢) | {c['hedge_locks']:,} | {c['p_hedge']['pct']}% |",
        f"| No hedge, won (+20¢) | {c['no_hedge_wins']:,} | {c['p_no_hedge_win']['pct']}% |",
        f"| No hedge, lost (−80¢) | {c['no_hedge_losses']:,} | {c['p_miss_loss']['pct']}% |",
        "",
        f"Gross EV: **{c['gross_ev_cents']}¢** / trade  "
        f"(baseline 80/40 close-stop: {c['baseline_80_40_ev_cents']}¢)",
        "",
        f"Of hedge locks, later settled YES (whipsaw vs hold): "
        f"{c['hedge_then_settled_yes']:,} / {c['hedge_locks']:,}",
        f"({(c['p_yes_given_hedge'] or {}).get('pct')}%).",
        "",
        f"Overlap vs favorite close-40 stop: both {ov['hedge_and_stop']:,}; "
        f"hedge only {ov['hedge_not_stop']:,}; stop only {ov['stop_not_hedge']:,}.",
        "",
        "## Wick-path hedge (opponent yes_bid_high ≥ 40)",
        "",
        f"Locks {w['hedge_locks']:,} ({w['p_hedge']['pct']}%). "
        f"EV {w['gross_ev_cents']}¢. Miss losses {w['no_hedge_losses']:,}.",
        "",
    ]
    path.write_text("\n".join(lines) + "\n")


def write_docs(nba: dict, ncaab: dict) -> None:
    nc, nw = ncaab["close"], ncaab["wick"]
    bc, bw = nba["close"], nba["wick"]
    text = f"""# FIRST80_OPPONENT_40_HEDGE_V1

Research only. **LIVE EXECUTION CHANGED: FALSE.**

After FIRST-80 on one YES, rest a **40¢ maker bid on the opponent YES**.

This is not `ExitPrice = 40`. If both legs fill:

```text
80 + 40 − 100 = −20¢ locked
```

If the 40 bid never fills: +20¢ on YES settlement, **−80¢** on NO settlement.

Candle proxy (ESTIMATED): first later tradable `opponent yes_bid_close ≥ 40`.
Wick proxy: `opponent yes_bid_high ≥ 40`. L2 / queue UNAVAILABLE.

Same FIRST-80 universe as the frozen audits (NBA 1,230 / NCAAB 4,099).
Fees UNRESOLVED.

## Results

| | NCAAB close | NCAAB wick | NBA close | NBA wick |
|---|---:|---:|---:|---:|
| n | {nc['n']:,} | {nw['n']:,} | {bc['n']:,} | {bw['n']:,} |
| Hedge lock (−20) | {nc['hedge_locks']:,} ({nc['p_hedge']['pct']}%) | {nw['hedge_locks']:,} ({nw['p_hedge']['pct']}%) | {bc['hedge_locks']:,} ({bc['p_hedge']['pct']}%) | {bw['hedge_locks']:,} ({bw['p_hedge']['pct']}%) |
| No hedge, win (+20) | {nc['no_hedge_wins']:,} | {nw['no_hedge_wins']:,} | {bc['no_hedge_wins']:,} | {bw['no_hedge_wins']:,} |
| No hedge, lose (−80) | {nc['no_hedge_losses']:,} | {nw['no_hedge_losses']:,} | {bc['no_hedge_losses']:,} | {bw['no_hedge_losses']:,} |
| **Hedge EV ¢** | **{nc['gross_ev_cents']}** | **{nw['gross_ev_cents']}** | **{bc['gross_ev_cents']}** | **{bw['gross_ev_cents']}** |
| Baseline 80/40 EV ¢ | {nc['baseline_80_40_ev_cents']} | | {bc['baseline_80_40_ev_cents']} | |
| Hedge then settled YES | {nc['hedge_then_settled_yes']:,} | {nw['hedge_then_settled_yes']:,} | {bc['hedge_then_settled_yes']:,} | {bw['hedge_then_settled_yes']:,} |
| Hedge ∩ favorite-40 | {nc['overlap_close_stop']['hedge_and_stop']:,} | | {bc['overlap_close_stop']['hedge_and_stop']:,} | |
| Hedge only | {nc['overlap_close_stop']['hedge_not_stop']:,} | | {bc['overlap_close_stop']['hedge_not_stop']:,} | |
| Stop only | {nc['overlap_close_stop']['stop_not_hedge']:,} | | {bc['overlap_close_stop']['stop_not_hedge']:,} | |

Held YES bid at the opponent-40 minute (close path), cents:

- NCAAB: {nc['held_bid_at_hedge_cents']}
- NBA: {bc['held_bid_at_hedge_cents']}

## How to read this

Opponent-40 is an **earlier** fade than favorite-40 (complement ≈ 100).
Those extra hedges include games that later settled YES — they flip +20 → −20.

Missed-hedge losses at −80 are why a “free 40 bid” can be worse than the
80/40 stop even when the lock itself is only −20.

Not live. Not FIRST01. Do not arm NBA/NCAAB execution from this table.

Code: `apps/ncaab-data/scripts/first80_opponent_40_hedge_v1.py`  
Artifacts: `.../derived/{{ncaab,nba}}/first80_opponent_40_hedge_v1/`
"""
    DOCS.write_text(text)


def run_sport(sport: str) -> dict:
    cfg = SPORTS[sport]
    print(f"== {sport} ==", flush=True)
    games = load_games(cfg)
    cands = json.loads(cfg["cands"].read_text())
    trades = [
        dict(c)
        for c in cands
        if c.get("status") == "FIRST_80" and c.get("expiration_result_yes") is not None
    ]
    assert len(trades) == cfg["expected"], (sport, len(trades), cfg["expected"])
    scan_hedges(cfg, trades, games)
    payload = {
        "program": PROGRAM,
        "sport": sport,
        "live_execution_changed": False,
        "close": summarize(sport, trades, "close"),
        "wick": summarize(sport, trades, "wick"),
    }
    out = cfg["out"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(payload, indent=2) + "\n")
    slim = []
    for t in trades:
        slim.append(
            {
                "ticker": t["ticker"],
                "opponent_ticker": t.get("opponent_ticker"),
                "game_date": t.get("game_date"),
                "dataset_split": t.get("dataset_split"),
                "expiration_result_yes": t["expiration_result_yes"],
                "stop_close_triggered": t.get("stop_close_triggered"),
                "hedge_close": t.get("hedge_close"),
                "hedge_wick": t.get("hedge_wick"),
                "hedge_close_ts": t.get("hedge_close_ts"),
                "held_bid_at_hedge_e4": t.get("held_bid_at_hedge_e4"),
                "complement_sum_e4": t.get("complement_sum_e4"),
                "close_outcome": classify(t, bool(t.get("hedge_close"))),
                "close_pnl_cents": pnl_cents(classify(t, bool(t.get("hedge_close")))),
                "baseline_pnl_cents": baseline_pnl(t),
            }
        )
    (out / "ledger.json").write_text(json.dumps(slim) + "\n")
    write_sport_report(payload, out / "REPORT.md")
    return payload


def main() -> int:
    assert LOCK_PNL == -20
    assert pnl_cents("HEDGE_LOCK") + 40 == pnl_cents("NO_HEDGE_WIN")
    nba = run_sport("nba")
    ncaab = run_sport("ncaab")
    write_docs(nba, ncaab)
    print(
        json.dumps(
            {
                "program": PROGRAM,
                "nba_close": nba["close"]["gross_ev_cents"],
                "nba_hedge": nba["close"]["hedge_locks"],
                "nba_miss": nba["close"]["no_hedge_losses"],
                "ncaab_close": ncaab["close"]["gross_ev_cents"],
                "ncaab_hedge": ncaab["close"]["hedge_locks"],
                "ncaab_miss": ncaab["close"]["no_hedge_losses"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
