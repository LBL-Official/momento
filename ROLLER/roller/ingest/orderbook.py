"""Official Kalshi orderbook snapshot client.

Forward-only. Does not invent historical L2. Does not submit orders.
Public GET /trade-api/v2/markets/{ticker}/orderbook is bids-only;
best YES is the last yes_dollars level.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

KALSHI_REST = "https://external-api.kalshi.com/trade-api/v2"
SERIES = {
    "NBA": "KXNBAGAME",
    "NCAAB": "KXNCAAMBGAME",
    "MLB": "KXMLBGAME",
}


def dollars_to_e4(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(round(float(value) * 10000))
    except (TypeError, ValueError):
        return None


def parse_orderbook_payload(payload: dict[str, Any]) -> dict[str, Any]:
    book = payload.get("orderbook_fp") or payload.get("orderbook") or payload
    yes = list(book.get("yes_dollars") or [])
    no = list(book.get("no_dollars") or [])
    best_yes = yes[-1] if yes else None
    best_no = no[-1] if no else None
    yes_px = dollars_to_e4(best_yes[0]) if best_yes else None
    no_px = dollars_to_e4(best_no[0]) if best_no else None
    return {
        "yes_levels": len(yes),
        "no_levels": len(no),
        "best_yes_bid_e4": "" if yes_px is None else str(yes_px),
        "best_no_bid_e4": "" if no_px is None else str(no_px),
        "yes_dollars_json": json.dumps(yes, separators=(",", ":")),
        "no_dollars_json": json.dumps(no, separators=(",", ":")),
        "market_data_type": "ORDERBOOK_SNAPSHOT",
        "note": "official bids-only snapshot; not a fill; not historical L2",
    }


def _request(path: str, timeout: float = 20.0) -> dict[str, Any]:
    url = f"{KALSHI_REST}{path}"
    req = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Kalshi GET {path} HTTP {exc.code}: {body[:200]}") from exc


def list_open_markets(series_ticker: str, *, cursor: str | None = None, limit: int = 200) -> dict[str, Any]:
    q = {"series_ticker": series_ticker, "status": "open", "limit": str(limit)}
    if cursor:
        q["cursor"] = cursor
    return _request("/markets?" + urllib.parse.urlencode(q))


def get_orderbook(ticker: str, depth: int | None = None) -> dict[str, Any]:
    path = f"/markets/{urllib.parse.quote(ticker)}/orderbook"
    if depth is not None:
        path += "?" + urllib.parse.urlencode({"depth": str(depth)})
    return _request(path)


def iter_open_tickers(series_ticker: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    cursor = None
    for _ in range(50):
        payload = list_open_markets(series_ticker, cursor=cursor)
        markets = payload.get("markets") or []
        out.extend(markets)
        cursor = payload.get("cursor") or payload.get("next_cursor")
        if not cursor or not markets:
            break
        time.sleep(0.05)
    return out


def env_has_kalshi_creds() -> bool:
    return bool(os.environ.get("MOMENTO_KALSHI_API_KEY_ID") and os.environ.get("MOMENTO_KALSHI_PRIVATE_KEY_PATH"))
