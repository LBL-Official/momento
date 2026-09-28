"""Display sign conventions. Computation stays full precision."""

from __future__ import annotations

MINUS = "\u2212"


def format_signed_cents(value: float | None, *, places: int = 2) -> str:
    if value is None or value != value:
        return "—"
    if value > 0:
        return f"+{value:.{places}f}¢"
    if value < 0:
        return f"{MINUS}{abs(value):.{places}f}¢"
    return f"{value:.{places}f}¢"


def format_signed_dollars(value: float | None, *, places: int = 2) -> str:
    if value is None or value != value:
        return "—"
    mag = f"{abs(value):,.{places}f}"
    if value > 0:
        return f"+${mag}"
    if value < 0:
        return f"{MINUS}${mag}"
    return f"${mag}"


def format_drawdown_dollars(value: float | None, *, places: int = 2) -> str:
    """Drawdown is a positive magnitude, never a negative P&L."""
    if value is None or value != value:
        return "—"
    return f"${abs(value):,.{places}f}"


def format_sharpe(value: float | None) -> str:
    if value is None or value != value:
        return "—"
    return f"{value:.3f}"
