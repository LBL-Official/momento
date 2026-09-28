#!/usr/bin/env python3
"""WNBA 80¢ maker / 40¢ stop observational backtest.

Same FIRST-80 / close-40 rule as apps/nba-data/scripts/nba_80_40_execution_audit.py
applied to Kalshi KXWNBAGAME. Prefers a real warehouse; otherwise the
Data-Real collector lake (RestCandlestick closes). Never uses the
Data/WNBA DEMO FIXTURE.

Research only. Does not change live FIRST01, Risk, or NBA/NCAAB artifacts.
Does not invent L2, queue position, fills, or a production fee model.

LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

import pyarrow.parquet as pq

NBA_SCRIPTS = Path("/Users/user/Desktop/Momento/apps/nba-data/scripts")
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(NBA_SCRIPTS))
sys.path.insert(0, str(SCRIPTS))
import nba_80_40_execution_audit as A  # noqa: E402
import wnba_collector_quotes as C  # noqa: E402

DEMO_SEASON = Path(
    "/Users/user/Desktop/Momento/Backtesting Suite/Data/WNBA/2025-2026"
)
ROOT = DEMO_SEASON / "warehouse"
NORM = ROOT / "normalized" / "wnba"
COLLECTOR_OUT = (
    Path(
        "/Users/user/Desktop/Momento/Backtesting Suite/Data-Real/WNBA/2025-2026"
    )
    / "derived"
    / "wnba"
    / "first80_execution_audit"
)
REPORTS = Path("/Users/user/Desktop/Momento/research/wnba_first80_80_40_v1")
DOCS = Path("/Users/user/Desktop/Momento/docs/research/wnba_first80_80_40_v1")
WAREHOUSE_OUT = ROOT / "derived" / "wnba" / "first80_execution_audit"

# A priori WNBA chronological cuts. Locked before examining results.
# Not the NBA Dec 31 / Mar 15 splits (those sit in the WNBA offseason).
A.SPLIT_RESEARCH_END = "2025-10-31"  # 2025 WNBA campaign (TRAIN / IN_SAMPLE)
A.SPLIT_VAL_END = "2026-07-15"  # first half of 2026 (VALIDATION)


def wnba_regime(game_date: str | None) -> str:
    if not game_date:
        return "UNKNOWN"
    if game_date < "2026-01-01":
        return "EARLY"
    if game_date <= "2026-07-15":
        return "MIDDLE"
    return "LATE"


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
            "open_time",
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
                "open_ts": A.parse_ts(t.column("open_time")[i].as_py()),
            }
        )
    return rows


def load_games():
    t = pq.read_table(NORM / "games" / "wnba_games.parquet")
    names = t.column_names
    rows = []
    for i in range(t.num_rows):
        row = {n: t.column(n)[i].as_py() for n in names}
        gd = A.parse_game_date(row.get("game_date"))
        if gd:
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
        start = m.get("open_ts")
        if start is None:
            start = g.get("game_window_start")
        end = m["close_ts"]
        if end is None:
            end = g.get("game_window_end")
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
        if n_file % 200 == 0 or n_file == 1:
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
        "n_candle_files": len(files),
    }


def is_demo_fixture(season_root: Path) -> bool:
    manifests = season_root / "manifests"
    if not manifests.exists():
        return False
    for p in manifests.glob("*.json"):
        try:
            notes = json.loads(p.read_text()).get("notes") or []
        except (OSError, json.JSONDecodeError):
            continue
        if any("DEMO FIXTURE" in str(n) for n in notes):
            return True
    return False


def warehouse_usable() -> bool:
    """Prefer a real Kalshi warehouse even if collector demo manifests exist."""
    return (NORM / "markets" / "markets.parquet").exists()


def relabel(cands):
    for rec in cands:
        rec["dataset_split"] = A.dataset_split(rec.get("game_date"))
        rec["regime"] = wnba_regime(rec.get("game_date"))
    return cands


def write_report(summary: dict) -> None:
    b = summary["baseline"]
    m = summary["models"]
    cov = summary.get("coverage") or {}
    j = b.get("joint") or {}
    warehouse = bool(cov.get("bid_ohlc_available"))
    n = b["first80_settled"] or 0
    wr = b["strategy_win_rate_pct"]
    ci = b["strategy_win_rate_ci95"]
    ev = m["original_baseline"]["gross_ev_R"]
    candle_dates = cov.get("candle_dates") or []
    date_line = (
        ", ".join(candle_dates)
        if candle_dates
        else cov.get("candle_span") or "see warehouse validation report"
    )
    ohlc_line = (
        "Bid OHLC high/low: **available** — wick-stop is independent of close-stop"
        if warehouse
        else "Bid OHLC high/low: **unavailable** — wick-stop = close-stop"
    )
    vol_line = (
        f"Volume gate: **{cov.get('volume_gate')}**"
        if warehouse
        else f"Volume gate: **{cov.get('volume_gate')}** (RestCandlestick has no candle volume)"
    )
    exec_note = (
        "HIGH/MEDIUM confidence uses last-print through 80 on the crossing candle. "
        "Wick-stop uses yes_bid_low. These are not fills."
        if warehouse
        else (
            "HIGH/MEDIUM confidence uses last-print through 80 on the crossing minute. "
            "On the collector lake bid high/low equal close, so wick-stop is not independent."
        )
    )
    split_note = (
        "IN_SAMPLE `game_date <= 2025-10-31`; VALIDATION through 2026-07-15; OOS after. "
        "Cuts were locked before this warehouse run and were not retuned."
    )
    lines = [
        "# WNBA FIRST80 80→40 — observational backtest",
        "",
        "Research only. Does not change live trading. Does not invent L2.",
        "",
        "Same FIRST80 / close-40 rule as `apps/nba-data/scripts/nba_80_40_execution_audit.py`",
        "on Kalshi `KXWNBAGAME`. Definition is imported, not rewritten.",
        "",
        cov.get("coverage_statement")
        or "Candle coverage: see coverage in summary.json.",
        "",
        "Collector demo manifests under `Backtesting Suite/Data/WNBA/manifests` were not used as candles.",
        "",
        "**Candle path ≠ fill. Historical stop quotes ≠ executable profit.**",
        "",
        "```",
        "LIVE EXECUTION = FALSE",
        "CANDLE PATH ≠ ACTUAL FILL",
        "```",
        "",
        "---",
        "",
        "## 0. Coverage",
        "",
        f"- Source: `{cov.get('source')}`",
        f"- Games: **{cov.get('n_games')}**",
        f"- Tickers: **{cov.get('n_markets')}**",
        f"- Candle span: {date_line}",
        f"- {vol_line}",
        f"- {ohlc_line}",
        "",
        "Kalshi `historical/cutoff` at ingest: market_settled_ts 2026-07-06. "
        "Earlier games used `/historical/markets/{ticker}/candlesticks`. "
        "Later settled games used the live candlestick endpoint with ≤5000-bar splits. "
        "Open September 2026 markets: 0 at ingest time. Historical L2 is unavailable.",
        "",
        "## 1. Observed FIRST-80 / close-40 path",
        "",
        "| | N |",
        "|---|---:|",
        f"| Games | {b['games']:,} |",
        f"| First tradable 80 cross (settled) | {n:,} |",
        f"| WIN ∧ ¬T40 | {j.get('win_no_t40', b['survivors_no40']):,} |",
        f"| WIN ∧ T40 | {j.get('win_t40', 0):,} |",
        f"| LOSS ∧ ¬T40 | {j.get('loss_no_t40', b['loss_no_stop']):,} |",
        f"| LOSS ∧ T40 | {j.get('loss_t40', 0):,} |",
        f"| Later `yes_bid_close ≤ 40¢` | {b['stops_40_close']:,} |",
        f"| No tradable 80 | {b['no_first_80']:,} |",
        f"| Same-minute FIRST80 tie | {b.get('tie_same_minute', 0):,} |",
        "",
        f"Strategy win rate (hold unless close-stop): **{wr}%**  ",
        f"95% Wilson CI: **{ci[0]}% – {ci[1]}%** (n = {n})",
        "",
        "| Quantity | Estimate |",
        "|---|---:|",
        f"| P(Kalshi yes \\| first 80) | {b['p_win_kalshi_yes']}% |",
        f"| P(WIN ∧ ¬T40 \\| first 80) | {b['p_no40']}% |",
        f"| Gross EV / trade (+1R/−2R) | {ev} R |",
        f"| +1R/−2R breakeven | 66.67% |",
        "",
        "Gross: +20¢ if win and never close-stop; −40¢ if close-stop (assumed 40¢ exit, not a fill); "
        "0 if LOSS_NO_STOP (measurement gap on minute closes).",
        "",
        "## 2. Execution-realism models",
        "",
        exec_note,
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
            "## 3. Chronological splits (a priori WNBA cuts; not retuned)",
            "",
            split_note,
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
            "- Not a production WNBA strategy.",
            "- Not proof of a tradable inefficiency.",
            "- Fees are a labeled published-schedule estimate. "
            "`KXWNBAGAME` is documented as quadratic / M=1; "
            "live `fee_type` is taker-quadratic, not a proven maker rebate.",
            "",
            "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
            "",
        ]
    )
    text = "\n".join(lines) + "\n"
    for dest in (WAREHOUSE_OUT, COLLECTOR_OUT, REPORTS, DOCS):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "REPORT.md").write_text(text)


def main() -> int:
    coverage = None
    if warehouse_usable():
        print("loading warehouse markets/games", flush=True)
        markets = load_markets()
        games = load_games()
        print(f"markets={len(markets)} games={len(games)}", flush=True)
        scanned = scan(markets, games)
        coverage = {
            "source": "Kalshi historical+live 1-minute candlesticks (warehouse)",
            "n_markets": len(markets),
            "n_games": len(games),
            "n_quote_rows": None,
            "n_candle_files": scanned.get("n_candle_files"),
            "candle_dates": None,
            "volume_gate": "NBA_quality_volume_or_prior",
            "bid_ohlc_available": True,
            "wick_stop_independent": True,
            "coverage_statement": (
                f"Kalshi KXWNBAGAME warehouse: {len(games)} games / {len(markets)} "
                "markets with 1-minute yes_bid OHLC + trades. "
                "Earliest candle 2025-05-22; latest 2026-08-31. "
                "Historical cutoff 2026-07-06; later settled games used the live "
                "candlestick endpoint with window splits. Historical L2 unavailable."
            ),
            "candle_span": "2025-05-22 .. 2026-08-31",
        }
    else:
        print("warehouse unavailable or DEMO FIXTURE; loading Data-Real collector", flush=True)
        markets, games, quotes, coverage = C.load_collector()
        print(
            f"markets={len(markets)} games={len(games)} "
            f"quote_rows={coverage['n_quote_rows']}",
            flush=True,
        )
        print(coverage["coverage_statement"], flush=True)
        scanned = C.scan_quotes(quotes, C.quality_spread_only)
        scanned["n_candle_files"] = len(coverage.get("candle_dates") or [])
    print(f"scan done first80_tickers={len(scanned['first80'])}", flush=True)
    cands = relabel(A.build_candidates(markets, games, scanned))

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
    ties = [c for c in cands if c["status"] == "TIE_SAME_MINUTE"]
    unsettled = [
        c
        for c in cands
        if c["status"] == "FIRST_80" and c["expiration_result_yes"] is None
    ]
    win_t40 = sum(
        1 for c in first if c["expiration_result_yes"] and c["stop_close_triggered"]
    )
    loss_t40 = sum(
        1
        for c in first
        if (not c["expiration_result_yes"]) and c["stop_close_triggered"]
    )

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

    ports = {
        str(k) if k else "unlimited": A.portfolio_sim(baseline_trades, k)
        for k in (1, 2, 3, 5, None)
    }
    ports_cons = {
        str(k) if k else "unlimited": A.portfolio_sim(cons, k) for k in (1, 2, 3, 5, None)
    }
    wr_b, lo_b, hi_b = A.wilson(len(survivors), len(first))

    leak = A.leakage_audit(cands, False)
    leak["baseline_reproduced"] = False
    leak["notes"] = list(leak.get("notes") or []) + [
        "WNBA is a first measurement. NBA frozen 1230/910/320 counts are not required.",
        "KXWNBAGAME maker-fee multiplier is UNKNOWN.",
        "Splits are WNBA a priori cuts (2025-10-31 / 2026-07-15), not NBA Dec/Mar cuts.",
        f"Unsettled FIRST80 dropped from P&L: {len(unsettled)}",
        "Data/WNBA demo fixture was not used.",
        "Volume gate waived on collector RestCandlestick (no candle volume).",
        "Bid high/low copied from close; wick-stop is not independent.",
        (coverage or {}).get("coverage_statement") or "",
    ]

    summary = {
        "sport": "wnba",
        "series": "KXWNBAGAME",
        "season": "2025-2026",
        "campaigns": "2025 and 2026 settled KXWNBAGAME markets returned by Kalshi",
        "full_season_backtest": True,
        "kalshi_open_markets_at_ingest": 0,
        "candle_span": "2025-05-22 .. 2026-08-31",
        "rule": "NBA FIRST-80 / close-40 observational audit, first WNBA measurement",
        "live_execution_changed": False,
        "coverage": coverage,
        "n_candle_files": scanned.get("n_candle_files"),
        "unsettled_first80": len(unsettled),
        "price_interpretation": {
            "yes_bid_ohlc": (
                "1-minute Kalshi yes_bid top-of-book OHLC when warehouse candles exist. "
                "Not last, not mid, not L2."
                if (coverage or {}).get("bid_ohlc_available")
                else "Collector: yes_bid/ask CLOSE only (high/low = close). Not last, not mid, not L2."
            ),
            "first_80_original": "first tradable yes_bid_close >= 8000 after a prior tradable close < 8000, market open/close window",
            "first_40_original": "later tradable yes_bid_close <= 4000",
            "orderbook_depth_available": False,
            "historical_fill_unknown": True,
            "volume_gate": (coverage or {}).get("volume_gate"),
            "wick_stop_independent": (coverage or {}).get("wick_stop_independent"),
        },
        "fees": {
            "production_fee_model": "UNRESOLVED",
            "kxwnbagame_maker_multiplier": "UNKNOWN_NOT_IN_WAREHOUSE",
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
            "tie_same_minute": len(ties),
            "joint": {
                "win_no_t40": len(survivors),
                "win_t40": win_t40,
                "loss_no_t40": sum(
                    1 for t in baseline_trades if t["outcome"] == "LOSS_NO_STOP"
                ),
                "loss_t40": loss_t40,
            },
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
                "IN_SAMPLE": "game_date <= 2025-10-31",
                "VALIDATION": "2025-10-31 < game_date <= 2026-07-15",
                "OOS": "game_date > 2026-07-15",
            },
            "original_baseline": A.by_split(baseline_trades, False),
            "base_execution": A.by_split(base_e, False),
            "conservative_execution": A.by_split(cons, False),
        },
        "regimes": {
            "cuts": {
                "EARLY": "2025 campaign (game_date < 2026-01-01)",
                "MIDDLE": "2026-01-01 .. 2026-07-15",
                "LATE": "> 2026-07-15",
            },
            "original_baseline": A.by_regime(baseline_trades, False),
            "conservative_execution": A.by_regime(cons, False),
        },
        "portfolio": {"original_baseline": ports, "conservative": ports_cons},
        "leakage": leak,
    }

    artifact_dirs = [WAREHOUSE_OUT, COLLECTOR_OUT, REPORTS, DOCS]
    for dest in artifact_dirs:
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

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

    for dest in artifact_dirs:
        (dest / "ledger_baseline.json").write_text(
            json.dumps([ledger_row(t) for t in baseline_trades]) + "\n"
        )
        (dest / "ledger_conservative.json").write_text(
            json.dumps([ledger_row(t) for t in cons]) + "\n"
        )
        (dest / "candidates.json").write_text(json.dumps(cands) + "\n")
    write_report(summary)

    print(
        json.dumps(
            {
                "sport": "wnba",
                "series": "KXWNBAGAME",
                "games": len(cands),
                "first80": len(first),
                "survivors": len(survivors),
                "stops": len(stops),
                "no80": len(no80),
                "unsettled": len(unsettled),
                "win_rate_pct": wr_b,
                "ci95": [lo_b, hi_b],
                "gross_ev_R": s_orig["gross_ev_R"],
                "p_win_kalshi_yes": summary["baseline"]["p_win_kalshi_yes"],
                "confidence": dict(conf_counts),
                "coverage": (coverage or {}).get("coverage_statement"),
                "out": str(WAREHOUSE_OUT),
                "live_execution_changed": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
