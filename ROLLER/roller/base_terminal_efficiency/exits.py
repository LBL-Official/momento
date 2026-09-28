"""Independent WIN/LOSS books. Exact-timestamp AMBIGUOUS. Wraps run_path; does not use _classify_exits."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from roller.base_terminal_efficiency.models import (
    AMBIGUOUS,
    DATA_REQUIRED,
    INVALID_SEMANTICS,
    LOSS,
    TIE_EXACT_TIMESTAMP,
    WIN,
)
from roller.research_query.entry_engine import TradableBar
from roller.research_query.models import PathCondition, PathOp
from roller.research_query.path_engine import run_path


def validate_books(entry_e4: int, win_e4: int | None, loss_e4: int | None) -> str | None:
    if win_e4 is not None and win_e4 < entry_e4:
        return INVALID_SEMANTICS
    if loss_e4 is not None and loss_e4 > entry_e4:
        return INVALID_SEMANTICS
    return None


def _has_game_clock(steps: list[PathCondition]) -> bool:
    return any(
        p.op in (PathOp.HORIZON_WIN, PathOp.HORIZON_LOSS) and p.horizon_kind == "game" for p in steps
    )


def classify_first_exit(
    entry: TradableBar,
    after: list[TradableBar],
    *,
    win_steps: list[PathCondition] | None = None,
    loss_steps: list[PathCondition] | None = None,
    win_price_e4: int | None = None,
    loss_price_e4: int | None = None,
    snap_fn: Callable[[datetime], dict[str, Any]] | None = None,
    entry_elapsed_s: int | None = None,
    sport: str = "NBA",
) -> dict[str, Any]:
    """First subsequent exit. Entry bar excluded by after[] and run_path."""
    after = [b for b in after if b.ts > entry.ts]
    win_steps = list(win_steps or [])
    loss_steps = list(loss_steps or [])
    if win_price_e4 is not None and not win_steps:
        win_steps = [PathCondition(id="win", op=PathOp.REACH, price_e4=int(win_price_e4))]
    if loss_price_e4 is not None and not loss_steps:
        loss_steps = [PathCondition(id="loss", op=PathOp.DROP_TO, price_e4=int(loss_price_e4))]
    err = validate_books(
        entry.bid,
        win_steps[0].price_e4 if win_steps and win_steps[0].op not in (PathOp.HORIZON_WIN, PathOp.HORIZON_LOSS) else None,
        loss_steps[0].price_e4 if loss_steps and loss_steps[0].op not in (PathOp.HORIZON_WIN, PathOp.HORIZON_LOSS) else None,
    )
    if err:
        return {
            "status": err,
            "exit_outcome": None,
            "exclusion_reason": err,
            "win_exit_ts": None,
            "loss_exit_ts": None,
            "exit_ts": None,
            "exit_price_e4": None,
        }
    if (_has_game_clock(win_steps) or _has_game_clock(loss_steps)) and snap_fn is None:
        return {
            "status": DATA_REQUIRED,
            "exit_outcome": None,
            "exclusion_reason": DATA_REQUIRED,
            "win_exit_ts": None,
            "loss_exit_ts": None,
            "exit_ts": None,
            "exit_price_e4": None,
        }
    win_hits, win_ok, win_bar = (
        run_path(
            after,
            entry.bid,
            win_steps,
            entry_ts=entry.ts,
            entry_elapsed_s=entry_elapsed_s,
            snap_fn=snap_fn,
            sport=sport,
        )
        if win_steps
        else ([], False, None)
    )
    loss_hits, loss_ok, loss_bar = (
        run_path(
            after,
            entry.bid,
            loss_steps,
            entry_ts=entry.ts,
            entry_elapsed_s=entry_elapsed_s,
            snap_fn=snap_fn,
            sport=sport,
        )
        if loss_steps
        else ([], False, None)
    )
    win_ts = win_bar.ts if win_ok and win_bar is not None else None
    loss_ts = loss_bar.ts if loss_ok and loss_bar is not None else None
    if win_ts is not None and loss_ts is not None and win_ts == loss_ts:
        return {
            "status": AMBIGUOUS,
            "exit_outcome": AMBIGUOUS,
            "exclusion_reason": TIE_EXACT_TIMESTAMP,
            "win_exit_ts": win_ts.isoformat().replace("+00:00", "Z"),
            "loss_exit_ts": loss_ts.isoformat().replace("+00:00", "Z"),
            "win_exit_price_e4": win_bar.bid if win_bar else None,
            "loss_exit_price_e4": loss_bar.bid if loss_bar else None,
            "exit_ts": None,
            "exit_price_e4": None,
        }
    if win_ts is not None and (loss_ts is None or win_ts < loss_ts):
        return {
            "status": WIN,
            "exit_outcome": WIN,
            "exclusion_reason": None,
            "win_exit_ts": win_ts.isoformat().replace("+00:00", "Z"),
            "loss_exit_ts": loss_ts.isoformat().replace("+00:00", "Z") if loss_ts else None,
            "win_exit_price_e4": win_bar.bid if win_bar else None,
            "exit_ts": win_ts.isoformat().replace("+00:00", "Z"),
            "exit_price_e4": win_bar.bid if win_bar else None,
            "win_exit_type": win_hits[0].op.value if win_hits else "REACH",
        }
    if loss_ts is not None and (win_ts is None or loss_ts < win_ts):
        return {
            "status": LOSS,
            "exit_outcome": LOSS,
            "exclusion_reason": None,
            "loss_exit_ts": loss_ts.isoformat().replace("+00:00", "Z"),
            "win_exit_ts": win_ts.isoformat().replace("+00:00", "Z") if win_ts else None,
            "loss_exit_price_e4": loss_bar.bid if loss_bar else None,
            "exit_ts": loss_ts.isoformat().replace("+00:00", "Z"),
            "exit_price_e4": loss_bar.bid if loss_bar else None,
            "loss_exit_type": loss_hits[0].op.value if loss_hits else "DROP_TO",
        }
    return {
        "status": None,
        "exit_outcome": None,
        "exclusion_reason": None,
        "win_exit_ts": None,
        "loss_exit_ts": None,
        "exit_ts": None,
        "exit_price_e4": None,
    }
