"""Empirical four-cell. WR for SuperASI EV is S, not terminal p."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from roller.superasi.models import SuperasiError, frac


def cells_from_counts(
    win_no: int,
    win_t40: int,
    lose_no: int,
    lose_t40: int,
    *,
    k_numer: int = 80,
    k_denom: int = 100,
) -> dict[str, Any]:
    n = win_no + win_t40 + lose_no + lose_t40
    if n <= 0:
        raise SuperasiError("EMPTY_POPULATION", "four-cell N is 0")
    w = win_no + win_t40
    lose = lose_no + lose_t40
    p = Fraction(w, n)
    s_w = Fraction(win_no, w) if w else None
    s_l = Fraction(lose_no, lose) if lose else None
    s = Fraction(win_no + lose_no, n)
    if s_w is None or s_l is None:
        raise SuperasiError("PACKAGE_SCHEMA_INVALID", "cannot form s_W or s_L")
    recon = s_l + p * (s_w - s_l)
    if recon != s:
        raise SuperasiError("PACKAGE_SCHEMA_INVALID", "S ≠ p·s_W + (1−p)·s_L")
    k = Fraction(k_numer, k_denom)
    return {
        "n": n,
        "cells": {
            "W_and_not_T40": win_no,
            "W_and_T40": win_t40,
            "L_and_not_T40": lose_no,
            "L_and_T40": lose_t40,
        },
        "p": {"numer": p.numerator, "denom": p.denominator, "status": "OBSERVED"},
        "alpha": {
            "numer": (p - k).numerator,
            "denom": (p - k).denominator,
            "status": "DERIVED",
            "K": {"numer": k.numerator, "denom": k.denominator},
        },
        "s_W": {"numer": s_w.numerator, "denom": s_w.denominator, "status": "OBSERVED"},
        "s_L": {"numer": s_l.numerator, "denom": s_l.denominator, "status": "OBSERVED"},
        "S": {"numer": s.numerator, "denom": s.denominator, "status": "OBSERVED"},
        "note": "S is the SuperASI production-rule WR. Do not conflate S with terminal p.",
        "status": "OBSERVED",
    }


def cells_from_trades(trades: list[dict[str, Any]], *, k_numer: int = 80, k_denom: int = 100) -> dict[str, Any]:
    win_no = win_t40 = lose_no = lose_t40 = 0
    missing_terminal = 0
    for t in trades:
        term = t.get("terminal_yes")
        path_loss = _path_loss(t)
        if term is None:
            missing_terminal += 1
            continue
        if term and not path_loss:
            win_no += 1
        elif term and path_loss:
            win_t40 += 1
        elif (not term) and not path_loss:
            lose_no += 1
        else:
            lose_t40 += 1
    used = win_no + win_t40 + lose_no + lose_t40
    if used <= 0:
        return cells_from_path_only(trades)
    out = cells_from_counts(win_no, win_t40, lose_no, lose_t40, k_numer=k_numer, k_denom=k_denom)
    out["n_terminal_unavailable"] = missing_terminal
    out["n_classified"] = used
    return out


def cells_from_path_only(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """S from path survival only. Do not invent terminal YES/NO."""
    survivors = losses = unclass = 0
    for t in trades:
        try:
            if _path_loss(t):
                losses += 1
            else:
                survivors += 1
        except SuperasiError:
            unclass += 1
    used = survivors + losses
    if used <= 0:
        raise SuperasiError("DATA_REQUIRED", "no path-classified trades")
    s = Fraction(survivors, used)
    return {
        "n": used,
        "n_population": len(trades),
        "n_unclassified_path": unclass,
        "cells": {
            "W_and_not_T40": None,
            "W_and_T40": None,
            "L_and_not_T40": None,
            "L_and_T40": None,
        },
        "path_survivors": survivors,
        "path_losses": losses,
        "p": {"status": "UNAVAILABLE", "numer": None, "denom": None},
        "alpha": {"status": "UNAVAILABLE"},
        "s_W": {"status": "UNAVAILABLE"},
        "s_L": {"status": "UNAVAILABLE"},
        "S": {
            "numer": s.numerator,
            "denom": s.denominator,
            "status": "OBSERVED",
            "basis": "PATH_SURVIVAL",
        },
        "note": (
            "S is path survival (not barrier / not path loss) / classified N. "
            "Terminal p, α, s_W, and s_L are UNAVAILABLE. Missing settlement is not NO."
        ),
        "status": "PATH_ONLY",
        "n_terminal_unavailable": sum(1 for t in trades if t.get("terminal_yes") is None),
        "n_classified": used,
    }


def as_fractions(cell: dict[str, Any]) -> dict[str, Fraction]:
    out: dict[str, Fraction] = {}
    for key in ("p", "s_W", "s_L", "S", "alpha"):
        fr = cell.get(key) or {}
        numer = fr.get("numer")
        denom = fr.get("denom")
        if numer is None or not denom:
            continue
        out[key] = Fraction(int(numer), int(denom))
    return out


def _path_loss(t: dict[str, Any]) -> bool:
    if t.get("loss_exit") is True or t.get("T40") is True:
        return True
    if t.get("win_exit") is True:
        return False
    if t.get("path_true") is False:
        return True
    if t.get("path_true") is True:
        return False
    raise SuperasiError("DATA_REQUIRED", f"cannot classify path for {t.get('ticker')}")


# Silence unused import if frac is unused in some builds
_ = frac
