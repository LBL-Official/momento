"""William Hill quote pairing. One complete set at a time."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from decimal import Decimal

from roller.ontologic_x import METHOD
from roller.ontologic_x.math import (
    InvalidPrice,
    american_implied,
    analytical_partition,
    is_integer_line,
    percent_text,
    proportional_no_vig,
)

MAX_SOURCE_SKEW = timedelta(seconds=120)
WILLIAM_HILL = {"williamhill", "williamhilluk"}
CAESARS_KEYS = {"williamhillus"}


def _book_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def classify_book(value: object) -> str:
    key = _book_key(value)
    if key in CAESARS_KEYS:
        return "caesars_key"
    if key in WILLIAM_HILL:
        return "williamhill"
    return "other"


def _parse_time(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed


def _line(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))


def _abs_line(value: object) -> str | None:
    number = _line(value)
    if number is None:
        return None
    return format(abs(number), "f")


def split_books(quotes: list[dict]) -> tuple[list[dict], list[dict]]:
    kept: list[dict] = []
    rejected: list[dict] = []
    for quote in quotes:
        kind = classify_book(quote.get("bookmaker"))
        if kind == "williamhill":
            kept.append({**quote, "bookmaker": "williamhill"})
        elif kind == "caesars_key":
            rejected.append({"bookmaker": quote.get("bookmaker"), "reason": "BOOK_KEY_IS_CAESARS"})
        else:
            rejected.append({"bookmaker": quote.get("bookmaker"), "reason": "NOT_WILLIAM_HILL"})
    return kept, rejected


def _group_key(quote: dict) -> tuple:
    return (
        quote.get("provider_event_id"),
        quote.get("bookmaker"),
        quote.get("market_family"),
        quote.get("market_name"),
        quote.get("participant"),
        quote.get("period"),
        quote.get("settlement"),
        _abs_line(quote.get("line")),
    )


def _skewed(left: dict, right: dict) -> bool:
    a = _parse_time(left.get("source_updated_at"))
    b = _parse_time(right.get("source_updated_at"))
    if a is None or b is None:
        return False
    if a.tzinfo is None or b.tzinfo is None:
        return False
    return abs(a - b) > MAX_SOURCE_SKEW


def _price_row(quote: dict) -> tuple[Decimal, Decimal] | None:
    try:
        if quote.get("american") is not None:
            return american_implied(quote.get("american"))
        return None
    except InvalidPrice:
        return None


def _pair_payload(left: dict, right: dict, status: str, result: dict | None) -> dict:
    integer = False
    line = left.get("line")
    if line is not None:
        integer = is_integer_line(line)
    payload = {
        "method": METHOD,
        "status": status,
        "market_family": left.get("market_family"),
        "period": left.get("period"),
        "settlement": left.get("settlement"),
        "main": bool(left.get("main")),
        "line": None if line is None else format(_line(line), "f"),
        "conditional_on_no_push": integer,
        "push_probability": "UNAVAILABLE" if integer else None,
        "sides": [left, right],
        "normalized": [],
        "overround_points": None,
    }
    if integer and status == "OK":
        payload["status"] = "CONDITIONAL_ON_NO_PUSH"
    if result and result.get("status") == "OK":
        payload["overround_points"] = result["overround_points"]
        payload["implied_total_points"] = percent_text(result["implied_total"]).rstrip("%")
        by_side = []
        for quote, item in zip((left, right), result["normalized"]):
            by_side.append(
                {
                    "side": quote.get("side"),
                    "line": None if quote.get("line") is None else format(_line(quote.get("line")), "f"),
                    "american": quote.get("american"),
                    "raw_display_percent": item["raw_display_percent"],
                    "display_percent": item["display_percent"],
                    "probability": format(item["probability"], "f"),
                    "fair_decimal": format(item["fair_decimal"], "f"),
                    "source_updated_at": quote.get("source_updated_at"),
                    "last_quote_change_at": quote.get("last_quote_change_at"),
                }
            )
        payload["normalized"] = by_side
    return payload


def pair_quotes(quotes: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = {}
    for quote in quotes:
        if quote.get("status") not in {None, "open"}:
            continue
        groups.setdefault(_group_key(quote), []).append(quote)
    pairs: list[dict] = []
    for grouped in groups.values():
        family = grouped[0].get("market_family")
        if family == "total":
            left = next((item for item in grouped if item.get("side") == "over"), None)
            right = next((item for item in grouped if item.get("side") == "under"), None)
            orientation_ok = (
                left is not None
                and right is not None
                and _line(left.get("line")) == _line(right.get("line"))
            )
        else:
            left = next((item for item in grouped if item.get("side") == "home"), None)
            right = next((item for item in grouped if item.get("side") == "away"), None)
            if family == "spread":
                orientation_ok = (
                    left is not None
                    and right is not None
                    and _line(left.get("line")) is not None
                    and _line(left.get("line")) == -_line(right.get("line"))
                )
            else:
                orientation_ok = left is not None and right is not None
        if left is None or right is None:
            pairs.append(
                {
                    "method": METHOD,
                    "status": "INCOMPLETE",
                    "market_family": family,
                    "period": grouped[0].get("period"),
                    "settlement": grouped[0].get("settlement"),
                    "sides": grouped,
                    "normalized": [],
                }
            )
            continue
        if not orientation_ok:
            pairs.append(_pair_payload(left, right, "ORIENTATION_INVALID", None))
            continue
        if _skewed(left, right):
            pairs.append(_pair_payload(left, right, "TIMESTAMP_SKEW", None))
            continue
        priced_left = _price_row(left)
        priced_right = _price_row(right)
        if priced_left is None or priced_right is None:
            pairs.append(_pair_payload(left, right, "INVALID_PRICE", None))
            continue
        result = proportional_no_vig([priced_left[1], priced_right[1]])
        pairs.append(_pair_payload(left, right, "OK", result))
    return pairs


def survival_points(pairs: list[dict], family: str, period: str, settlement: str, variable: str) -> dict:
    points: list[tuple[Decimal, Decimal]] = []
    for pair in pairs:
        if pair.get("market_family") != family or pair.get("period") != period:
            continue
        if pair.get("settlement") != settlement:
            continue
        if pair.get("status") != "OK" or pair.get("conditional_on_no_push"):
            continue
        home = next((side for side in pair["normalized"] if side["side"] in {"home", "over"}), None)
        if home is None or pair.get("line") is None:
            continue
        line = Decimal(pair["line"])
        threshold = -line if family == "spread" else line
        if family == "spread":
            home_side = next(side for side in pair["normalized"] if side["side"] == "home")
            probability = Decimal(home_side["probability"])
        else:
            probability = Decimal(home["probability"])
        points.append((threshold, probability))
    return analytical_partition(points, variable)
