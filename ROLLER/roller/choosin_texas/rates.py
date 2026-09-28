"""Derived rates from four-cell integers. Fraction first. Display last."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from roller.choosin_texas.ev import ev_payload
from roller.choosin_texas.locks import (
    BARRIER_55,
    BARRIER_55_POOL_CELLS,
    BARRIER_55_POOL_EXCL,
    BARRIER_55_POOL_L,
    BARRIER_55_POOL_N,
    BARRIER_55_POOL_W,
    ENTRY_CAP_CENTS,
    K_DENOM,
    K_NUMER,
    MID_STOPS,
    PATH_STOPS,
    POOL_CELLS,
    POOL_L,
    POOL_N,
    POOL_W,
    STOP_55_CENTS,
    STOP_CENTS,
    Barrier55Lock,
    PartitionLock,
    ladder_cells,
    loss_cents_for_stop,
)
from roller.choosin_texas.models import ChoosinTexasError, frac, pct_display, ratio_display
from roller.results_math.proportions import wilson_interval


def assert_identities(
    n: int,
    w: int,
    lose: int,
    win_no: int,
    win_t40: int,
    lose_no: int,
    lose_t40: int,
    *,
    label: str,
) -> None:
    if n != w + lose:
        raise ChoosinTexasError("LOCK_MISMATCH", f"{label}: N != W + L ({n} != {w}+{lose})")
    cell_sum = win_no + win_t40 + lose_no + lose_t40
    if cell_sum != n:
        raise ChoosinTexasError("LOCK_MISMATCH", f"{label}: four-cell sum {cell_sum} != N {n}")
    if win_no + win_t40 != w:
        raise ChoosinTexasError("LOCK_MISMATCH", f"{label}: W cells != W")
    if lose_no + lose_t40 != lose:
        raise ChoosinTexasError("LOCK_MISMATCH", f"{label}: L cells != L")
    if n <= 0:
        raise ChoosinTexasError("LOCK_MISMATCH", f"{label}: N is 0")
    p = Fraction(w, n)
    s_w = Fraction(win_no, w) if w else None
    s_l = Fraction(lose_no, lose) if lose else None
    s = Fraction(win_no + lose_no, n)
    if s_w is None or s_l is None:
        raise ChoosinTexasError("LOCK_MISMATCH", f"{label}: cannot form s_W or s_L")
    recon = s_l + p * (s_w - s_l)
    if recon != s:
        raise ChoosinTexasError("LOCK_MISMATCH", f"{label}: S ≠ p·s_W + (1−p)·s_L")


def _wilson_pct(successes: int, n: int) -> dict[str, Any] | None:
    interval = wilson_interval(successes, n)
    if interval is None:
        return None
    return {
        "lower_pct": round(interval["lower"] * 100, 4),
        "upper_pct": round(interval["upper"] * 100, 4),
        "display": (
            f"{interval['lower'] * 100:.4f}–{interval['upper'] * 100:.4f}"
        ),
        "status": "DERIVED",
        "method": "wilson",
        "numer": int(successes),
        "denom": int(n),
    }


def rates_from_cells(
    n: int,
    w: int,
    lose: int,
    win_no: int,
    win_t40: int,
    lose_no: int,
    lose_t40: int,
    *,
    label: str,
) -> dict[str, Any]:
    assert_identities(n, w, lose, win_no, win_t40, lose_no, lose_t40, label=label)
    s_n = win_no + lose_no
    trade_l = n - s_n
    p = Fraction(w, n)
    s = Fraction(s_n, n)
    s_w = Fraction(win_no, w)
    s_l = Fraction(lose_no, lose)
    k = Fraction(K_NUMER, K_DENOM)
    alpha = p - k
    return {
        "n": n,
        "W": w,
        "L": lose,
        "cells": {
            "W_and_not_T40": win_no,
            "W_and_T40": win_t40,
            "L_and_not_T40": lose_no,
            "L_and_T40": lose_t40,
        },
        "terminal": {
            "wins": w,
            "losses": lose,
            "p": frac(w, n),
            "loss_rate": frac(lose, n),
            "p_display": ratio_display(w, n),
            "p_pct_display": pct_display(w, n),
            "p_bar_pct": float(p * 100),
            "loss_display": ratio_display(lose, n),
            "loss_pct_display": pct_display(lose, n),
            "p_wilson": _wilson_pct(w, n),
            "note": "Settlement YES given FIRST80. Not the 80/40 trade win rate.",
        },
        "trade_80_40": {
            "key": "80/40",
            "n": n,
            "wins": s_n,
            "losses": trade_l,
            "S": frac(s_n, n),
            "loss_rate": frac(trade_l, n),
            "S_display": ratio_display(s_n, n),
            "S_pct_display": pct_display(s_n, n),
            "S_bar_pct": float(s * 100),
            "loss_display": ratio_display(trade_l, n),
            "loss_pct_display": pct_display(trade_l, n),
            "S_wilson": _wilson_pct(s_n, n),
            "note": "S = P(¬T40). W∩T40 is a terminal win and an 80/40 loss.",
            **ev_payload(n=n, s_n=s_n, stop_cents=STOP_CENTS),
        },
        "s_W": {
            **frac(win_no, w),
            "display": ratio_display(win_no, w),
            "pct_display": pct_display(win_no, w),
        },
        "s_L": {
            **frac(lose_no, lose),
            "display": ratio_display(lose_no, lose),
            "pct_display": pct_display(lose_no, lose),
        },
        "alpha": {
            "numer": alpha.numerator,
            "denom": alpha.denominator,
            "status": "DERIVED",
            "K": {"numer": K_NUMER, "denom": K_DENOM},
            "pp_display": f"{float(alpha * 100):+.4f}",
        },
        "joint": {
            **frac(win_no, n),
            "display": ratio_display(win_no, n),
            "pct_display": pct_display(win_no, n),
        },
        "K": {"numer": K_NUMER, "denom": K_DENOM},
        "stop_cents": STOP_CENTS,
    }


def partition_payload(lock: PartitionLock) -> dict[str, Any]:
    body = rates_from_cells(
        lock.n,
        lock.W,
        lock.L,
        lock.win_no,
        lock.win_t40,
        lock.lose_no,
        lock.lose_t40,
        label=lock.partition_id,
    )
    body.update(
        {
            "partition_id": lock.partition_id,
            "sport": lock.sport,
            "sport_label": lock.sport_label,
            "slice": lock.slice,
            "slice_label": lock.slice_label,
            "role": "asked_six_slice",
            "rule": "FIRST80",
        }
    )
    return body


def pool_payload(
    n: int,
    w: int,
    lose: int,
    win_no: int,
    win_t40: int,
    lose_no: int,
    lose_t40: int,
) -> dict[str, Any]:
    body = rates_from_cells(
        n, w, lose, win_no, win_t40, lose_no, lose_t40, label="derived_four"
    )
    body.update(
        {
            "partition_id": "derived_four",
            "sport": "nba_ncaab_p5",
            "sport_label": "NBA + NCAAB P5",
            "slice": "asked_four",
            "slice_label": "NBA 2Q+3Q ∪ NCAAB 1H2+2H1",
            "role": "derived_four",
            "rule": "FIRST80",
            "note": "Derived union of the four slices. Not asked-six (1182).",
        }
    )
    return body


def trade_80_55_payload(
    n: int,
    w: int,
    lose: int,
    win_no: int,
    win_t55: int,
    lose_no: int,
    lose_t55: int,
    *,
    excluded_hit_86: int,
    label: str,
) -> dict[str, Any]:
    assert_identities(n, w, lose, win_no, win_t55, lose_no, lose_t55, label=label)
    s_n = win_no + lose_no
    trade_l = n - s_n
    s = Fraction(s_n, n)
    p = Fraction(w, n)
    return {
        "n": n,
        "excluded_hit_86": excluded_hit_86,
        "W": w,
        "L": lose,
        "cells": {
            "W_and_not_T55": win_no,
            "W_and_T55": win_t55,
            "L_and_not_T55": lose_no,
            "L_and_T55": lose_t55,
        },
        "filter": {
            "entry_yes_bid_lt": ENTRY_CAP_CENTS,
            "excluded_hit_86": excluded_hit_86,
            "n_full": n + excluded_hit_86,
            "note": (
                "Only FIRST80 prints still below 86. "
                "If the first ≥80 close is already ≥86, do not count."
            ),
        },
        "terminal": {
            "wins": w,
            "losses": lose,
            "p": frac(w, n),
            "p_display": ratio_display(w, n),
            "p_pct_display": pct_display(w, n),
            "p_bar_pct": float(p * 100),
            "loss_display": ratio_display(lose, n),
            "loss_pct_display": pct_display(lose, n),
            "note": "Terminal YES on the entry<86 subset. Not 80/55 S.",
        },
        "S": frac(s_n, n),
        "wins": s_n,
        "losses": trade_l,
        "S_display": ratio_display(s_n, n),
        "S_pct_display": pct_display(s_n, n),
        "S_bar_pct": float(s * 100),
        "loss_display": ratio_display(trade_l, n),
        "loss_pct_display": pct_display(trade_l, n),
        "S_wilson": _wilson_pct(s_n, n),
        "stop_cents": STOP_55_CENTS,
        "note": "S = P(¬T55 | entry yes_bid < 86). Candle path ≠ fill.",
        **ev_payload(n=n, s_n=s_n, stop_cents=STOP_55_CENTS),
    }


def barrier_55_from_lock(lock: Barrier55Lock) -> dict[str, Any]:
    return trade_80_55_payload(
        lock.n,
        lock.W,
        lock.L,
        lock.win_no,
        lock.win_t55,
        lock.lose_no,
        lock.lose_t55,
        excluded_hit_86=lock.excluded_hit_86,
        label=f"80_55:{lock.partition_id}",
    )


def path_payload(
    n: int,
    w: int,
    lose: int,
    win_no: int,
    win_tx: int,
    lose_no: int,
    lose_tx: int,
    *,
    stop_cents: int,
    label: str,
    excluded_hit_86: int | None = None,
) -> dict[str, Any]:
    assert_identities(n, w, lose, win_no, win_tx, lose_no, lose_tx, label=label)
    s_n = win_no + lose_no
    trade_l = n - s_n
    s = Fraction(s_n, n)
    loss = loss_cents_for_stop(stop_cents)
    body: dict[str, Any] = {
        "key": f"80/{stop_cents}",
        "stop_cents": int(stop_cents),
        "n": n,
        "W": w,
        "L": lose,
        "cells": {
            f"W_and_not_T{stop_cents}": win_no,
            f"W_and_T{stop_cents}": win_tx,
            f"L_and_not_T{stop_cents}": lose_no,
            f"L_and_T{stop_cents}": lose_tx,
        },
        "S": frac(s_n, n),
        "wins": s_n,
        "losses": trade_l,
        "S_display": ratio_display(s_n, n),
        "S_pct_display": pct_display(s_n, n),
        "S_bar_pct": float(s * 100),
        "loss_display": ratio_display(trade_l, n),
        "loss_pct_display": pct_display(trade_l, n),
        "S_wilson": _wilson_pct(s_n, n),
        "gain_cents": 20,
        "loss_cents": loss,
        "note": (
            f"S = P(¬T{stop_cents}). EV = 20S − {loss}(1−S). "
            "Candle path ≠ fill. Not live EV."
        ),
        **ev_payload(n=n, s_n=s_n, stop_cents=stop_cents),
    }
    if excluded_hit_86 is not None:
        body["excluded_hit_86"] = excluded_hit_86
        body["filter"] = {
            "entry_yes_bid_lt": ENTRY_CAP_CENTS,
            "excluded_hit_86": excluded_hit_86,
            "n_full": n + excluded_hit_86,
            "note": (
                "Only FIRST80 prints still below 86. "
                "If the first ≥80 close is already ≥86, do not count."
            ),
        }
        body["note"] = (
            "S = P(¬T55 | entry yes_bid < 86). EV = 20S − 25(1−S). "
            "Candle path ≠ fill. Not live EV."
        )
    return body


def paths_from_lock(lock: PartitionLock) -> list[dict[str, Any]]:
    barrier_55 = {row.partition_id: row for row in BARRIER_55}[lock.partition_id]
    out: list[dict[str, Any]] = []
    for stop in PATH_STOPS:
        if stop == 55:
            out.append(
                path_payload(
                    barrier_55.n,
                    barrier_55.W,
                    barrier_55.L,
                    barrier_55.win_no,
                    barrier_55.win_t55,
                    barrier_55.lose_no,
                    barrier_55.lose_t55,
                    stop_cents=55,
                    label=f"80_55:{lock.partition_id}",
                    excluded_hit_86=barrier_55.excluded_hit_86,
                )
            )
            continue
        win_no, win_tx, lose_no, lose_tx = ladder_cells(stop, lock.partition_id)
        out.append(
            path_payload(
                lock.n,
                lock.W,
                lock.L,
                win_no,
                win_tx,
                lose_no,
                lose_tx,
                stop_cents=stop,
                label=f"80_{stop}:{lock.partition_id}",
            )
        )
    return out


def mid_paths_from_lock(lock: PartitionLock) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for stop in MID_STOPS:
        win_no, win_tx, lose_no, lose_tx = ladder_cells(stop, lock.partition_id)
        out.append(
            path_payload(
                lock.n,
                lock.W,
                lock.L,
                win_no,
                win_tx,
                lose_no,
                lose_tx,
                stop_cents=stop,
                label=f"80_{stop}:{lock.partition_id}",
            )
        )
    return out


def mid_paths_from_pool() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for stop in MID_STOPS:
        win_no, win_tx, lose_no, lose_tx = ladder_cells(stop, "derived_four")
        out.append(
            path_payload(
                POOL_N,
                POOL_W,
                POOL_L,
                win_no,
                win_tx,
                lose_no,
                lose_tx,
                stop_cents=stop,
                label=f"80_{stop}:derived_four",
            )
        )
    return out


def paths_from_pool() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for stop in PATH_STOPS:
        if stop == 55:
            out.append(
                path_payload(
                    BARRIER_55_POOL_N,
                    BARRIER_55_POOL_W,
                    BARRIER_55_POOL_L,
                    *BARRIER_55_POOL_CELLS,
                    stop_cents=55,
                    label="80_55:derived_four",
                    excluded_hit_86=BARRIER_55_POOL_EXCL,
                )
            )
            continue
        win_no, win_tx, lose_no, lose_tx = ladder_cells(stop, "derived_four")
        out.append(
            path_payload(
                POOL_N,
                POOL_W,
                POOL_L,
                win_no,
                win_tx,
                lose_no,
                lose_tx,
                stop_cents=stop,
                label=f"80_{stop}:derived_four",
            )
        )
    return out


def ledger_rank(paths: list[dict[str, Any]]) -> list[str]:
    ranked = sorted(
        paths,
        key=lambda row: (
            Fraction(int(row["ev_cents"]["numer"]), int(row["ev_cents"]["denom"])),
            -int(row["stop_cents"]),
        ),
        reverse=True,
    )
    return [str(row["key"]) for row in ranked]
