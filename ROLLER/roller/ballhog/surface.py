"""q × p theoretical hedge surface. Never a fill."""

from __future__ import annotations

from typing import Any

from roller.ballhog.arithmetic import evaluate_candidate
from roller.ballhog.errors import BallhogError
from roller.ballhog.models import RESEARCH_UNIT_QTY, SURFACE_SCHEMA
from roller.ballhog.policy import BallhogPolicy


def build_surface(
    *,
    q_dir: int,
    a_t: float,
    a_l: float | None,
    weighted_t40_rate: float | None,
    policy: BallhogPolicy,
    research_unit_qty: int = RESEARCH_UNIT_QTY,
) -> dict[str, Any]:
    n = int(q_dir)
    if n <= 0:
        raise BallhogError("INVALID_QUANTITY", "q_dir must be a positive integer")
    cells: list[dict[str, Any]] = []
    for q in range(0, n + 1):
        prices = (0,) if q == 0 else policy.price_grid
        for p in prices:
            cell = evaluate_candidate(
                q_dir=n,
                q_hedge=q,
                hedge_price_cents=int(p) if q else 0,
                a_t=a_t,
                a_l=a_l,
                weighted_t40_rate=weighted_t40_rate,
                research_unit_qty=research_unit_qty,
            )
            if q == 0:
                cell["hedge_price_cents"] = None
                cell["assumed_hedge_price_cents"] = None
                cell["paired_lock_cents"] = 0
                cell["price_relevant"] = False
                cell["note"] = "No hedge. Paired lock not applied. Assumed A2 price is irrelevant."
            else:
                cell["price_relevant"] = True
                cell["note"] = "THEORETICAL / CANDLE_PATH. Not a fill."
            cells.append(cell)
    return {
        "schema": SURFACE_SCHEMA,
        "research_unit_qty": research_unit_qty,
        "q_dir": n,
        "price_grid": list(policy.price_grid),
        "execution_assumption": policy.execution_assumption,
        "fill_claimed": False,
        "current_hedge_price": "UNAVAILABLE",
        "cells": cells,
        "n_cells": len(cells),
    }
