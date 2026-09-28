"""Observational yes-bid candle SVG. Candle path ≠ fill. Missing = DATA_REQUIRED."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from roller.jump.catalog.kalshi import fetch_candles
from roller.jump.catalog.store import load_chart, write_chart
from roller.jump.dashboard.ledger import parse_utc

CHART_HALF_WINDOW_S = 90 * 60
WIDTH = 640
HEIGHT = 160
PAD = 12


def _looks_like_ticker(raw: str | None) -> bool:
    text = str(raw or "").strip()
    if len(text) < 4 or text.isdigit():
        return False
    return any(ch.isalpha() for ch in text)


def render_yes_bid_svg(
    candles: list[dict[str, Any]],
    *,
    fill_ts: datetime | None,
    ticker: str,
) -> str | None:
    bars: list[dict[str, int]] = []
    for row in candles:
        try:
            end_ts = int(row.get("end_period_ts"))
            close = row.get("close_cents")
            high = row.get("high_cents")
            low = row.get("low_cents")
            open_c = row.get("open_cents")
            if close is None or high is None or low is None or open_c is None:
                continue
            bars.append(
                {
                    "end_period_ts": end_ts,
                    "open": int(open_c),
                    "high": int(high),
                    "low": int(low),
                    "close": int(close),
                }
            )
        except (TypeError, ValueError):
            continue
    if not bars:
        return None
    lows = [b["low"] for b in bars]
    highs = [b["high"] for b in bars]
    lo = min(lows)
    hi = max(highs)
    if hi <= lo:
        hi = lo + 1
    inner_w = WIDTH - 2 * PAD
    inner_h = HEIGHT - 2 * PAD
    n = len(bars)
    step = inner_w / n
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="Yes-bid candles around fill">',
        '<rect width="100%" height="100%" fill="#111111"/>',
        f'<text x="{PAD}" y="14" fill="#f4f4f4" font-size="10">{_xml(ticker)} yes-bid · candle path ≠ fill</text>',
    ]
    fill_x: float | None = None
    fill_unix = int(fill_ts.timestamp()) if fill_ts is not None else None
    for i, bar in enumerate(bars):
        x = PAD + i * step + step / 2
        def y(cents: int) -> float:
            return PAD + 8 + (hi - cents) * (inner_h - 16) / (hi - lo)
        y_h = y(bar["high"])
        y_l = y(bar["low"])
        y_o = y(bar["open"])
        y_c = y(bar["close"])
        color = "#c45d6e" if bar["close"] < bar["open"] else "#d7d7d7"
        parts.append(
            f'<line x1="{x:.1f}" y1="{y_h:.1f}" x2="{x:.1f}" y2="{y_l:.1f}" stroke="{color}" stroke-width="1"/>'
        )
        top = min(y_o, y_c)
        h = max(abs(y_c - y_o), 1.0)
        parts.append(
            f'<rect x="{x - max(step * 0.3, 1):.1f}" y="{top:.1f}" width="{max(step * 0.6, 1):.1f}" height="{h:.1f}" fill="{color}"/>'
        )
        if fill_unix is not None:
            if i == 0 and fill_unix <= bar["end_period_ts"]:
                fill_x = x
            elif i + 1 < n and bars[i]["end_period_ts"] <= fill_unix < bars[i + 1]["end_period_ts"]:
                fill_x = x
            elif i == n - 1 and fill_unix >= bar["end_period_ts"]:
                fill_x = x
    if fill_x is not None:
        parts.append(
            f'<line x1="{fill_x:.1f}" y1="{PAD}" x2="{fill_x:.1f}" y2="{HEIGHT - 4}" stroke="#a24857" stroke-width="1.5" stroke-dasharray="3 2"/>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def chart_for_trade(row: dict[str, Any], *, root=None, fetch: bool = True) -> dict[str, Any]:
    tid = str(row.get("jump_trade_id") or "")
    cached = load_chart(tid, root=root) if tid else None
    if cached:
        return {
            "status": "CONFIRMED",
            "svg": cached,
            "caption": "Candle path ≠ fill. L2/tick = DATA_REQUIRED.",
        }
    ticker = str(row.get("ticker") or "")
    if not _looks_like_ticker(ticker):
        return {"status": "DATA_REQUIRED", "svg": None, "caption": "DATA_REQUIRED"}
    ts = parse_utc(row.get("exchange_ts"))
    if ts is None or not fetch:
        return {"status": "DATA_REQUIRED", "svg": None, "caption": "DATA_REQUIRED"}
    start = int(ts.replace(tzinfo=ts.tzinfo or timezone.utc).timestamp()) - CHART_HALF_WINDOW_S
    end = int(ts.timestamp()) + CHART_HALF_WINDOW_S
    pulled = fetch_candles(ticker, start, end, environment=str(row.get("environment") or "PRODUCTION"))
    if not pulled.get("ok"):
        return {"status": "DATA_REQUIRED", "svg": None, "caption": "DATA_REQUIRED"}
    svg = render_yes_bid_svg(pulled.get("candles") or [], fill_ts=ts, ticker=ticker)
    if not svg:
        return {"status": "DATA_REQUIRED", "svg": None, "caption": "DATA_REQUIRED"}
    if tid:
        write_chart(tid, svg, root=root)
    return {
        "status": "CONFIRMED",
        "svg": svg,
        "caption": "Candle path ≠ fill. L2/tick = DATA_REQUIRED.",
    }
