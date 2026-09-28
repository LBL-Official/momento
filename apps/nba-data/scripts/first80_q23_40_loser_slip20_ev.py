#!/usr/bin/env python3
"""MODELED 2Q/3Q FIRST80→40 EV with loser fill mix 50/20/30.

Locked overlay (research only, not a fill):

- Universe: frozen NBA FIRST80 entry Q2 and Q3.
- The exit *signal* is still the first close-path 40. We do not wait
  for a 20 or 10 close-touch.
- Survive (no close-touch 40): hold to 100, +20¢. All survivors are winners.
- Winner who close-touches 40: still exit at 40¢, −40¢.
- Loser (every loser close-touches 40): 50% fill at 40¢ (−40¢),
  20% slip to 20¢ (−60¢), 30% slip to 10¢ (−70¢).
  Expected loser P&L = −53¢.

Does not change live FIRST01. Zero fee. Candle path. 20¢ / 10¢ fills
are assumed slippage on the 40 signal, not observed.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first80_quarter_barrier_survival as Q  # noqa: E402

OUT = Q.OUT.parent / "first80_q23_40_loser_slip20_ev"
LEVEL = 40
LOSE_AT_40_WGT = 50  # percent — intended 40 fill
LOSE_AT_20_WGT = 20  # percent — slip to 20 on the 40 signal
LOSE_AT_10_WGT = 30  # percent — slip to 10 on the 40 signal
EXIT_40_PNL = 40 - Q.ENTRY_CENTS  # −40
EXIT_20_PNL = 20 - Q.ENTRY_CENTS  # −60
EXIT_10_PNL = 10 - Q.ENTRY_CENTS  # −70
# 0.50*(−40) + 0.20*(−60) + 0.30*(−70) = −53.
LOSE_MIX_PNL = (
    LOSE_AT_40_WGT * EXIT_40_PNL
    + LOSE_AT_20_WGT * EXIT_20_PNL
    + LOSE_AT_10_WGT * EXIT_10_PNL
) // 100
DEBIT_1000_CONTRACTS = 1000 * 100 // Q.ENTRY_CENTS  # 1,250 YES @ 80¢

SLICES = {
    "Q2": {"n": 314, "w": 267, "t40": 75, "w_not": 239, "lose": 47},
    "Q3": {"n": 290, "w": 238, "t40": 79, "w_not": 211, "lose": 52},
}


class IdentityHalt(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def loser_mix_pnl_cents() -> int:
    if LOSE_AT_40_WGT + LOSE_AT_20_WGT + LOSE_AT_10_WGT != 100:
        raise IdentityHalt("HALT loser mix weights")
    if LOSE_MIX_PNL != -53:
        raise IdentityHalt(f"HALT mix pnl {LOSE_MIX_PNL}")
    return LOSE_MIX_PNL


def ev_from_sum(n: int, total_cents: int) -> dict:
    if n <= 0:
        return {
            "n": 0,
            "sum_pnl_cents": 0,
            "ev_cents_per_contract": None,
            "ev_pct_of_1_dollar": None,
            "ev_pct_of_80_debit": None,
            "label": "MODELED LOSER EXIT MIX — NOT A FILL — ZERO FEE",
        }
    ev = total_cents / n
    return {
        "n": n,
        "sum_pnl_cents": total_cents,
        "ev_cents_per_contract": round(ev, 4),
        "ev_pct_of_1_dollar": round(ev, 4),
        "ev_pct_of_80_debit": round(ev / Q.ENTRY_CENTS * 100.0, 4),
        "label": "MODELED LOSER EXIT MIX — NOT A FILL — ZERO FEE",
    }


def counts_of(rows: list[dict]) -> dict:
    n = len(rows)
    w = sum(1 for r in rows if r.get("W"))
    t40 = sum(1 for r in rows if r.get("T40"))
    w_not = sum(1 for r in rows if r.get("W") and not r.get("T40"))
    lose = n - w
    w_touch = sum(1 for r in rows if r.get("W") and r.get("T40"))
    leak = sum(1 for r in rows if (not r.get("W")) and not r.get("T40"))
    return {
        "n": n,
        "n_win": w,
        "n_lose": lose,
        "n_t40": t40,
        "n_survive_win": w_not,
        "n_win_and_touch": w_touch,
        "n_lose_and_touch": lose,
        "n_lose_without_t40": leak,
    }


def ev_modeled(c: dict) -> dict:
    mix = loser_mix_pnl_cents()
    total = (
        c["n_survive_win"] * Q.WIN_PNL_CENTS
        + c["n_win_and_touch"] * EXIT_40_PNL
        + c["n_lose"] * mix
    )
    out = ev_from_sum(c["n"], total)
    out.update(
        {
            "n_survive_win": c["n_survive_win"],
            "n_win_and_touch": c["n_win_and_touch"],
            "n_lose": c["n_lose"],
            "survive_pnl_cents": Q.WIN_PNL_CENTS,
            "winner_touch_pnl_cents": EXIT_40_PNL,
            "loser_mix_pnl_cents": mix,
            "loser_exit_40_pct": LOSE_AT_40_WGT,
            "loser_exit_20_pct": LOSE_AT_20_WGT,
            "loser_exit_10_pct": LOSE_AT_10_WGT,
            "ev_per_1000_debit_dollars": round(
                DEBIT_1000_CONTRACTS * total / c["n"] / 100.0, 2
            )
            if c["n"]
            else None,
        }
    )
    return out


def halt_counts(bucket: str, c: dict) -> None:
    exp = SLICES[bucket]
    if c["n"] != exp["n"] or c["n_win"] != exp["w"] or c["n_t40"] != exp["t40"]:
        raise IdentityHalt(f"HALT {bucket} {c} expected {exp}")
    if c["n_survive_win"] != exp["w_not"] or c["n_lose"] != exp["lose"]:
        raise IdentityHalt(f"HALT {bucket} joints {c}")
    if c["n_lose_without_t40"] != 0:
        raise IdentityHalt(f"HALT {bucket} loser leak")


def cell(name: str, rows: list[dict], halt_key: str | None) -> dict:
    c = counts_of(rows)
    if halt_key:
        halt_counts(halt_key, c)
    hold = Q.ev_hold_gross(c["n"], c["n_win"])
    stop = Q.ev_stop_gross(c["n"], c["n_survive_win"], c["n_t40"], LEVEL)
    modeled = ev_modeled(c)
    vs_hold = None
    vs_stop = None
    if modeled["ev_cents_per_contract"] is not None and hold["ev_cents_per_contract"] is not None:
        vs_hold = round(modeled["ev_cents_per_contract"] - hold["ev_cents_per_contract"], 4)
    if modeled["ev_cents_per_contract"] is not None and stop["ev_cents_per_contract"] is not None:
        vs_stop = round(modeled["ev_cents_per_contract"] - stop["ev_cents_per_contract"], 4)
    return {
        "cell": name,
        **c,
        "ev_hold": hold,
        "ev_stop_40_original": stop,
        "ev_modeled_slip20": modeled,
        "vs_hold_cents": vs_hold,
        "vs_original_stop_cents": vs_stop,
    }


def analyze(rows: list[dict] | None = None) -> dict:
    rows = rows if rows is not None else Q._pq().read_table(Q.OUT / "trades.parquet").to_pylist()
    q2 = [r for r in rows if r.get("entry_quarter_bucket") == "Q2"]
    q3 = [r for r in rows if r.get("entry_quarter_bucket") == "Q3"]
    cells = [
        cell("2Q 40", q2, "Q2"),
        cell("3Q 40", q3, "Q3"),
        cell("2Q+3Q 40", q2 + q3, None),
    ]
    combo = cells[2]
    if combo["n"] != 604 or combo["n_lose"] != 99 or combo["n_lose_without_t40"] != 0:
        raise IdentityHalt(f"HALT combined {combo}")
    table = [
        {
            "cell": c["cell"],
            "n": c["n"],
            "survive_W": c["n_survive_win"],
            "winner_touch": c["n_win_and_touch"],
            "losers": c["n_lose"],
            "touch": c["n_t40"],
            "hold_ev": c["ev_hold"]["ev_cents_per_contract"],
            "original_stop_ev": c["ev_stop_40_original"]["ev_cents_per_contract"],
            "modeled_ev": c["ev_modeled_slip20"]["ev_cents_per_contract"],
            "modeled_ev_80": c["ev_modeled_slip20"]["ev_pct_of_80_debit"],
            "ev_per_1000_debit": c["ev_modeled_slip20"]["ev_per_1000_debit_dollars"],
            "vs_hold": c["vs_hold_cents"],
            "vs_original_stop": c["vs_original_stop_cents"],
        }
        for c in cells
    ]
    return {
        "written_utc": utc_now(),
        "research_only": True,
        "live_execution_changed": False,
        "assumption": (
            "Exit signal is still first close-path 40. Among losers, "
            "50% fill at 40¢ (−40¢), 20% slip to 20¢ (−60¢), 30% slip to "
            "10¢ (−70¢). Expected loser P&L = −53¢. Winner-touches still "
            "−40¢. Survivors +20¢. MODELED — not observed fills."
        ),
        "loser_mix_pnl_cents": loser_mix_pnl_cents(),
        "cells": cells,
        "ev_table": table,
    }


def write_outputs(summary: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("wrote", OUT / "summary.json")
    for row in summary["ev_table"]:
        print(
            row["cell"],
            "orig",
            row["original_stop_ev"],
            "modeled",
            row["modeled_ev"],
            "vs hold",
            row["vs_hold"],
            "vs stop",
            row["vs_original_stop"],
            "$1000",
            row["ev_per_1000_debit"],
        )


def main() -> int:
    write_outputs(analyze())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
