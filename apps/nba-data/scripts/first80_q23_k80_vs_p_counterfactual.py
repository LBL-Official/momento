#!/usr/bin/env python3
"""2Q/3Q FIRST80: observed P at Kalshi 80¢, and 2026-27 P=0.75 book.

Research only. K=80 is a quote, not a probability.

Extracted from the frozen NBA Q2+Q3 FIRST80 tape:

    P_term  = P(W | FIRST80, Q2∪Q3)
    P_bar   = P(¬T40 | FIRST80, Q2∪Q3)
    P_bar|W = P(¬T40 | W, FIRST80, Q2∪Q3)

T40 is still the first later close-path yes_bid ≤ 40. Adverse fills
are T40 trades; 20¢/10¢ are slippage on that signal.

2026-27 counterfactual: Kalshi 80¢ is taken to mean P_term = 0.75.
Two worlds — terminal and path are not required to move together.

    World A — hold path conditionals: P(¬T40|W) and P(T40|L)=1.
    World S — hold barrier survival P(¬T40); leftover wins are T40.

Does not change live FIRST01. Zero fee. Does not invent L2.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first80_quarter_barrier_survival as Q  # noqa: E402

OUT = Q.OUT.parent / "first80_q23_k80_vs_p_counterfactual"

SLICES = {
    "Q2": {"n": 314, "w": 267, "t40": 75, "w_not": 239, "lose": 47},
    "Q3": {"n": 290, "w": 238, "t40": 79, "w_not": 211, "lose": 52},
}
COMBINED_N = 604
COMBINED_W = 505
COMBINED_T40 = 154
COMBINED_W_NOT = 450
COMBINED_LOSE = 99
FUTURE_P_TERM = Fraction(75, 100)  # 2026-27: K=80 means P=0.75
ENTRY = Q.ENTRY_CENTS  # 80
WIN_PNL = Q.WIN_PNL_CENTS  # +20
TOUCH_PNL = 40 - ENTRY  # −40
# Conservative loser fills on the 40 signal: 50% @40, 30% @20, 20% @10.
LOSE_MIX_PNL = -52
DEBIT_1000_CONTRACTS = 1000 * 100 // ENTRY


class IdentityHalt(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def counts_of(rows: list[dict]) -> dict:
    n = len(rows)
    w = sum(1 for r in rows if r.get("W"))
    t40 = sum(1 for r in rows if r.get("T40"))
    w_not = sum(1 for r in rows if r.get("W") and not r.get("T40"))
    lose = n - w
    w_touch = w - w_not
    l_not = sum(1 for r in rows if (not r.get("W")) and not r.get("T40"))
    return {
        "n": n,
        "w": w,
        "t40": t40,
        "w_not": w_not,
        "w_touch": w_touch,
        "lose": lose,
        "l_not": l_not,
    }


def halt_slice(name: str, c: dict) -> None:
    exp = SLICES[name]
    if c["n"] != exp["n"] or c["w"] != exp["w"] or c["t40"] != exp["t40"]:
        raise IdentityHalt(f"HALT {name} {c} expected {exp}")
    if c["w_not"] != exp["w_not"] or c["lose"] != exp["lose"] or c["l_not"] != 0:
        raise IdentityHalt(f"HALT {name} joints {c}")


def define_p(c: dict) -> dict:
    n, w, w_not, lose, w_touch = c["n"], c["w"], c["w_not"], c["lose"], c["w_touch"]
    if n <= 0 or w <= 0:
        raise IdentityHalt("HALT empty P")
    p_term = Fraction(w, n)
    p_bar = Fraction(w_not, n)  # L∩¬T40 = 0 ⇒ ¬T40 = W∩¬T40
    p_bar_w = Fraction(w_not, w)
    p_t40_w = Fraction(w_touch, w)
    p_t40_l = Fraction(lose, lose) if lose else Fraction(0, 1)
    return {
        "definition": {
            "K": "Kalshi FIRST80 quote = 80¢. A price, not a probability.",
            "P_term": "P(expiration YES | FIRST80, this slice)",
            "P_bar": "P(¬T40 | FIRST80) = P(never later close-path ≤40)",
            "P_bar_given_W": "P(¬T40 | W, FIRST80)",
            "note": (
                "K=80 did not equal P_term in 2025-26. T40 is a market "
                "barrier on the 40 close-path, not a basketball event."
            ),
        },
        "K_cents": ENTRY,
        "P_term": float(p_term),
        "P_term_pct": round(float(p_term) * 100.0, 4),
        "P_bar": float(p_bar),
        "P_bar_pct": round(float(p_bar) * 100.0, 4),
        "P_bar_given_W": float(p_bar_w),
        "P_bar_given_W_pct": round(float(p_bar_w) * 100.0, 4),
        "P_T40_given_W": float(p_t40_w),
        "P_T40_given_L": float(p_t40_l),
        "K_minus_P_term_cents": round(ENTRY - float(p_term) * 100.0, 4),
        "fractions": {
            "P_term": f"{w}/{n}",
            "P_bar": f"{w_not}/{n}",
            "P_bar_given_W": f"{w_not}/{w}",
        },
    }


def ev_book(
    n: Fraction,
    w_surv: Fraction,
    w_touch: Fraction,
    l_touch: Fraction,
    l_surv: Fraction = Fraction(0),
) -> dict:
    """W¬T40 +20, WT40 −40, L∩T40 −52, L∩¬T40 hold-to-0 −80."""
    if w_surv + w_touch + l_touch + l_surv != n:
        raise IdentityHalt("HALT book partition")
    total = (
        w_surv * WIN_PNL
        + w_touch * TOUCH_PNL
        + l_touch * LOSE_MIX_PNL
        + l_surv * Q.LOSE_HOLD_PNL_CENTS
    )
    ev = total / n
    clean_total = (
        w_surv * WIN_PNL
        + (w_touch + l_touch) * TOUCH_PNL
        + l_surv * Q.LOSE_HOLD_PNL_CENTS
    )
    clean_ev = clean_total / n
    hold_total = (w_surv + w_touch) * WIN_PNL + (l_touch + l_surv) * Q.LOSE_HOLD_PNL_CENTS
    hold_ev = hold_total / n
    return {
        "n": float(n),
        "survive_win": float(w_surv),
        "winner_touch": float(w_touch),
        "loser_touch": float(l_touch),
        "loser_survive": float(l_surv),
        "P_term": float((w_surv + w_touch) / n),
        "P_bar": float((w_surv + l_surv) / n),
        "ev_slip_cents": round(float(ev), 4),
        "ev_slip_pct_of_debit": round(float(ev / ENTRY * 100), 4),
        "ev_per_1000_debit": round(float(DEBIT_1000_CONTRACTS * ev / 100), 2),
        "ev_clean40_cents": round(float(clean_ev), 4),
        "ev_clean40_pct_of_debit": round(float(clean_ev / ENTRY * 100), 4),
        "ev_hold_cents": round(float(hold_ev), 4),
        "has_slip_edge": bool(ev > 0),
        "has_clean40_edge": bool(clean_ev > 0),
        "has_hold_edge": bool(hold_ev > 0),
        "required_loser_no_t40": bool(l_surv > 0),
    }


def observed_book(c: dict) -> dict:
    return ev_book(
        Fraction(c["n"]),
        Fraction(c["w_not"]),
        Fraction(c["w_touch"]),
        Fraction(c["lose"]),
        Fraction(c["l_not"]),
    )


def world_a_path_conditionals_held(c: dict, p_term: Fraction) -> dict:
    """P(W)=p_term; P(¬T40|W) and P(T40|L)=1 held from 2025-26."""
    n = Fraction(c["n"])
    w = p_term * n
    lose = n - w
    w_not = w * Fraction(c["w_not"], c["w"])
    w_touch = w - w_not
    return {
        "world": "A_path_conditionals_held",
        "meaning": (
            "Terminal P falls to 0.75. P(¬T40|W) stays at the 2025-26 "
            "slice rate. Every loser still T40. Same basketball-conditional "
            "path; only the win-rate mix changes."
        ),
        **ev_book(n, w_not, w_touch, lose, Fraction(0)),
    }


def world_s_barrier_held(c: dict, p_term: Fraction) -> dict:
    """P(W)=p_term; P(¬T40) held at the 2025-26 count.

    If observed ¬T40 exceeds future W, some barrier survivors lose
    (L and ¬T40) and mark −80¢. That leak is 0 in the 2025-26 tape
    but is required if both rates are held on Q2.
    """
    n = Fraction(c["n"])
    w = p_term * n
    lose = n - w
    bar = Fraction(c["w_not"] + c["l_not"])
    w_surv = min(w, bar)
    l_surv = bar - w_surv
    w_touch = w - w_surv
    l_touch = lose - l_surv
    if l_touch < 0:
        raise IdentityHalt("HALT World S T40 underflow")
    return {
        "world": "S_barrier_survival_held",
        "meaning": (
            "Terminal P falls to 0.75. Barrier survival P(¬T40) stays at "
            "the 2025-26 slice rate. If P(¬T40)>0.75, some survivors lose "
            "and settle 0 (−80¢). Otherwise extra losses are T40."
        ),
        **ev_book(n, w_surv, w_touch, l_touch, l_surv),
    }


def cell(name: str, rows: list[dict], halt_key: str | None) -> dict:
    c = counts_of(rows)
    if halt_key:
        halt_slice(halt_key, c)
    p = define_p(c)
    obs = observed_book(c)
    a = world_a_path_conditionals_held(c, FUTURE_P_TERM)
    s = world_s_barrier_held(c, FUTURE_P_TERM)
    return {
        "cell": name,
        **c,
        "observed_p": p,
        "observed_2025_26": obs,
        "future_p75_world_A": a,
        "future_p75_world_S": s,
    }


def analyze(rows: list[dict] | None = None) -> dict:
    rows = rows if rows is not None else Q._pq().read_table(Q.OUT / "trades.parquet").to_pylist()
    q2 = [r for r in rows if r.get("entry_quarter_bucket") == "Q2"]
    q3 = [r for r in rows if r.get("entry_quarter_bucket") == "Q3"]
    cells = [
        cell("2Q", q2, "Q2"),
        cell("3Q", q3, "Q3"),
        cell("2Q+3Q", q2 + q3, None),
    ]
    combo = cells[2]
    if (
        combo["n"] != COMBINED_N
        or combo["w"] != COMBINED_W
        or combo["t40"] != COMBINED_T40
        or combo["w_not"] != COMBINED_W_NOT
        or combo["lose"] != COMBINED_LOSE
        or combo["l_not"] != 0
    ):
        raise IdentityHalt(f"HALT combined {combo}")
    return {
        "written_utc": utc_now(),
        "research_only": True,
        "live_execution_changed": False,
        "assumption": (
            "2025-26: K=80 is the FIRST80 quote, not P. Extracted P_term "
            "and P(¬T40) from frozen Q2+Q3. 2026-27: assume K=80 means "
            "P_term=0.75. World A holds P(¬T40|W). World S holds P(¬T40). "
            "Exit signal remains first close-path 40. Loser fills 50/30/20 "
            "on that 40 (−52¢). Zero fee. MODELED."
        ),
        "future_p_term": 0.75,
        "loser_mix_pnl_cents": LOSE_MIX_PNL,
        "cells": cells,
    }


def write_outputs(summary: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("wrote", OUT / "summary.json")
    for c in summary["cells"]:
        p = c["observed_p"]
        a = c["future_p75_world_A"]
        s = c["future_p75_world_S"]
        print(
            c["cell"],
            "P_term",
            p["P_term_pct"],
            "P_bar",
            p["P_bar_pct"],
            "obs_slip",
            c["observed_2025_26"]["ev_slip_cents"],
            "A",
            a["ev_slip_cents"],
            "edgeA",
            a["has_slip_edge"],
            "S",
            s["ev_slip_cents"],
            "edgeS",
            s["has_slip_edge"],
        )


def main() -> int:
    write_outputs(analyze())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
