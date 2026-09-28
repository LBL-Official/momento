"""Load WNBA RestCandlestick closes from Data-Real collector lake.

Not L2. Bid/ask close only (no candle high/low, no volume).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq

DATA_REAL = Path(
    "/Users/user/Desktop/Momento/Backtesting Suite/Data-Real/WNBA/2025-2026"
)

MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


def cents_to_e4(c):
    if c is None:
        return None
    return int(c) * 100


def game_date_from_event(event_ticker: str) -> str | None:
    rest = event_ticker.removeprefix("KXWNBAGAME-")
    if len(rest) < 7:
        return None
    yy = rest[0:2]
    mon = rest[2:5]
    dd = rest[5:7]
    month = MONTHS.get(mon)
    if month is None:
        return None
    try:
        return f"20{yy}-{month:02d}-{int(dd):02d}"
    except ValueError:
        return None


def parse_ts(s):
    if not s:
        return None
    s = str(s).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def quality_spread_only(bid, ask, _vol, _had_quality):
    """Volume is not stored on RestCandlestick rows. Spread-only gate."""
    if bid is None or ask is None:
        return False
    if bid > ask:
        return False
    if ask - bid > 1000:
        return False
    return True


def load_collector():
    markets_by_ticker = {}
    games_by_event = {}
    quotes = defaultdict(list)
    dropped = {
        "empty_orderbook_days": 0,
        "non_candle_rows": 0,
        "duplicate_tickers": 0,
        "days_with_candles": 0,
        "days_without_candles": 0,
    }

    for day in sorted((DATA_REAL / "orderbook").glob("date=*")):
        meta_p = day / "metadata.parquet"
        ob_p = day / "orderbook.parquet"
        n_ob = 0
        if ob_p.exists():
            n_ob = pq.read_table(ob_p, columns=["event_type"]).num_rows
        if n_ob == 0:
            dropped["days_without_candles"] += 1
            dropped["empty_orderbook_days"] += 1
        else:
            dropped["days_with_candles"] += 1

        if meta_p.exists():
            mt = pq.read_table(meta_p)
            n = mt.num_rows
            if n:
                cols = {c: mt.column(c) for c in mt.column_names}
                for i in range(n):
                    ticker = cols["ticker"][i].as_py()
                    event_id = cols["event_ticker"][i].as_py()
                    rec = {
                        "ticker": ticker,
                        "event_id": event_id,
                        "market_id": cols["market_id"][i].as_py(),
                        "team": ticker.rsplit("-", 1)[-1] if ticker else None,
                        "result": cols["result"][i].as_py(),
                        "settlement_value_e4": None,
                        "season_phase": "UNKNOWN",
                        "close_ts": parse_ts(cols["close_time"][i].as_py()),
                        "open_ts": parse_ts(cols["open_time"][i].as_py()),
                        "status": cols["status"][i].as_py(),
                    }
                    if ticker in markets_by_ticker:
                        dropped["duplicate_tickers"] += 1
                    markets_by_ticker[ticker] = rec
                    gd = game_date_from_event(event_id or "")
                    g = games_by_event.setdefault(
                        event_id,
                        {
                            "event_id": event_id,
                            "game_id": cols["game_id"][i].as_py(),
                            "event_ticker": event_id,
                            "game_date": gd,
                            "season_phase": "UNKNOWN",
                            "home_team": None,
                            "away_team": None,
                            "game_window_start": rec["open_ts"],
                            "game_window_end": rec["close_ts"],
                        },
                    )
                    if rec["open_ts"] is not None:
                        prev = g.get("game_window_start")
                        g["game_window_start"] = rec["open_ts"] if prev is None else min(prev, rec["open_ts"])
                    if rec["close_ts"] is not None:
                        prev = g.get("game_window_end")
                        g["game_window_end"] = rec["close_ts"] if prev is None else max(prev, rec["close_ts"])

        if not ob_p.exists() or n_ob == 0:
            continue
        ot = pq.read_table(
            ob_p,
            columns=[
                "ticker",
                "exchange_timestamp_ms",
                "event_type",
                "yes_bid_cents",
                "yes_ask_cents",
            ],
        )
        get = {c: ot.column(c) for c in ot.column_names}
        for i in range(ot.num_rows):
            if get["event_type"][i].as_py() != "candlestick_close":
                dropped["non_candle_rows"] += 1
                continue
            ticker = get["ticker"][i].as_py()
            ms = get["exchange_timestamp_ms"][i].as_py()
            if ms is None:
                continue
            ts = int(ms) // 1000
            bid = cents_to_e4(get["yes_bid_cents"][i].as_py())
            ask = cents_to_e4(get["yes_ask_cents"][i].as_py())
            quotes[ticker].append(
                {
                    "ts": ts,
                    "bid_o": bid,
                    "bid_h": bid,
                    "bid_l": bid,
                    "bid_c": bid,
                    "ask_o": ask,
                    "ask_h": ask,
                    "ask_l": ask,
                    "ask_c": ask,
                    "px_o": None,
                    "px_h": None,
                    "px_l": None,
                    "px_c": None,
                    "vol": None,
                    "ohlc_available": False,
                    "volume_available": False,
                }
            )

    wanted = set(quotes)
    trade_minutes = defaultdict(
        lambda: defaultdict(lambda: {"lo": None, "hi": None, "n": 0, "qty": 0})
    )
    for tp in sorted((DATA_REAL / "trades").glob("date=*/trades.parquet")):
        if pq.read_table(tp, columns=["ticker"]).num_rows == 0:
            continue
        tt = pq.read_table(
            tp,
            columns=[
                "ticker",
                "exchange_timestamp",
                "yes_price_cents",
                "quantity_hundredths",
            ],
        )
        get = {c: tt.column(c) for c in tt.column_names}
        for i in range(tt.num_rows):
            ticker = get["ticker"][i].as_py()
            if ticker not in wanted:
                continue
            ts = parse_ts(get["exchange_timestamp"][i].as_py())
            if ts is None:
                continue
            minute = ts - (ts % 60)
            px = cents_to_e4(get["yes_price_cents"][i].as_py())
            if px is None:
                continue
            rec = trade_minutes[ticker][minute]
            rec["n"] += 1
            qty = get["quantity_hundredths"][i].as_py()
            rec["qty"] += 0 if qty is None else int(qty)
            rec["lo"] = px if rec["lo"] is None else min(rec["lo"], px)
            rec["hi"] = px if rec["hi"] is None else max(rec["hi"], px)

    for ticker, rows in quotes.items():
        rows.sort(key=lambda r: r["ts"])
        tm = trade_minutes.get(ticker, {})
        for q in rows:
            minute = q["ts"] - (q["ts"] % 60)
            # RestCandlestick timestamp is treated as period end.
            tr = tm.get(minute - 60) or tm.get(minute)
            if tr:
                q["px_l"] = tr["lo"]
                q["px_h"] = tr["hi"]
                q["px_c"] = tr["hi"]
                q["vol"] = tr["qty"]

    windowed = defaultdict(list)
    dropped["out_of_window"] = 0
    dropped["duplicate_ts"] = 0
    for ticker, rows in quotes.items():
        m = markets_by_ticker.get(ticker) or {}
        start = m.get("open_ts")
        end = m.get("close_ts")
        seen = set()
        for q in rows:
            if start is not None and q["ts"] < start:
                dropped["out_of_window"] += 1
                continue
            if end is not None and q["ts"] > end:
                dropped["out_of_window"] += 1
                continue
            if q["ts"] in seen:
                dropped["duplicate_ts"] += 1
                continue
            seen.add(q["ts"])
            windowed[ticker].append(q)
    quotes = windowed

    candle_dates = sorted(
        p.name.removeprefix("date=")
        for p in (DATA_REAL / "orderbook").glob("date=*")
        if (p / "orderbook.parquet").exists()
        and pq.read_table(p / "orderbook.parquet", columns=["event_type"]).num_rows > 0
    )
    game_dates = sorted(
        {g["game_date"] for g in games_by_event.values() if g.get("game_date")}
    )

    markets = list(markets_by_ticker.values())
    games = list(games_by_event.values())
    meta = {
        "source": "Data-Real collector RestCandlestick",
        "lake": str(DATA_REAL),
        "n_markets": len(markets),
        "n_games": len(games),
        "n_tickers_with_quotes": len(quotes),
        "n_quote_rows": sum(len(v) for v in quotes.values()),
        "candle_dates": candle_dates,
        "game_dates": game_dates,
        "coverage_statement": (
            "Usable 1-minute yes_bid/yes_ask closes exist only for "
            f"{candle_dates[0] if candle_dates else 'none'} through "
            f"{candle_dates[-1] if candle_dates else 'none'} "
            f"({len(games)} settled games). 2025 campaign candles: 0. "
            "Not a full 2025–2026 WNBA season."
        ),
        "dropped": dropped,
        "volume_gate": "WAIVED_SPREAD_ONLY",
        "bid_ohlc_available": False,
        "wick_stop_independent": False,
        "limitations": [
            "yes_bid/ask CLOSE only — high/low set equal to close",
            "NBA quality() volume gate waived; RestCandlestick has no candle volume",
            "last-trade minute OHLC used only for maker-fill confidence, not for FIRST80",
            "not a full 2025 and 2026 WNBA season",
            "Kalshi live ingest from this laptop was connection-refused",
            "Backtesting Suite/Data/WNBA is a DEMO FIXTURE and was not used",
        ],
    }
    return markets, games, quotes, meta


def scan_quotes(quotes, quality_fn):
    first80 = {}
    first40_close = {}
    first40_low = {}
    first39_close = {}
    first38_close = {}
    subsequent_80 = {}
    HIT80, HIT40, HIT39, HIT38 = 8000, 4000, 3900, 3800
    for ticker, rows in quotes.items():
        rows = sorted(rows, key=lambda r: r["ts"])
        had_q = False
        seen_below_80 = False
        f80 = None
        for q in rows:
            if not quality_fn(q["bid_c"], q["ask_c"], q["vol"], had_q):
                continue
            had_q = True
            if q["bid_c"] < HIT80:
                seen_below_80 = True
            if f80 is None and q["bid_c"] >= HIT80 and seen_below_80:
                f80 = q
                first80[ticker] = q
        if not f80:
            continue
        n80 = 0
        for q in rows:
            if q["ts"] <= f80["ts"]:
                continue
            if not quality_fn(q["bid_c"], q["ask_c"], q["vol"], True):
                continue
            if q["bid_c"] >= HIT80:
                n80 += 1
            if ticker not in first40_close and q["bid_c"] <= HIT40:
                first40_close[ticker] = q
            if ticker not in first39_close and q["bid_c"] <= HIT39:
                first39_close[ticker] = q
            if ticker not in first38_close and q["bid_c"] <= HIT38:
                first38_close[ticker] = q
            if ticker not in first40_low and q["bid_l"] is not None and q["bid_l"] <= HIT40:
                first40_low[ticker] = q
        subsequent_80[ticker] = n80
        if (
            ticker not in first40_low
            and f80["bid_l"] is not None
            and f80["bid_l"] <= HIT40
        ):
            first40_low[ticker] = f80
    return {
        "first80": first80,
        "first40_close": first40_close,
        "first40_low": first40_low,
        "first39_close": first39_close,
        "first38_close": first38_close,
        "subsequent_80": subsequent_80,
        "meta": {},
    }
