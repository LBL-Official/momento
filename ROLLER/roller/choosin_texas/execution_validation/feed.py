"""Unsigned public REST collection for the paired observation spec.

Records quotes, depth, trades, and candle closes. Does not send orders.
Does not score fills or returns. A hypothetical 80 cent intent is written
only for a minute close that arrives while the collector is already running.
"""

from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from roller.choosin_texas.execution_validation.prospective import (
    install_observation_spec,
    prospective_dir,
)
from roller.choosin_texas.models import ChoosinTexasError

PUBLIC_ORIGIN = "https://external-api.kalshi.com"
SERIES = ("KXNBAGAME", "KXNCAAMBGAME")
Get = Callable[[str], tuple[Any, str]]


def public_request_headers() -> dict[str, str]:
    return {"Accept": "application/json"}


def dollars_to_cents(value: Any) -> int | None:
    if value in (None, ""):
        return None
    cents = Decimal(str(value)) * 100
    if cents != cents.to_integral_value():
        return None
    return int(cents)


def public_get(path: str) -> tuple[Any, str]:
    headers = public_request_headers()
    if "Authorization" in headers:
        raise ChoosinTexasError("LOCK_MISMATCH", "public collection must not send credentials")
    request = urllib.request.Request(PUBLIC_ORIGIN + path, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
    received = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return json.loads(raw.decode("utf-8")), received


def _append(root: Path, name: str, row: dict[str, Any]) -> None:
    folder = root / "market_data"
    folder.mkdir(parents=True, exist_ok=True)
    row["simulated_fills"] = "BLOCKED"
    row["portfolio_pnl"] = "NOT_REPORTED"
    row["fill_label"] = None
    row["sent"] = False
    with (folder / f"{name}.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def _quote_row(market: dict[str, Any], received_ts: str) -> dict[str, Any]:
    return {
        "record_kind": "QUOTE",
        "instrument": market.get("ticker"),
        "event_ticker": market.get("event_ticker"),
        "status": market.get("status"),
        "exchange_ts": market.get("updated_time"),
        "received_ts": received_ts,
        "yes_bid_cents": dollars_to_cents(market.get("yes_bid_dollars")),
        "yes_ask_cents": dollars_to_cents(market.get("yes_ask_dollars")),
        "yes_bid_size_fp": market.get("yes_bid_size_fp"),
        "yes_ask_size_fp": market.get("yes_ask_size_fp"),
        "last_price_cents": dollars_to_cents(market.get("last_price_dollars")),
        "sequence": None,
        "feed_continuity": "REST_SNAPSHOT_NOT_A_SEQUENCE",
        "evidence_level": "OBSERVED_MARKET_DATA",
    }


def _new_candle_intents(
    candles: list[dict[str, Any]],
    *,
    watermark: int | None,
    received_ts: str,
    instrument: str,
) -> tuple[list[dict[str, Any]], int | None]:
    """Intent only for a close that is new since the previous poll."""
    ordered: list[tuple[int, int | None]] = []
    for row in candles:
        end = row.get("end_period_ts")
        if end is None:
            continue
        bid = None
        yes_bid = row.get("yes_bid")
        if isinstance(yes_bid, dict):
            bid = dollars_to_cents(yes_bid.get("close_dollars"))
        ordered.append((int(end), bid))
    ordered.sort()
    if not ordered:
        return [], watermark
    newest = ordered[-1][0]
    if watermark is None:
        return [], newest
    intents: list[dict[str, Any]] = []
    previous: int | None = None
    for end, bid in ordered:
        if previous is not None and end > watermark and bid is not None and previous < 80 <= bid:
            if received_ts >= datetime.fromtimestamp(end, tz=timezone.utc).isoformat():
                intents.append(
                    {
                        "record_kind": "HYPOTHETICAL_ORDER_INTENT",
                        "instrument": instrument,
                        "trigger": "CANDLE_CLOSE",
                        "signal": "ENTRY",
                        "exchange_ts": datetime.fromtimestamp(end, tz=timezone.utc).isoformat(),
                        "received_ts": received_ts,
                        "yes_bid_cents": bid,
                        "price_cents": 80,
                        "post_only": True,
                        "sent": False,
                        "entry_rest": "POLICY_UNRESOLVED",
                        "entry_cancel": "POLICY_UNRESOLVED",
                        "evidence_level": "OBSERVED_MARKET_DATA",
                    }
                )
        if bid is not None:
            previous = bid
    return intents, max(watermark, newest)


def poll_once(dest: Path | None = None, *, get: Get = public_get) -> dict[str, Any]:
    root = dest or prospective_dir()
    install_observation_spec(root)
    state_path = root / "collector_state.json"
    state: dict[str, Any] = {}
    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    watermarks = dict(state.get("candle_watermarks") or {})
    records = 0
    markets_seen = 0
    for series in SERIES:
        payload, received = get(f"/trade-api/v2/markets?series_ticker={series}&status=open&limit=200")
        markets = payload.get("markets") or []
        markets_seen += len(markets)
        _append(
            root,
            f"catalog_{series}",
            {
                "record_kind": "CATALOG",
                "series": series,
                "received_ts": received,
                "exchange_ts": None,
                "open_markets": len(markets),
                "cursor_present": bool(payload.get("cursor")),
                "evidence_level": "OBSERVED_MARKET_DATA",
            },
        )
        records += 1
        for market in markets:
            ticker = str(market.get("ticker") or "")
            if not ticker:
                continue
            _append(root, ticker, _quote_row(market, received))
            records += 1
            book, book_received = get(f"/trade-api/v2/markets/{ticker}/orderbook?depth=10")
            _append(
                root,
                ticker,
                {
                    "record_kind": "ORDER_BOOK",
                    "instrument": ticker,
                    "received_ts": book_received,
                    "exchange_ts": None,
                    "orderbook_fp": book.get("orderbook_fp"),
                    "sequence": None,
                    "feed_continuity": "REST_SNAPSHOT_NOT_A_SEQUENCE",
                    "evidence_level": "OBSERVED_MARKET_DATA",
                },
            )
            records += 1
            trades, trade_received = get(f"/trade-api/v2/markets/trades?ticker={ticker}&limit=20")
            _append(
                root,
                ticker,
                {
                    "record_kind": "PUBLIC_TRADES",
                    "instrument": ticker,
                    "received_ts": trade_received,
                    "trades": trades.get("trades") or [],
                    "cursor_present": bool(trades.get("cursor")),
                    "sequence": None,
                    "evidence_level": "OBSERVED_MARKET_DATA",
                },
            )
            records += 1
            end = int(datetime.now(timezone.utc).timestamp())
            start = end - 3600
            candles, candle_received = get(
                f"/trade-api/v2/series/{series}/markets/{ticker}/candlesticks"
                f"?start_ts={start}&end_ts={end}&period_interval=1"
            )
            rows = candles.get("candlesticks") or []
            _append(
                root,
                ticker,
                {
                    "record_kind": "CANDLE",
                    "instrument": ticker,
                    "received_ts": candle_received,
                    "window_start_ts": start,
                    "window_end_ts": end,
                    "candlesticks": rows,
                    "coverage": "EMPTY_WINDOW" if not rows else "PRESENT",
                    "evidence_level": "OBSERVED_MARKET_DATA",
                },
            )
            records += 1
            intents, watermark = _new_candle_intents(
                rows,
                watermark=watermarks.get(ticker),
                received_ts=candle_received,
                instrument=ticker,
            )
            watermarks[ticker] = watermark
            for intent in intents:
                _append(root, ticker, intent)
                records += 1
    received_now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    new_state = {
        "feed": "REST_PUBLIC",
        "websocket": "NOT_STARTED",
        "credentials_read": False,
        "submits": False,
        "simulated_fills": "BLOCKED",
        "return_calculation": "BLOCKED",
        "last_poll_received_ts": received_now,
        "markets_seen": markets_seen,
        "records_this_poll": records,
        "candle_watermarks": watermarks,
        "last_error": None,
    }
    state_path.write_text(json.dumps(new_state, indent=2) + "\n", encoding="utf-8")
    return new_state


def run_collector(interval_seconds: int = 60) -> None:
    if interval_seconds <= 0:
        raise ChoosinTexasError("LOCK_MISMATCH", "poll interval must be positive")
    while True:
        try:
            poll_once()
        except Exception as exc:  # noqa: BLE001 — keep the public poll alive and visible
            root = prospective_dir()
            root.mkdir(parents=True, exist_ok=True)
            path = root / "collector_state.json"
            prior: dict[str, Any] = {}
            if path.is_file():
                prior = json.loads(path.read_text(encoding="utf-8"))
            prior.update(
                {
                    "feed": "REST_PUBLIC",
                    "websocket": "NOT_STARTED",
                    "credentials_read": False,
                    "submits": False,
                    "simulated_fills": "BLOCKED",
                    "return_calculation": "BLOCKED",
                    "last_poll_received_ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                    "last_error": f"{type(exc).__name__}: {exc}",
                }
            )
            path.write_text(json.dumps(prior, indent=2) + "\n", encoding="utf-8")
        time.sleep(interval_seconds)
