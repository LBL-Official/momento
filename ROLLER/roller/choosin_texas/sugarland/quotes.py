"""Quote validity and timestamps. Candle end time is the PIT."""

from __future__ import annotations

from datetime import datetime, timezone

from roller.choosin_texas.sugarland.constants import BELOW_100, SPREAD_CAP_E4


def parse_ts(value: object) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def epoch(value: datetime | None) -> int | None:
    if value is None:
        return None
    return int(value.timestamp())


def parse_e4(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        number = float(text) if "." in text else int(text)
    except ValueError:
        return None
    if isinstance(number, float):
        if not number.is_integer():
            return None
        number = int(number)
    return int(number)


def is_valid_quote(bid: int | None, ask: int | None, *, spread_cap: int = SPREAD_CAP_E4) -> bool:
    if bid is None or ask is None:
        return False
    if not (0 < bid <= ask < BELOW_100):
        return False
    return (ask - bid) <= spread_cap


def is_boundary_arithmetic_mark(bid: int | None, ask: int | None, *, spread_cap: int = SPREAD_CAP_E4) -> bool:
    """Two-sided mark the frozen rule rejects only because a side touches 0 or 10000.

    Spread still has to be within the cap. Arithmetic on the bid is defined.
    Log-odds are not, when the bid itself is 0 or 10000.
    """
    if bid is None or ask is None:
        return False
    if not (0 <= bid <= ask <= BELOW_100):
        return False
    if (ask - bid) > spread_cap:
        return False
    return bid == 0 or bid == BELOW_100 or ask == 0 or ask == BELOW_100


def endpoint_reject_reason(bid: int | None, ask: int | None) -> str | None:
    """Why the frozen primary rule rejects a candle. None when the candle is valid."""
    if is_valid_quote(bid, ask):
        return None
    if is_boundary_arithmetic_mark(bid, ask):
        return "BOUNDARY_QUOTE"
    if bid is not None and ask is not None and ask >= bid and (ask - bid) > SPREAD_CAP_E4:
        return "EXCESSIVE_SPREAD"
    return "OTHER_EXCLUSION"


def price_band(bid: int) -> str:
    if 7000 < bid < 7500:
        return "(70,75)"
    if 7500 <= bid < 8000:
        return "[75,80)"
    if 8000 <= bid < 8500:
        return "[80,85)"
    if 8500 <= bid < 9000:
        return "[85,90)"
    if 9000 <= bid < 10000:
        return "[90,100)"
    return "other"


def lead_bucket(hours: float) -> str:
    if hours < 1:
        return "[0,1)"
    if hours < 2:
        return "[1,2)"
    if hours < 6:
        return "[2,6)"
    if hours < 12:
        return "[6,12)"
    if hours < 24:
        return "[12,24)"
    if hours < 48:
        return "[24,48)"
    return ">=48"
