#!/usr/bin/env python3
"""NCAAB 80¢ maker / 40¢ stop observational audit.

Same FIRST-80 / close-40 rule as apps/nba-data/scripts/nba_80_40_execution_audit.py
applied to the 2025–2026 KXNCAAMBGAME warehouse.

Research only. Does not change live FIRST01, Risk, or NBA artifacts.
Does not invent L2, queue position, fills, or a production fee model.
Does not require NBA frozen counts (this is a first measurement).
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pyarrow.parquet as pq

NBA_SCRIPTS = Path("/Users/user/Desktop/Momento/apps/nba-data/scripts")
sys.path.insert(0, str(NBA_SCRIPTS))
import nba_80_40_execution_audit as A  # noqa: E402

ROOT = Path(
    "/Users/user/Desktop/Momento/Backtesting Suite/Data/NCAAB/2025-2026/warehouse"
)
NORM = ROOT / "normalized" / "ncaab"
OUT = ROOT / "derived" / "ncaab" / "first80_execution_audit"

# Same a priori calendar cuts as the NBA audit. Not fit to NCAAB results.
A.SPLIT_RESEARCH_END = "2025-12-31"
A.SPLIT_VAL_END = "2026-03-15"


def load_markets():
    t = pq.read_table(
        NORM / "markets" / "markets.parquet",
        columns=[
            "ticker",
            "event_id",
            "market_id",
            "team",
            "yes_subtitle",
            "result",
            "settlement_value_e4",
            "season_phase",
            "close_time",
        ],
    )
    rows = []
    for i in range(t.num_rows):
        rows.append(
            {
                "ticker": t.column("ticker")[i].as_py(),
                "event_id": t.column("event_id")[i].as_py(),
                "market_id": t.column("market_id")[i].as_py(),
                "team": t.column("team")[i].as_py()
                or t.column("yes_subtitle")[i].as_py(),
                "result": t.column("result")[i].as_py(),
                "settlement_value_e4": A._opt_int(
                    t.column("settlement_value_e4")[i].as_py()
                ),
                "season_phase": t.column("season_phase")[i].as_py(),
                "close_ts": A.parse_ts(t.column("close_time")[i].as_py()),
            }
        )
    return rows


def load_games():
    t = pq.read_table(NORM / "games" / "ncaab_games.parquet")
    names = t.column_names
    rows = []
    for i in range(t.num_rows):
        row = {n: t.column(n)[i].as_py() for n in names}
        gd = A.parse_game_date(row.get("game_date"))
        if gd:
            # Same game-day window as the NBA audit (16h–52h from date UTC).
            row["game_window_start"] = int((gd + timedelta(hours=16)).timestamp())
            row["game_window_end"] = int((gd + timedelta(hours=52)).timestamp())
        else:
            row["game_window_start"] = None
            row["game_window_end"] = None
        rows.append(row)
    return rows


def scan(markets, games):
    """Same tradable-cross rule as NBA, one candle file at a time."""
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
        meta[m["ticker"]] = (start, end, m["close_ts"])

    files = sorted((NORM / "candles_1m").rglob("*.parquet"))
    cols = [
        "ticker",
        "end_period_ts",
        "yes_bid_open_e4",
        "yes_bid_high_e4",
        "yes_bid_low_e4",
        "yes_bid_close_e4",
        "yes_ask_open_e4",
        "yes_ask_high_e4",
        "yes_ask_low_e4",
        "yes_ask_close_e4",
        "price_open_e4",
        "price_high_e4",
        "price_low_e4",
        "price_close_e4",
        "volume_hundredths",
        "is_valid",
    ]
    first80 = {}
    first40_close = {}
    first40_low = {}
    first39_close = {}
    first38_close = {}
    subsequent_80 = {}
    for n_file, path in enumerate(files, 1):
        if n_file % 500 == 0 or n_file == 1:
            print(
                f"scan {n_file}/{len(files)} first80={len(first80)}",
                flush=True,
            )
        table = pq.read_table(path, columns=cols)
        get = {c: table.column(c) for c in cols}
        by_ticker = defaultdict(list)
        for i in range(table.num_rows):
            if not get["is_valid"][i].as_py():
                continue
            ticker = get["ticker"][i].as_py()
            t = int(get["end_period_ts"][i].as_py())
            start, end, _ = meta.get(ticker, (None, None, None))
            if start is not None and t < start:
                continue
            if end is not None and t > end:
                continue
            by_ticker[ticker].append(
                {
                    "ts": t,
                    "bid_o": A._opt_int(get["yes_bid_open_e4"][i].as_py()),
                    "bid_h": A._opt_int(get["yes_bid_high_e4"][i].as_py()),
                    "bid_l": A._opt_int(get["yes_bid_low_e4"][i].as_py()),
                    "bid_c": A._opt_int(get["yes_bid_close_e4"][i].as_py()),
                    "ask_o": A._opt_int(get["yes_ask_open_e4"][i].as_py()),
                    "ask_h": A._opt_int(get["yes_ask_high_e4"][i].as_py()),
                    "ask_l": A._opt_int(get["yes_ask_low_e4"][i].as_py()),
                    "ask_c": A._opt_int(get["yes_ask_close_e4"][i].as_py()),
                    "px_o": A._opt_int(get["price_open_e4"][i].as_py()),
                    "px_h": A._opt_int(get["price_high_e4"][i].as_py()),
                    "px_l": A._opt_int(get["price_low_e4"][i].as_py()),
                    "px_c": A._opt_int(get["price_close_e4"][i].as_py()),
                    "vol": A._opt_int(get["volume_hundredths"][i].as_py()),
                }
            )
        for ticker, rows in by_ticker.items():
            rows.sort(key=lambda r: r["ts"])
            had_q = False
            seen_below_80 = False
            f80 = None
            for q in rows:
                if not A.quality(q["bid_c"], q["ask_c"], q["vol"], had_q):
                    continue
                had_q = True
                if q["bid_c"] < A.HIT80:
                    seen_below_80 = True
                if f80 is None and q["bid_c"] >= A.HIT80 and seen_below_80:
                    f80 = q
                    first80[ticker] = q
            if not f80:
                continue
            n80 = 0
            for q in rows:
                if q["ts"] <= f80["ts"]:
                    continue
                if not A.quality(q["bid_c"], q["ask_c"], q["vol"], True):
                    continue
                if q["bid_c"] >= A.HIT80:
                    n80 += 1
                if ticker not in first40_close and q["bid_c"] <= A.HIT40:
                    first40_close[ticker] = q
                if ticker not in first39_close and q["bid_c"] <= A.HIT39:
                    first39_close[ticker] = q
                if ticker not in first38_close and q["bid_c"] <= A.HIT38:
                    first38_close[ticker] = q
                if (
                    ticker not in first40_low
                    and q["bid_l"] is not None
                    and q["bid_l"] <= A.HIT40
                ):
                    first40_low[ticker] = q
            subsequent_80[ticker] = n80
            if (
                ticker not in first40_low
                and f80["bid_l"] is not None
                and f80["bid_l"] <= A.HIT40
            ):
                first40_low[ticker] = f80
    return {
        "first80": first80,
        "first40_close": first40_close,
        "first40_low": first40_low,
        "first39_close": first39_close,
        "first38_close": first38_close,
        "subsequent_80": subsequent_80,
        "meta": meta,
    }


def write_report(summary: dict) -> None:
    b = summary["baseline"]
    m = summary["models"]
    lines = [
        "# NCAAB 80¢ maker / 40¢ stop — observational audit",
        "",
        "Research only. Does not change live FIRST01. Does not invent L2.",
        "",
        "Same rule as `apps/nba-data/scripts/nba_80_40_execution_audit.py` on",
        "`KXNCAAMBGAME` 2025–2026. **This is a first measurement**, not a",
        "reproduction of the NBA 1,230 / 910 / 320 freeze.",
        "",
        "Re-run: ` /tmp/momento-nba-venv/bin/python apps/ncaab-data/scripts/ncaab_80_40_execution_audit.py`",
        "",
        "---",
        "",
        "## 1. Observed FIRST-80 / close-40 path",
        "",
        "| | N |",
        "|---|---:|",
        f"| Games | {b['games']:,} |",
        f"| First tradable 80 cross (settled) | {b['first80_settled']:,} |",
        f"| Never later `yes_bid_close ≤ 40¢` and won | {b['survivors_no40']:,} |",
        f"| Later `yes_bid_close ≤ 40¢` | {b['stops_40_close']:,} |",
        f"| No tradable 80 | {b['no_first_80']:,} |",
        "",
        f"Strategy win rate (hold unless close-stop): **{b['strategy_win_rate_pct']}%**  ",
        f"95% Wilson CI: **{b['strategy_win_rate_ci95'][0]}% – {b['strategy_win_rate_ci95'][1]}%** "
        f"(n = {b['first80_settled']})",
        "",
        "| Quantity | Estimate |",
        "|---|---:|",
        f"| P(Kalshi yes \\| first 80) | {b['p_win_kalshi_yes']}% |",
        f"| P(no close-40 \\| first 80) | {b['p_no40']}% |",
        f"| Gross EV / trade (+1R/−2R) | {m['original_baseline']['gross_ev_R']} R |",
        f"| +1R/−2R breakeven | 66.67% |",
        "",
        "Candle path ≠ fill. Historical L2 is NOT AVAILABLE.",
        "",
        "## 2. Execution-realism models",
        "",
        "| Model | Trades | Win rate | Gross EV R |",
        "|---|---:|---:|---:|",
    ]
    for key, label in (
        ("original_baseline", "original (close-stop, all fills)"),
        ("base_execution", "require last-print through 80"),
        ("conservative_execution", "HIGH + wick-stop"),
        ("high_fill_close_stop", "HIGH + close-stop"),
        ("all_fills_bid_low_stop", "all fills + wick-stop"),
    ):
        v = m[key]
        lines.append(
            f"| {label} | {v['trades']:,} | {v['win_rate_pct']}% | {v['gross_ev_R']} |"
        )
    lines.extend(
        [
            "",
            "## 3. Chronological splits (a priori, same cuts as NBA)",
            "",
            "IN_SAMPLE `game_date <= 2025-12-31`; VALIDATION through 2026-03-15; OOS after.",
            "",
        ]
    )
    for split, v in summary["splits"]["original_baseline"].items():
        lines.append(
            f"- **{split}**: n={v['trades']:,} win={v['win_rate_pct']}% "
            f"CI {v['win_rate_ci95']} EV_R={v['gross_ev_R']}"
        )
    lines.extend(
        [
            "",
            "## 4. What this is not",
            "",
            "- Not a live order, fill, or realized P&L.",
            "- Not MLB FIRST01 / 80/81/83/89.",
            "- Not W9. Not a production NCAAB strategy.",
            "- Fees are a labeled published-schedule estimate. "
            "`KXNCAAMBGAME` maker multiplier is UNKNOWN.",
            "",
        ]
    )
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n")


def main() -> int:
    print("loading markets/games", flush=True)
    markets = load_markets()
    games = load_games()
    print(f"markets={len(markets)} games={len(games)}", flush=True)
    scanned = scan(markets, games)
    print(f"scan done first80_tickers={len(scanned['first80'])}", flush=True)
    cands = A.build_candidates(markets, games, scanned)

    first = [
        c
        for c in cands
        if c["status"] == "FIRST_80" and c["expiration_result_yes"] is not None
    ]
    survivors = [
        c
        for c in first
        if not c["stop_close_triggered"] and c["expiration_result_yes"]
    ]
    stops = [c for c in first if c["stop_close_triggered"]]
    no80 = [c for c in cands if c["status"] == "NO_FIRST_80"]

    baseline_trades = []
    for c in first:
        outcome = "STOP" if c["stop_close_triggered"] else "WIN"
        if outcome == "WIN" and not c["expiration_result_yes"]:
            outcome = "LOSS_NO_STOP"
        baseline_trades.append({**c, "outcome": outcome, "scenario": "original_baseline"})

    conf_counts = defaultdict(int)
    for c in first:
        conf_counts[c["maker_fill_confidence"]] += 1

    agg, agg_rej = A.apply_scenario(cands, "aggressive")
    base_e, base_rej = A.apply_scenario(cands, "baseline_exec")
    cons, cons_rej = A.apply_scenario(cands, "conservative", stop_level="40_low")
    high_close, _ = A.apply_scenario(cands, "conservative", stop_level="40_close")
    all_low, _ = A.apply_scenario(cands, "aggressive", stop_level="40_low")

    s_orig = A.summarize_trades(baseline_trades, "original_baseline", False)
    s_agg = A.summarize_trades(agg, "aggressive", False)
    s_base = A.summarize_trades(base_e, "base_execution", False)
    s_cons = A.summarize_trades(cons, "conservative", False)
    s_high_close = A.summarize_trades(high_close, "high_fill_close_stop", False)
    s_all_low = A.summarize_trades(all_low, "all_fills_low_stop", False)
    s_orig_fee = A.summarize_trades(baseline_trades, "original_baseline_maker_fee_on", True)
    s_base_fee = A.summarize_trades(base_e, "base_execution_maker_fee_on", True)
    s_cons_fee = A.summarize_trades(cons, "conservative_maker_fee_on", True)

    p40_close = A.eventual_win_given_stop(cands, "stop_close_triggered")
    p40_low = A.eventual_win_given_stop(cands, "stop_low_triggered")

    sens = {}
    for name, attr in (
        ("40_close", "stop_close_triggered"),
        ("39_close", "stop_39_triggered"),
        ("38_close", "stop_38_triggered"),
        ("40_low", "stop_low_triggered"),
    ):
        tr = []
        for c in first:
            stopped = c[attr]
            outcome = (
                "STOP"
                if stopped
                else ("WIN" if c["expiration_result_yes"] else "LOSS_NO_STOP")
            )
            tr.append({**c, "outcome": outcome})
        sens[name] = A.summarize_trades(tr, name, False)

    ports = {str(k) if k else "unlimited": A.portfolio_sim(baseline_trades, k) for k in (1, 2, 3, 5, None)}
    ports_cons = {str(k) if k else "unlimited": A.portfolio_sim(cons, k) for k in (1, 2, 3, 5, None)}
    wr_b, lo_b, hi_b = A.wilson(len(survivors), len(first))

    leak = A.leakage_audit(cands, False)
    leak["baseline_reproduced"] = False
    leak["notes"] = list(leak.get("notes") or []) + [
        "NCAAB is a first measurement. NBA frozen 1230/910/320 counts are not required.",
        "KXNCAAMBGAME maker-fee multiplier is UNKNOWN.",
    ]

    summary = {
        "sport": "ncaab",
        "series": "KXNCAAMBGAME",
        "season": "2025-2026",
        "rule": "NBA FIRST-80 / close-40 observational audit, first NCAAB measurement",
        "price_interpretation": {
            "yes_bid_ohlc": "1-minute Kalshi yes_bid top-of-book OHLC. Not last, not mid, not L2.",
            "first_80_original": "first tradable yes_bid_close >= 8000 after a prior tradable close < 8000, game-day window",
            "first_40_original": "later tradable yes_bid_close <= 4000",
            "orderbook_depth_available": False,
            "historical_fill_unknown": True,
        },
        "fees": {
            "production_fee_model": "UNRESOLVED",
            "kxncaambgame_maker_multiplier": "UNKNOWN_NOT_IN_WAREHOUSE",
            "label": "RESEARCH_PUBLISHED_SCHEDULE_ESTIMATE",
        },
        "baseline": {
            "games": len(cands),
            "no_first_80": len(no80),
            "first80_settled": len(first),
            "survivors_no40": len(survivors),
            "stops_40_close": len(stops),
            "strategy_win_rate_pct": wr_b,
            "strategy_win_rate_ci95": [lo_b, hi_b],
            "reproduced": False,
            "p_win_kalshi_yes": A.rate(
                sum(1 for c in first if c["expiration_result_yes"]), len(first)
            ),
            "p_no40": A.rate(len(survivors), len(first)),
            "p_eventual_win_given_40_close": p40_close,
            "p_eventual_win_given_40_low": p40_low,
            "loss_no_stop": sum(1 for t in baseline_trades if t["outcome"] == "LOSS_NO_STOP"),
        },
        "fill_confidence_counts": dict(conf_counts),
        "models": {
            "original_baseline": s_orig,
            "aggressive_execution": s_agg,
            "base_execution": s_base,
            "conservative_execution": s_cons,
            "high_fill_close_stop": s_high_close,
            "all_fills_bid_low_stop": s_all_low,
            "original_baseline_maker_fee_on": s_orig_fee,
            "base_execution_maker_fee_on": s_base_fee,
            "conservative_execution_maker_fee_on": s_cons_fee,
        },
        "rejected": {
            "aggressive": len(agg_rej),
            "base": len(base_rej),
            "conservative": len(cons_rej),
        },
        "stop_sensitivity": sens,
        "splits": {
            "cuts": {
                "IN_SAMPLE": "game_date <= 2025-12-31",
                "VALIDATION": "2025-12-31 < game_date <= 2026-03-15",
                "OOS": "game_date > 2026-03-15",
            },
            "original_baseline": A.by_split(baseline_trades, False),
            "base_execution": A.by_split(base_e, False),
            "conservative_execution": A.by_split(cons, False),
        },
        "regimes": {
            "cuts": {
                "EARLY": "< 2026-01-01",
                "MIDDLE": "2026-01-01 .. 2026-03-31",
                "LATE": ">= 2026-04-01",
            },
            "original_baseline": A.by_regime(baseline_trades, False),
            "conservative_execution": A.by_regime(cons, False),
        },
        "portfolio": {"original_baseline": ports, "conservative": ports_cons},
        "leakage": leak,
        "live_execution_changed": False,
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    def ledger_row(t):
        f = A.fees_for(t["outcome"], False)
        return {
            "game_id": t.get("game_id"),
            "market_id": t.get("market_id"),
            "event_ticker": t.get("event_ticker"),
            "team": t.get("team"),
            "game_date": t.get("game_date"),
            "dataset_split": t.get("dataset_split"),
            "regime": t.get("regime"),
            "season_phase": t.get("season_phase"),
            "first_80_timestamp": t.get("first_80_timestamp"),
            "first_80_utc": t.get("first_80_utc"),
            "entry_price": 0.80,
            "entry_confidence": t.get("maker_fill_confidence"),
            "stop_triggered": t["outcome"] == "STOP",
            "expiration_result": t.get("expiration_result_yes"),
            "winner_or_stop": t["outcome"],
            "gross_pnl_cents": A.gross_cents(t["outcome"]),
            "scenario": t.get("scenario"),
        }

    (OUT / "ledger_baseline.json").write_text(
        json.dumps([ledger_row(t) for t in baseline_trades]) + "\n"
    )
    (OUT / "ledger_conservative.json").write_text(
        json.dumps([ledger_row(t) for t in cons]) + "\n"
    )
    (OUT / "candidates.json").write_text(json.dumps(cands) + "\n")
    write_report(summary)

    print(
        json.dumps(
            {
                "sport": "ncaab",
                "series": "KXNCAAMBGAME",
                "games": len(cands),
                "first80": len(first),
                "survivors": len(survivors),
                "stops": len(stops),
                "no80": len(no80),
                "win_rate_pct": wr_b,
                "ci95": [lo_b, hi_b],
                "gross_ev_R": s_orig["gross_ev_R"],
                "confidence": dict(conf_counts),
                "out": str(OUT),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
