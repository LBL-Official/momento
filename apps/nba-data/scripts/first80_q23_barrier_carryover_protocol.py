#!/usr/bin/env python3
"""How to tell if 2Q/3Q barrier survival carries into 2026-27.

Research only. Does not change live FIRST01. Does not invent L2.

Frozen objects stay frozen:
    FIRST80, T40 = first later close-path yes_bid ≤ 40, Q2∪Q3 only.

World A (2026-27 K=80 means P(W)=0.75, path|W held):
    P(¬T40) → 66.83%
    P(¬T40|W) stays 89.11%
    P(T40|L) stays 1

World S (P(W)=0.75, P(¬T40) held):
    P(¬T40) stays 74.50%
    P(¬T40|W) → ~99.3%
    winner-touches nearly vanish

Those two worlds make different predictions. Carryover is decided by
which rates print — not by a story about efficiency.

2025-26 already moved month to month. That is the prior, not a forecast.
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first80_quarter_barrier_survival as Q  # noqa: E402

OUT = Q.OUT.parent / "first80_q23_barrier_carryover_protocol"

COMBINED_N = 604
COMBINED_W = 505
COMBINED_W_NOT = 450
COMBINED_LOSE = 99
# World A at P(W)=0.75: 0.75 * 450/505
WORLD_A_P_BAR = 0.75 * 450 / 505
WORLD_S_P_BAR = 450 / 604
WORLD_A_P_BAR_W = 450 / 505
WORLD_S_P_BAR_W = (450 / 604) / 0.75  # if L∩¬T40 stays 0


class IdentityHalt(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def game_date_of(row: dict) -> date:
    return date.fromisoformat(str(row["game_date"])[:10])


def wilson(k: int, n: int, z: float = 1.96) -> dict:
    if n <= 0:
        raise IdentityHalt("HALT empty wilson")
    p = k / n
    den = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / den
    half = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / den
    return {
        "k": k,
        "n": n,
        "p": round(p, 6),
        "p_pct": round(p * 100.0, 4),
        "lo_pct": round((center - half) * 100.0, 4),
        "hi_pct": round((center + half) * 100.0, 4),
    }


def slice_rates(rows: list[dict], label: str) -> dict:
    n = len(rows)
    w = sum(1 for r in rows if r.get("W"))
    w_not = sum(1 for r in rows if r.get("W") and not r.get("T40"))
    lose = n - w
    l_not = sum(1 for r in rows if (not r.get("W")) and not r.get("T40"))
    t40 = sum(1 for r in rows if r.get("T40"))
    return {
        "label": label,
        "n": n,
        "w": w,
        "w_not": w_not,
        "w_touch": w - w_not,
        "lose": lose,
        "l_not": l_not,
        "t40": t40,
        "P_term": wilson(w, n) if n else None,
        "P_bar": wilson(w_not + l_not, n) if n else None,
        "P_bar_given_W": wilson(w_not, w) if w else None,
        "P_T40_given_L": wilson(lose - l_not, lose) if lose else None,
    }


def load_q23() -> list[dict]:
    rows = Q._pq().read_table(Q.OUT / "trades.parquet").to_pylist()
    q23 = [r for r in rows if r.get("entry_quarter_bucket") in ("Q2", "Q3")]
    c = slice_rates(q23, "2Q+3Q")
    if c["n"] != COMBINED_N or c["w"] != COMBINED_W or c["w_not"] != COMBINED_W_NOT:
        raise IdentityHalt(f"HALT q23 {c}")
    if c["lose"] != COMBINED_LOSE or c["l_not"] != 0:
        raise IdentityHalt(f"HALT leak {c}")
    return q23


def monthly(rows: list[dict]) -> list[dict]:
    by: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        d = game_date_of(r)
        by[f"{d.year}-{d.month:02d}"].append(r)
    return [slice_rates(by[k], k) for k in sorted(by)]


def n_to_separate_worlds(alpha: float = 0.05) -> dict:
    """Rough n so Wilson CIs on P_bar no longer both cover 66.8% and 74.5%."""
    p0, p1 = WORLD_A_P_BAR, WORLD_S_P_BAR
    gap = p1 - p0
    # two-proportion SE ~ sqrt(2p(1-p)/n) with p=0.70
    p = 0.70
    z = 1.96
    n = math.ceil(2 * p * (1 - p) * (z / gap) ** 2)
    return {
        "world_A_P_bar_pct": round(p0 * 100.0, 4),
        "world_S_P_bar_pct": round(p1 * 100.0, 4),
        "gap_pp": round(gap * 100.0, 4),
        "approx_n_for_95_separation": n,
        "approx_weeks_at_21_taken": round(n / 20.7917, 1),
        "note": "Order-of-magnitude. Use sequential CIs, not this n as a stop rule.",
    }


def analyze() -> dict:
    rows = load_q23()
    novapr = [
        r
        for r in rows
        if date(2025, 11, 1) <= game_date_of(r) <= date(2026, 4, 12)
    ]
    novapr = sorted(novapr, key=lambda r: (game_date_of(r), int(r["first_80_timestamp"])))
    mid = len(novapr) // 2
    months = monthly(rows)
    dec = next(m for m in months if m["label"] == "2025-12")
    nov = next(m for m in months if m["label"] == "2025-11")
    if dec["P_bar"]["p_pct"] >= 70:
        raise IdentityHalt(f"HALT expected Dec dip {dec}")
    return {
        "written_utc": utc_now(),
        "research_only": True,
        "live_execution_changed": False,
        "frozen": {
            "entry": "FIRST80 Q2 or Q3 only",
            "T40": "first later tradable yes_bid_close ≤ 40",
            "do_not_retune": True,
            "existing_finding": (
                "Alpha-decomposition v1 on the full n=1230 tape: independent "
                "path survival vs FIRST75 was NOT established (OOS CI included 0). "
                "Barrier carryover is therefore unproven even in 2025-26."
            ),
        },
        "observed_2025_26": slice_rates(rows, "2Q+3Q"),
        "nov_apr": slice_rates(novapr, "Nov1-Apr12"),
        "nov_apr_h1": slice_rates(novapr[:mid], "NovApr-H1"),
        "nov_apr_h2": slice_rates(novapr[mid:], "NovApr-H2"),
        "months": months,
        "intra_season_move": {
            "nov_P_bar_pct": nov["P_bar"]["p_pct"],
            "dec_P_bar_pct": dec["P_bar"]["p_pct"],
            "move_pp": round(dec["P_bar"]["p_pct"] - nov["P_bar"]["p_pct"], 2),
            "note": "December already printed ~World A barrier rate. Carryover is not automatic.",
        },
        "world_predictions_if_k80_means_p75": {
            "A": {
                "P_term": 0.75,
                "P_bar": round(WORLD_A_P_BAR, 6),
                "P_bar_pct": round(WORLD_A_P_BAR * 100.0, 4),
                "P_bar_given_W_pct": round(WORLD_A_P_BAR_W * 100.0, 4),
                "P_T40_given_L": 1.0,
                "slip_edge": False,
            },
            "S": {
                "P_term": 0.75,
                "P_bar": round(WORLD_S_P_BAR, 6),
                "P_bar_pct": round(WORLD_S_P_BAR * 100.0, 4),
                "P_bar_given_W_pct": round(WORLD_S_P_BAR_W * 100.0, 4),
                "P_T40_given_L": 1.0,
                "slip_edge": True,
            },
        },
        "how_to_decide": {
            "rule": (
                "Freeze definitions before 2026-10-20. After each week of "
                "2Q+3Q FIRST80, update the four cells. Classify by whether "
                "the 95% Wilson interval on P_bar covers 66.83% (A), 74.50% "
                "(S), both, or neither. Do not retune T40 or the quarter cut."
            ),
            "call_A": "P_term CI covers 75% AND P_bar CI covers 66.83% AND excludes 74.50% AND P(¬T40|W) stays near 89%.",
            "call_S": "P_term CI covers 75% AND P_bar CI covers 74.50% AND excludes 66.83% AND winner-touches collapse.",
            "call_neither": "P_bar misses both targets, or L∩¬T40 appears, or entry-quarter mix shifts enough to explain the rate.",
            "sample": n_to_separate_worlds(),
        },
        "separate_nba_from_market": {
            "why": (
                "T40 is K_t≤40, not a basketball event. Same G path can T40 "
                "or not if the market maps states differently."
            ),
            "measure_in_parallel": [
                "G at τ80: period, remaining clock, PBP score differential (frozen join)",
                "After entry: min subsequent lead; whether the FIRST80 team ever trails",
                "T40 vs lead-collapse: if T40 rises and lead-collapse does not, that is market-path change",
                "FIRST80 population: if 80¢ now prints earlier/later or at different leads, the mix drifted",
            ],
            "control": (
                "Same as alpha-decomp Module B: compare P(¬T40|W, FIRST80) to "
                "P(¬T40|W, FIRST75) on 2026-27. Independent FIRST80 path "
                "requires that gap's CI exclude 0. It did not in 2025-26."
            ),
        },
    }


def write_outputs(summary: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("wrote", OUT / "summary.json")
    print("Nov P_bar", summary["intra_season_move"]["nov_P_bar_pct"])
    print("Dec P_bar", summary["intra_season_move"]["dec_P_bar_pct"])
    print("n_sep", summary["how_to_decide"]["sample"]["approx_n_for_95_separation"])


def main() -> int:
    write_outputs(analyze())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
