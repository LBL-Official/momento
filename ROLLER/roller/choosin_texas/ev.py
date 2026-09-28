"""Candle-path ledger EV. Not a fill. Not live EV."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from roller.choosin_texas.locks import EV_BAR_FULL_CENTS, GAIN_CENTS, loss_cents_for_stop
from roller.choosin_texas.models import ChoosinTexasError, frac


def ev_from_s(s: Fraction, gain: int, loss: int) -> Fraction:
    return s * int(gain) - (1 - s) * int(loss)


def book_cents(s_n: int, n: int, *, gain: int, loss: int) -> int:
    return int(gain) * int(s_n) - int(loss) * (int(n) - int(s_n))


def ev_payload(
    *,
    n: int,
    s_n: int,
    stop_cents: int,
    gain_cents: int = GAIN_CENTS,
    loss_cents: int | None = None,
) -> dict[str, Any]:
    if n <= 0:
        raise ChoosinTexasError("LOCK_MISMATCH", "EV denominator N is 0")
    if s_n < 0 or s_n > n:
        raise ChoosinTexasError("LOCK_MISMATCH", f"S count {s_n} outside N {n}")
    loss = int(loss_cents) if loss_cents is not None else loss_cents_for_stop(stop_cents)
    book = book_cents(s_n, n, gain=gain_cents, loss=loss)
    ev = Fraction(book, n)
    if ev != ev_from_s(Fraction(s_n, n), gain_cents, loss):
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            f"EV identity {int(gain_cents)}S − L(1−S) failed",
        )
    bar = Fraction(ev.numerator, ev.denominator * EV_BAR_FULL_CENTS) * 100
    clipped = max(0.0, min(100.0, float(bar)))
    return {
        "gain_cents": int(gain_cents),
        "loss_cents": int(loss),
        "stop_cents": int(stop_cents),
        "ev_cents": frac(ev.numerator, ev.denominator),
        "ev_display": f"{ev.numerator}/{ev.denominator} ¢",
        "ev_per_trade_display": f"{float(ev):+.4f}¢ / trade",
        "book_cents": book,
        "ev_bar_pct": clipped,
    }
