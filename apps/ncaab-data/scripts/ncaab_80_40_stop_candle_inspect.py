#!/usr/bin/env python3
"""Inspect FIRST-80 close-40 stop candles: range vs 10¢, gap-through-40.

Research only. Does not invent L2 or fills. A 1-minute candle that closes
<= 40¢ does not prove a 40.00 stop fill.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ncaab_80_40_execution_audit as N  # noqa: E402

HIT40 = 4000
TEN_CENTS = 1000  # 10 percentage points on the YES contract
CANDLES = N.NORM / "candles_1m"
CANDS = N.OUT / "candidates.json"
OUT = N.OUT / "stop_candle_inspect"


def load_ticker_candles(ticker: str) -> list[dict]:
    rows = []
    for path in sorted(CANDLES.rglob(f"{ticker}.parquet")):
        t = pq.read_table(
            path,
            columns=[
                "end_period_ts",
                "yes_bid_open_e4",
                "yes_bid_high_e4",
                "yes_bid_low_e4",
                "yes_bid_close_e4",
                "yes_ask_close_e4",
                "price_open_e4",
                "price_high_e4",
                "price_low_e4",
                "price_close_e4",
                "volume_hundredths",
                "is_valid",
            ],
        )
        get = {c: t.column(c) for c in t.column_names}
        for i in range(t.num_rows):
            if not get["is_valid"][i].as_py():
                continue
            rows.append(
                {
                    "ts": int(get["end_period_ts"][i].as_py()),
                    "bid_o": get["yes_bid_open_e4"][i].as_py(),
                    "bid_h": get["yes_bid_high_e4"][i].as_py(),
                    "bid_l": get["yes_bid_low_e4"][i].as_py(),
                    "bid_c": get["yes_bid_close_e4"][i].as_py(),
                    "ask_c": get["yes_ask_close_e4"][i].as_py(),
                    "px_o": get["price_open_e4"][i].as_py(),
                    "px_h": get["price_high_e4"][i].as_py(),
                    "px_l": get["price_low_e4"][i].as_py(),
                    "px_c": get["price_close_e4"][i].as_py(),
                    "vol": get["volume_hundredths"][i].as_py(),
                }
            )
    rows.sort(key=lambda r: r["ts"])
    return rows


def e4(v) -> int | None:
    return None if v is None else int(v)


def rng(a, b) -> int | None:
    if a is None or b is None:
        return None
    return int(a) - int(b)


def pct(n, d):
    if not d:
        return None
    return round(100.0 * n / d, 2)


def inspect_stop(c: dict) -> dict | None:
    ts = c.get("first_40_close_ts")
    ticker = c.get("ticker")
    if ts is None or not ticker:
        return None
    rows = load_ticker_candles(ticker)
    idx = next((i for i, r in enumerate(rows) if r["ts"] == ts), None)
    if idx is None:
        return {"ticker": ticker, "ts": ts, "missing_candle": True}
    q = rows[idx]
    prev = rows[idx - 1] if idx > 0 else None
    bid_range = rng(q["bid_h"], q["bid_l"])
    last_range = rng(q["px_h"], q["px_l"])
    bid_c = e4(q["bid_c"])
    bid_l = e4(q["bid_l"])
    bid_h = e4(q["bid_h"])
    bid_o = e4(q["bid_o"])
    prev_c = e4(prev["bid_c"]) if prev else None
    through_close = None if bid_c is None else HIT40 - bid_c
    through_low = None if bid_l is None else HIT40 - bid_l
    traded_through_40 = (
        bid_h is not None and bid_l is not None and bid_h >= HIT40 >= bid_l
    )
    gapped_below_40 = bid_h is not None and bid_h < HIT40
    jumped_from_above_50 = prev_c is not None and prev_c > 5000 and bid_c is not None and bid_c <= HIT40
    jumped_from_above_55 = prev_c is not None and prev_c > 5500 and bid_c is not None and bid_c <= HIT40
    return {
        "ticker": ticker,
        "event_ticker": c.get("event_ticker"),
        "game_date": c.get("game_date"),
        "stop_ts": ts,
        "stop_utc": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
        "bid_open_e4": bid_o,
        "bid_high_e4": bid_h,
        "bid_low_e4": bid_l,
        "bid_close_e4": bid_c,
        "last_open_e4": e4(q["px_o"]),
        "last_high_e4": e4(q["px_h"]),
        "last_low_e4": e4(q["px_l"]),
        "last_close_e4": e4(q["px_c"]),
        "ask_close_e4": e4(q["ask_c"]),
        "prev_bid_close_e4": prev_c,
        "bid_range_e4": bid_range,
        "last_range_e4": last_range,
        "close_through_40_e4": through_close,
        "low_through_40_e4": through_low,
        "bid_range_gt_10c": bid_range is not None and bid_range > TEN_CENTS,
        "last_range_gt_10c": last_range is not None and last_range > TEN_CENTS,
        "close_through_gt_10c": through_close is not None and through_close > TEN_CENTS,
        "traded_through_40": traded_through_40,
        "gapped_entirely_below_40": gapped_below_40,
        "jumped_from_above_50": jumped_from_above_50,
        "jumped_from_above_55": jumped_from_above_55,
        "missing_candle": False,
    }


def summarize(rows: list[dict]) -> dict:
    ok = [r for r in rows if not r.get("missing_candle")]
    n = len(ok)
    ranges = [r["bid_range_e4"] for r in ok if r["bid_range_e4"] is not None]
    last_ranges = [r["last_range_e4"] for r in ok if r["last_range_e4"] is not None]
    through = [r["close_through_40_e4"] for r in ok if r["close_through_40_e4"] is not None]
    lows = [r["low_through_40_e4"] for r in ok if r["low_through_40_e4"] is not None]

    def dist(vals):
        if not vals:
            return None
        s = sorted(vals)
        def q(p):
            return s[min(len(s) - 1, int(round((len(s) - 1) * p)))]
        return {
            "n": len(s),
            "min_cents": round(s[0] / 100, 2),
            "p25_cents": round(q(0.25) / 100, 2),
            "median_cents": round(q(0.5) / 100, 2),
            "p75_cents": round(q(0.75) / 100, 2),
            "p90_cents": round(q(0.9) / 100, 2),
            "max_cents": round(s[-1] / 100, 2),
            "mean_cents": round((sum(s) / len(s)) / 100, 2),
        }

    buckets = Counter()
    for r in ok:
        br = r["bid_range_e4"]
        if br is None:
            buckets["unknown"] += 1
        elif br <= 200:
            buckets["0-2c"] += 1
        elif br <= 500:
            buckets["2-5c"] += 1
        elif br <= 1000:
            buckets["5-10c"] += 1
        elif br <= 2000:
            buckets["10-20c"] += 1
        else:
            buckets[">20c"] += 1

    return {
        "stop_close_trades": n,
        "missing_stop_candle": sum(1 for r in rows if r.get("missing_candle")),
        "bid_range_gt_10c": sum(1 for r in ok if r["bid_range_gt_10c"]),
        "bid_range_gt_10c_pct": pct(sum(1 for r in ok if r["bid_range_gt_10c"]), n),
        "last_range_gt_10c": sum(1 for r in ok if r["last_range_gt_10c"]),
        "last_range_gt_10c_pct": pct(sum(1 for r in ok if r["last_range_gt_10c"]), n),
        "close_finished_more_than_10c_through_40": sum(1 for r in ok if r["close_through_gt_10c"]),
        "traded_through_40_in_minute": sum(1 for r in ok if r["traded_through_40"]),
        "traded_through_40_pct": pct(sum(1 for r in ok if r["traded_through_40"]), n),
        "gapped_entirely_below_40": sum(1 for r in ok if r["gapped_entirely_below_40"]),
        "gapped_entirely_below_40_pct": pct(sum(1 for r in ok if r["gapped_entirely_below_40"]), n),
        "prior_close_above_50_then_close_40": sum(1 for r in ok if r["jumped_from_above_50"]),
        "prior_close_above_55_then_close_40": sum(1 for r in ok if r["jumped_from_above_55"]),
        "bid_range_cents": dist(ranges),
        "last_range_cents": dist(last_ranges),
        "close_through_40_cents": dist(through),
        "low_through_40_cents": dist(lows),
        "bid_range_buckets": dict(buckets),
    }


def write_report(s: dict) -> None:
    lines = [
        "# NCAAB 80/40 stop-candle inspection",
        "",
        "Universe: settled FIRST-80 trades whose first later tradable",
        "`yes_bid_close ≤ 40¢` is the baseline stop. 1-minute TOB candles only.",
        "**Not a fill.** L2 unavailable.",
        "",
        f"Stop candles found: {s['stop_close_trades']:,} "
        f"(missing {s['missing_stop_candle']})",
        "",
        "## How many stop minutes were bigger than 10¢ (10%)?",
        "",
        f"- Bid range (high−low) > 10¢: **{s['bid_range_gt_10c']:,}** "
        f"({s['bid_range_gt_10c_pct']}%)",
        f"- Last-trade range > 10¢: **{s['last_range_gt_10c']:,}** "
        f"({s['last_range_gt_10c_pct']}%)",
        f"- Close finished more than 10¢ through 40 (close ≤ 30¢): "
        f"**{s['close_finished_more_than_10c_through_40']:,}**",
        "",
        "Bid-range buckets:",
        "",
    ]
    for k in ("0-2c", "2-5c", "5-10c", "10-20c", ">20c", "unknown"):
        if k in s["bid_range_buckets"]:
            lines.append(f"- {k}: {s['bid_range_buckets'][k]:,}")
    br = s["bid_range_cents"] or {}
    lines.extend(
        [
            "",
            f"Bid range median {br.get('median_cents')}¢ "
            f"(p90 {br.get('p90_cents')}¢, max {br.get('max_cents')}¢).",
            "",
            "## Could an algorithm have sold at exactly 40?",
            "",
            f"- Bid high/low straddled 40 in that minute: "
            f"**{s['traded_through_40_in_minute']:,}** ({s['traded_through_40_pct']}%). "
            "The bid *passed* 40. That is not your fill.",
            f"- Entire minute already below 40 (high < 40): "
            f"**{s['gapped_entirely_below_40']:,}** ({s['gapped_entirely_below_40_pct']}%). "
            "No 40 print on the bid that minute.",
            f"- Prior minute close > 50¢, this close ≤ 40¢: "
            f"**{s['prior_close_above_50_then_close_40']:,}**",
            f"- Prior minute close > 55¢, this close ≤ 40¢: "
            f"**{s['prior_close_above_55_then_close_40']:,}**",
            "",
            "Close-through-40 (40 − close) median "
            f"{(s['close_through_40_cents'] or {}).get('median_cents')}¢; "
            "low-through-40 median "
            f"{(s['low_through_40_cents'] or {}).get('median_cents')}¢.",
            "",
            "Execution implication:",
            "",
            "1. A **resting maker sell at 40** fills only if a buyer lifts 40.",
            "   On a crash, buyers do not have to lift 40; the bid can gap through.",
            "2. A **stop-market / reduce-only IOC when bid ≤ 40** sells at the",
            "   then-available bid, which this candle may already show as 39, 30, or lower.",
            "3. Candles cannot prove queue position. Historical L2 is NOT AVAILABLE.",
            "4. The backtest's −40¢ / −2R assumes a 40.00 fill. Wide or gapped",
            "   stop minutes mean that assumption is **optimistic**.",
            "",
        ]
    )
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n")


def main() -> int:
    cands = json.loads(CANDS.read_text())
    stops = [
        c
        for c in cands
        if c.get("status") == "FIRST_80"
        and c.get("stop_close_triggered")
        and c.get("expiration_result_yes") is not None
    ]
    print(f"stop trades={len(stops)}", flush=True)
    rows = []
    for i, c in enumerate(stops, 1):
        if i % 100 == 0 or i == 1:
            print(f"inspect {i}/{len(stops)}", flush=True)
        row = inspect_stop(c)
        if row:
            rows.append(row)
    s = summarize(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(s, indent=2) + "\n")
    (OUT / "stop_candles.json").write_text(json.dumps(rows) + "\n")
    write_report(s)
    print(json.dumps(s, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
