"""Frozen tradable-cross / quality() from the FIRST80 candle scan.

Candle path ≠ fill. Spread is integer E4 (1000 = 10¢).
"""

from __future__ import annotations

from typing import Any

HIT80 = 8000
HIT40 = 4000
MAX_SPREAD_E4 = 1000  # 10¢, same as nba_80_40_execution_audit


def _int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def quality(bid: Any, ask: Any, vol: Any, had_quality: bool) -> bool:
    """Uncrossed spread ≤ 10¢, and volume > 0 or a prior tradable bar."""
    b = _int(bid)
    a = _int(ask)
    if b is None or a is None:
        return False
    if b > a:
        return False
    if a - b > MAX_SPREAD_E4:
        return False
    v = _int(vol)
    if v is not None and v > 0:
        return True
    return bool(had_quality)


def candle_quality_fields(bid: Any, ask: Any, vol: Any, is_valid: Any) -> dict[str, Any]:
    """Per-row flags. Sequential had_quality is applied in the FIRST80 scan."""
    b = _int(bid)
    a = _int(ask)
    v = _int(vol)
    spread = None if b is None or a is None else a - b
    uncrossed = b is not None and a is not None and b <= a
    spread_ok = spread is not None and 0 <= spread <= MAX_SPREAD_E4
    valid = None
    if is_valid in (True, False):
        valid = bool(is_valid)
    elif str(is_valid).strip().lower() in {"1", "true", "t"}:
        valid = True
    elif str(is_valid).strip().lower() in {"0", "false", "f"}:
        valid = False
    return {
        "is_valid": "" if valid is None else ("1" if valid else "0"),
        "spread_e4": "" if spread is None else str(spread),
        "uncrossed": "1" if uncrossed else "0",
        "spread_ok": "1" if spread_ok else "0",
        "volume_positive": "1" if v is not None and v > 0 else "0",
        "tradable_cross": "1" if uncrossed and spread_ok else "0",
    }
