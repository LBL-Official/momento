"""Empirical counts and partitions. Not a model. No alpha / edge / predicted probability."""

from __future__ import annotations

from typing import Any, Callable, Iterable

from roller.base_terminal_efficiency.models import (
    AMBIGUOUS,
    LOSS,
    TERMINAL_MISSING,
    TERMINAL_NO,
    TERMINAL_YES,
    WIN,
)


def measure(
    observations: Iterable[dict[str, Any]],
    *,
    exit_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = list(observations)
    exits = exit_results if exit_results is not None else [None] * len(rows)
    n_entry = len(rows)
    n_win = n_loss = n_win_before = n_loss_before = n_amb = 0
    n_yes = n_no = n_miss = 0
    for row, ex in zip(rows, exits):
        term = row.get("terminal_outcome")
        if term == TERMINAL_YES:
            n_yes += 1
        elif term == TERMINAL_NO:
            n_no += 1
        else:
            n_miss += 1
        if not ex:
            continue
        oc = ex.get("exit_outcome")
        if oc == WIN:
            n_win += 1
            n_win_before += 1
        elif oc == LOSS:
            n_loss += 1
            n_loss_before += 1
        elif oc == AMBIGUOUS:
            n_amb += 1
    return {
        "n_entry": n_entry,
        "n_win_exit": n_win,
        "n_loss_exit": n_loss,
        "n_win_before_loss": n_win_before,
        "n_loss_before_win": n_loss_before,
        "n_ambiguous": n_amb,
        "n_terminal_yes": n_yes,
        "n_terminal_no": n_no,
        "n_terminal_missing": n_miss,
    }


def partition(
    observations: list[dict[str, Any]],
    pred: Callable[[dict[str, Any]], bool],
    *,
    exit_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    kept_o: list[dict[str, Any]] = []
    kept_e: list[dict[str, Any]] | None = [] if exit_results is not None else None
    for i, row in enumerate(observations):
        if pred(row):
            kept_o.append(row)
            if kept_e is not None and exit_results is not None:
                kept_e.append(exit_results[i])
    return measure(kept_o, exit_results=kept_e)


def range_pred(field: str, lo: int | None, hi: int | None) -> Callable[[dict[str, Any]], bool]:
    def _ok(row: dict[str, Any]) -> bool:
        v = row.get(field)
        if v is None:
            return False
        if lo is not None and v < lo:
            return False
        if hi is not None and v > hi:
            return False
        return True

    return _ok
