"""Research exit mixes. NOT live liquidation rules."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from roller.superasi.models import SuperasiError
from roller.superasi.versions import DEFAULT_FILL, FILL_ALGORITHMS

GAIN_CENTS = 20
BARRIER_CENTS = 40
ENTRY_CENTS = 80
PLAN_EV = Fraction(5, 2)

DEFINITIONS = {
    "LEDGER_RULE": "L_x = barrier price (ledger). NOT A FILL.",
    "FIRST_BARRIER_CLOSE": "L_x = first tradable close ≤ barrier. NOT A FILL.",
    "PRINTED_OR_CLOSE": "40¢ if printed on the stop bar, else first through-close. NOT A FILL.",
    "PLUS_1M": "L_x = close one minute after the stop bar. Missing = UNAVAILABLE.",
    "PLUS_5M": "L_x = close five minutes after the stop bar. Missing = UNAVAILABLE.",
    "MIN_5M": "L_x = minimum close in +1…+5 minutes. Missing all = UNAVAILABLE.",
    "PLANNING_2_5": "Implied L such that EV = +2.50¢. PLANNING / NOT MEASURED.",
    "FAST_GAP_TAKER": "FAST_GAP uses first through-close as TAKER; else FIRST_BARRIER_CLOSE.",
}


def ev_from_s(s: Fraction, gain: int, loss: Fraction) -> Fraction:
    return s * gain - (1 - s) * loss


def implied_loss(s: Fraction, gain: int, ev: Fraction) -> Fraction:
    if s == 1:
        raise SuperasiError("PACKAGE_SCHEMA_INVALID", "implied L undefined at S=1")
    return (s * gain - ev) / (1 - s)


def _cents_loss(entry: int, exit_px: int | None) -> Fraction | None:
    if exit_px is None:
        return None
    return Fraction(entry - int(exit_px))


def loss_for_trade(trade: dict[str, Any], algo: str, *, entry: int = ENTRY_CENTS, barrier: int = BARRIER_CENTS) -> dict[str, Any]:
    if algo not in FILL_ALGORITHMS:
        raise SuperasiError("PACKAGE_SCHEMA_INVALID", f"unknown fill algorithm {algo}")
    if not _is_path_loss(trade):
        return {
            "loss_basis": algo,
            "loss_value_e4": None,
            "loss_cents": None,
            "loss_status": "NOT_PATH_LOSS",
            "liquidity": None,
        }
    derived = trade.get("window_derived") or {}
    t40 = _int(derived.get("t40_close") if derived.get("t40_close") is not None else trade.get("exit_close"))
    printed = bool(derived.get("printed_at_barrier")) or (t40 == barrier)
    fast = bool(derived.get("fast_gap"))
    plus1 = _int(derived.get("close_1m"))
    plus5 = _int(derived.get("close_5m"))
    min5 = _int(derived.get("min_close_5m"))

    exit_px: int | None
    status = "DERIVED"
    liq = "UNAVAILABLE"
    if algo == "LEDGER_RULE":
        exit_px = barrier
        status = "OBSERVED" if printed else "HYPOTHETICAL"
        liq = "TAKER" if (t40 is not None and t40 < barrier) or fast else "UNAVAILABLE"
    elif algo == "FIRST_BARRIER_CLOSE":
        exit_px = t40
        status = "OBSERVED" if exit_px is not None else "UNAVAILABLE"
        liq = "TAKER" if exit_px is not None and exit_px < barrier else ("OBSERVED" if printed else "UNAVAILABLE")
        if printed:
            liq = "UNAVAILABLE"
        elif exit_px is not None:
            liq = "TAKER"
    elif algo == "PRINTED_OR_CLOSE":
        exit_px = barrier if printed else t40
        status = "OBSERVED" if exit_px is not None else "UNAVAILABLE"
        liq = "TAKER" if (not printed and exit_px is not None) else "UNAVAILABLE"
    elif algo == "PLUS_1M":
        exit_px = plus1
        status = "OBSERVED" if exit_px is not None else "UNAVAILABLE"
        liq = "TAKER" if exit_px is not None else "UNAVAILABLE"
    elif algo == "PLUS_5M":
        exit_px = plus5
        status = "OBSERVED" if exit_px is not None else "UNAVAILABLE"
        liq = "TAKER" if exit_px is not None else "UNAVAILABLE"
    elif algo == "MIN_5M":
        exit_px = min5
        status = "OBSERVED" if exit_px is not None else "UNAVAILABLE"
        liq = "TAKER" if exit_px is not None else "UNAVAILABLE"
    elif algo == "PLANNING_2_5":
        exit_px = None
        status = "MODEL-ASSUMED"
        liq = None
    else:  # FAST_GAP_TAKER
        exit_px = t40
        status = "OBSERVED" if exit_px is not None else "UNAVAILABLE"
        liq = "TAKER" if fast or (exit_px is not None and exit_px < barrier) else "UNAVAILABLE"

    loss = _cents_loss(entry, exit_px) if algo != "PLANNING_2_5" else None
    if status == "UNAVAILABLE":
        loss = None
        exit_px = None
    return {
        "loss_basis": algo,
        "loss_value_e4": None if exit_px is None else int(exit_px) * 100,
        "exit_cents": exit_px,
        "loss_cents": None if loss is None else {"numer": loss.numerator, "denom": loss.denominator},
        "loss_status": status,
        "liquidity": liq,
        "printed_at_barrier": printed,
        "fast_gap": fast,
        "note": DEFINITIONS[algo],
    }


def summarize_mix(
    trades: list[dict[str, Any]],
    s: Fraction,
    algo: str,
    *,
    gain: int = GAIN_CENTS,
    entry: int = ENTRY_CENTS,
    barrier: int = BARRIER_CENTS,
) -> dict[str, Any]:
    if algo == "PLANNING_2_5":
        loss = implied_loss(s, gain, PLAN_EV)
        ev = PLAN_EV
        return {
            "id": algo,
            "definition": DEFINITIONS[algo],
            "n_path_loss": sum(1 for t in trades if _is_path_loss(t)),
            "n_available": None,
            "n_unavailable": None,
            "mean_L": {"numer": loss.numerator, "denom": loss.denominator, "status": "MODEL-ASSUMED"},
            "mean_exit": {
                "numer": (entry - loss).numerator,
                "denom": (entry - loss).denominator,
                "status": "MODEL-ASSUMED",
            },
            "EV": {"numer": ev.numerator, "denom": ev.denominator, "status": "MODEL-ASSUMED"},
            "G": gain,
            "S": {"numer": s.numerator, "denom": s.denominator},
            "research_status": "PLANNING / NOT MEASURED",
            "not_a_fill": True,
        }

    losses: list[Fraction] = []
    exits: list[int] = []
    n_loss = 0
    n_unavail = 0
    for t in trades:
        if not _is_path_loss(t):
            continue
        n_loss += 1
        rec = loss_for_trade(t, algo, entry=entry, barrier=barrier)
        if rec["loss_status"] == "UNAVAILABLE" or rec["loss_cents"] is None:
            n_unavail += 1
            continue
        losses.append(Fraction(rec["loss_cents"]["numer"], rec["loss_cents"]["denom"]))
        if rec["exit_cents"] is not None:
            exits.append(int(rec["exit_cents"]))
    if not losses:
        ev_status = "UNAVAILABLE"
        mean_l = None
        ev = None
    else:
        mean_l = sum(losses, Fraction(0)) / len(losses)
        ev = ev_from_s(s, gain, mean_l)
        ev_status = "DERIVED"
    return {
        "id": algo,
        "definition": DEFINITIONS[algo],
        "n_path_loss": n_loss,
        "n_available": len(losses),
        "n_unavailable": n_unavail,
        "mean_L": None
        if mean_l is None
        else {"numer": mean_l.numerator, "denom": mean_l.denominator, "status": ev_status},
        "mean_exit": None
        if not exits
        else {
            "numer": sum(exits),
            "denom": len(exits),
            "status": "OBSERVED",
        },
        "EV": None if ev is None else {"numer": ev.numerator, "denom": ev.denominator, "status": ev_status},
        "G": gain,
        "S": {"numer": s.numerator, "denom": s.denominator},
        "research_status": "RESEARCH EXIT MIX",
        "not_a_fill": True,
        "active_default": algo == DEFAULT_FILL,
    }


def all_mixes(
    trades: list[dict[str, Any]],
    s: Fraction,
    *,
    gain: int = GAIN_CENTS,
    entry: int = ENTRY_CENTS,
) -> dict[str, Any]:
    return {algo: summarize_mix(trades, s, algo, gain=gain, entry=entry) for algo in FILL_ALGORITHMS}


def _is_path_loss(t: dict[str, Any]) -> bool:
    return t.get("loss_exit") is True or t.get("T40") is True or t.get("path_true") is False


def _int(value: Any) -> int | None:
    if value is None or value == "" or value == "UNAVAILABLE":
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None
