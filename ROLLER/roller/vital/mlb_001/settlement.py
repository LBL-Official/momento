"""Public Kalshi market settlement for MLB 001. Unsigned GET. Never submits."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from roller.vital.mlb_001.kalshi_observe import kalshi_observe_skipped
from roller.vital.store import execution_settlements_path, read_json, write_json
from roller.vital.versions import BOT_ID

# Official production origin from crates/kalshi REST_PRODUCTION_ORIGIN.
PUBLIC_ORIGIN = "https://external-api.kalshi.com"
MARKETS_PATH = "/trade-api/v2/markets"
HISTORICAL_MARKETS_PATH = "/trade-api/v2/historical/markets"
SKIP_ENV = "VITAL_SKIP_SETTLEMENT"


def settlement_fetch_skipped() -> bool:
    if kalshi_observe_skipped():
        return True
    return (os.environ.get(SKIP_ENV) or "").strip().lower() in {"1", "true", "yes"}


def _dollars_to_cents(raw: Any) -> int | None:
    text = str(raw or "").strip()
    if not text:
        return None
    neg = text.startswith("-")
    if neg:
        text = text[1:]
    if "." in text:
        whole, frac = text.split(".", 1)
    else:
        whole, frac = text, ""
    if whole and not whole.isdigit():
        return None
    frac = (frac + "00")[:2]
    if not frac.isdigit():
        return None
    cents = int(whole or "0") * 100 + int(frac)
    return -cents if neg else cents


def parse_market_settlement(body: dict[str, Any], *, ticker: str) -> dict[str, Any] | None:
    market = body.get("market") if isinstance(body.get("market"), dict) else body
    if not isinstance(market, dict):
        return None
    result = str(market.get("result") or "").strip().lower()
    if result not in {"yes", "no"}:
        return {
            "ticker": ticker,
            "result": None,
            "settlement_value_cents": None,
            "settlement_ts": None,
            "status": "UNSETTLED",
            "source": "kalshi_public_market",
        }
    value = _dollars_to_cents(market.get("settlement_value_dollars"))
    if value is None:
        value = 100 if result == "yes" else 0
    return {
        "ticker": ticker,
        "result": result,
        "settlement_value_cents": value,
        "settlement_ts": market.get("settlement_ts") or market.get("close_time"),
        "status": "CONFIRMED",
        "source": "kalshi_public_market",
    }


def _get_json(url: str) -> dict[str, Any] | None:
    req = urllib.request.Request(url, headers={"User-Agent": "MomentoVital/settlement-observe"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            if getattr(resp, "status", 200) != 200:
                return None
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def fetch_public_settlement(ticker: str) -> dict[str, Any] | None:
    token = str(ticker or "").strip()
    if not token.startswith("KXMLBGAME"):
        return None
    for path in (f"{MARKETS_PATH}/{token}", f"{HISTORICAL_MARKETS_PATH}/{token}"):
        body = _get_json(f"{PUBLIC_ORIGIN}{path}")
        if not body:
            continue
        parsed = parse_market_settlement(body, ticker=token)
        if parsed:
            return parsed
    return None


def load_settlements(bot_id: str = BOT_ID, *, root: Path | None = None) -> dict[str, dict[str, Any]]:
    raw = read_json(execution_settlements_path(bot_id, root=root))
    tickers = (raw or {}).get("tickers") if isinstance(raw, dict) else None
    if not isinstance(tickers, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for key, row in tickers.items():
        if isinstance(row, dict):
            out[str(key)] = row
    return out


def persist_settlements(
    bot_id: str,
    tickers: dict[str, dict[str, Any]],
    *,
    root: Path | None = None,
) -> dict[str, dict[str, Any]]:
    write_json(
        execution_settlements_path(bot_id, root=root),
        {"tickers": tickers, "source": "kalshi_public_market", "read_only": True},
    )
    return tickers


def observe_settlements(
    bot_id: str,
    tickers: list[str],
    *,
    root: Path | None = None,
    fetch: bool = True,
    max_fetch: int | None = 4,
) -> dict[str, dict[str, Any]]:
    """Disk cache first. Public GET only for missing/unsettled tickers."""
    cached = load_settlements(bot_id, root=root)
    wanted = [str(token).strip() for token in tickers if str(token or "").startswith("KXMLBGAME")]
    if not fetch or settlement_fetch_skipped():
        return cached
    changed = False
    fetched_n = 0
    for token in wanted:
        row = cached.get(token)
        if isinstance(row, dict) and row.get("status") == "CONFIRMED" and row.get("result") in {"yes", "no"}:
            continue
        if max_fetch is not None and fetched_n >= max_fetch:
            break
        fetched = fetch_public_settlement(token)
        fetched_n += 1
        if fetched:
            cached[token] = fetched
            changed = True
    if changed:
        persist_settlements(bot_id, cached, root=root)
    return cached
