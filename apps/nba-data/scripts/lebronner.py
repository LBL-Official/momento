#!/usr/bin/env python3
"""Lebronner — frozen FIRST75 terminal × path archive and named EV cases.

Successor program name: SuperASI (`apps/nba-data/scripts/superasi.py`).
Lebronner remains the FIRST75 named-archive label.

Does not change live FIRST01. Candle path, not fills. Does not retune
FIRST75 / FIRST80 / T40. Reconstructs named arithmetic from locked counts.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/Users/user/Desktop/Momento")
REPORTS = REPO / "research" / "lebronner"
DOCS = REPO / "docs" / "research" / "lebronner"
WH_OUT = (
    REPO
    / "Backtesting Suite"
    / "Data"
    / "NBA"
    / "2025-2026"
    / "warehouse"
    / "derived"
    / "nba"
    / "lebronner"
)

# Locked pooled six-row FIRST75 counts (asked slices only).
N75 = 1126
WIN_NO = 750
WIN_T40 = 121
LOSE_NO = 1
LOSE_T40 = 254

# Locked pooled six-row FIRST80 counts (same clock slices, not retuned).
N80 = 1182
F80_WIN_NO = 883
F80_WIN_T40 = 108
F80_LOSE_NO = 0
F80_LOSE_T40 = 191

# Slice table (FIRST75). Locked after the warehouse run that produced
# research/first75_terminal_path_decomp/REPORT.md.
SLICES = (
    {
        "sport": "WNBA",
        "slice": "2Q",
        "n": 128,
        "W": 105,
        "win_no": 91,
        "win_t40": 14,
        "lose_no": 0,
        "lose_t40": 23,
        "wilson": "74.4782–87.7176",
        "clopper_pearson": "74.2681–88.2551",
        "two_sided_p_vs_75": 0.06665,
        "ci_vs_75": "includes K",
        "p80": 0.826772,
        "s_W_80": 0.847619,
        "joint80": 0.700787,
    },
    {
        "sport": "WNBA",
        "slice": "3Q",
        "n": 85,
        "W": 70,
        "win_no": 59,
        "win_t40": 11,
        "lose_no": 0,
        "lose_t40": 15,
        "wilson": "72.9042–89.0037",
        "clopper_pearson": "72.5695–89.773",
        "two_sided_p_vs_75": 0.1329,
        "ci_vs_75": "includes K",
        "p80": 0.840336,
        "s_W_80": 0.940000,
        "joint80": 0.789916,
    },
    {
        "sport": "NBA",
        "slice": "2Q",
        "n": 318,
        "W": 242,
        "win_no": 208,
        "win_t40": 34,
        "lose_no": 1,
        "lose_t40": 75,
        "wilson": "71.1194–80.4588",
        "clopper_pearson": "71.025–80.6827",
        "two_sided_p_vs_75": 0.6977,
        "ci_vs_75": "includes K",
        "p80": 0.850318,
        "s_W_80": 0.895131,
        "joint80": 0.761146,
    },
    {
        "sport": "NBA",
        "slice": "3Q",
        "n": 258,
        "W": 192,
        "win_no": 167,
        "win_t40": 25,
        "lose_no": 0,
        "lose_t40": 66,
        "wilson": "68.7633–79.3574",
        "clopper_pearson": "68.6384–79.6283",
        "two_sided_p_vs_75": 0.8293,
        "ci_vs_75": "includes K",
        "p80": 0.820690,
        "s_W_80": 0.886555,
        "joint80": 0.727586,
    },
    {
        "sport": "NCAAB P5",
        "slice": "1H second 10",
        "n": 204,
        "W": 152,
        "win_no": 126,
        "win_t40": 26,
        "lose_no": 0,
        "lose_t40": 52,
        "wilson": "68.1146–79.999",
        "clopper_pearson": "67.9537–80.3388",
        "two_sided_p_vs_75": 0.8716,
        "ci_vs_75": "includes K",
        "p80": 0.844560,
        "s_W_80": 0.871166,
        "joint80": 0.735751,
    },
    {
        "sport": "NCAAB P5",
        "slice": "2H first 10",
        "n": 133,
        "W": 110,
        "win_no": 99,
        "win_t40": 11,
        "lose_no": 0,
        "lose_t40": 23,
        "wilson": "75.3858–88.1913",
        "clopper_pearson": "75.1903–88.7103",
        "two_sided_p_vs_75": 0.04463,
        "ci_vs_75": "excludes K",
        "p80": 0.848921,
        "s_W_80": 0.915254,
        "joint80": 0.776978,
    },
)

K75 = 0.75
K80 = 0.80
P_COUNTERFACTUAL = 0.73
S_DISPLAY = 0.6296  # published 62.96% display of the 73% counterfactual S
SENSITIVITY_P = (0.80, 0.773535, 0.75, 0.73, 0.70)

# Named Lebronner payoffs (user-specified, not a Kalshi fill).
LEBRONNER_WIN_CENTS = 20  # FIRST75 trigger costed at 80¢ → +20 if survive to 100
LEBRONNER_STOP_CENTS = -35  # user-stated stop; not the accounting 80→40 (−40)
LEBRONNER_LOSE_HOLD_CENTS = -80  # if a loser survives to expire no after paying 80
NATIVE75_WIN_CENTS = 25
NATIVE75_STOP_CENTS = -35
NATIVE75_LOSE_HOLD_CENTS = -75
TRUE80_WIN_CENTS = 20
TRUE80_STOP_CENTS = -40

# Mechanism A: wait for a 3¢ pullback and enter at 77¢, exit at 40¢.
# Mechanical price improvement only. Selection effect of the pullback is separate.
PULLBACK_ENTRY_CENTS = 77
PULLBACK_WIN_CENTS = 23
PULLBACK_STOP_CENTS = -37
DELTA_S_TARGETS_PP = (1, 2, 3)

SOURCES = {
    "decomp": "research/first75_terminal_path_decomp/REPORT.md",
    "asof": "research/firstq_fourcell_asof_predictor/REPORT.md",
    "slice_script": "apps/nba-data/scripts/first75_slice_not40_given_w.py",
    "asof_script": "apps/nba-data/scripts/firstq_fourcell_asof_predictor.py",
    "program": "research/lebronner/PROGRAM.md",
    "tables": "research/lebronner/TABLES.md",
    "superasi": "research/superasi/README.md",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def halt_if(cond: bool, msg: str) -> None:
    if cond:
        raise RuntimeError(msg)


def rates_from_cells(win_no: int, win_t40: int, lose_no: int, lose_t40: int) -> dict:
    n = win_no + win_t40 + lose_no + lose_t40
    w = win_no + win_t40
    lose = lose_no + lose_t40
    halt_if(n <= 0, "HALT empty cells")
    p = w / n
    s_w = win_no / w if w else None
    s_l = lose_no / lose if lose else None
    joint = win_no / n
    s = (win_no + lose_no) / n
    recon = None if s_w is None else p * s_w + (0.0 if s_l is None else (1.0 - p) * s_l)
    if s_w is not None and recon is not None:
        halt_if(abs(recon - s) > 1e-12, "HALT S identity")
        halt_if(abs(p * s_w - joint) > 1e-12, "HALT product identity")
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
        "cell_probs": {
            "W_and_not_T40": win_no / n,
            "W_and_T40": win_t40 / n,
            "L_and_not_T40": lose_no / n,
            "L_and_T40": lose_t40 / n,
        },
        "p": p,
        "s_W": s_w,
        "s_L": s_l,
        "joint_win_survive": joint,
        "S": s,
        "S_recon": recon,
        "dS_dp": None if s_w is None or s_l is None else s_w - s_l,
        "P_W_given_not_T40": None if (win_no + lose_no) == 0 else win_no / (win_no + lose_no),
        "P_T40_given_L": None if lose == 0 else lose_t40 / lose,
    }


def four_cell_at_p(p: float, s_w: float, s_l: float) -> dict:
    """Hold path conditionals. Not a forecast."""
    return {
        "p": p,
        "s_W": s_w,
        "s_L": s_l,
        "W_and_not_T40": p * s_w,
        "W_and_T40": p * (1.0 - s_w),
        "L_and_not_T40": (1.0 - p) * s_l,
        "L_and_T40": (1.0 - p) * (1.0 - s_l),
        "S": s_l + p * (s_w - s_l),
        "note": "Holds s_W and s_L. Not a forecast.",
    }


def ev_sl_zero(s: float, win_cents: int, stop_cents: int) -> dict:
    """s_L=0 so ¬T40 ⇒ expire yes. EV = win*S + stop*(1-S)."""
    ev = win_cents * s + stop_cents * (1.0 - s)
    be = None if win_cents == stop_cents else -stop_cents / (win_cents - stop_cents)
    return {
        "S": s,
        "s_L": 0.0,
        "win_cents": win_cents,
        "stop_cents": stop_cents,
        "ev_cents": ev,
        "breakeven_S": be,
        "formula": f"EV = {win_cents}S + ({stop_cents})(1-S)",
    }


def ev_four_cell(probs: dict, win_cents: int, stop_cents: int, lose_hold_cents: int) -> float:
    return (
        probs["W_and_not_T40"] * win_cents
        + probs["L_and_not_T40"] * lose_hold_cents
        + (probs["W_and_T40"] + probs["L_and_T40"]) * stop_cents
    )


def ev_survivor_mix(
    s: float,
    p_w_given_survive: float,
    win_cents: int,
    stop_cents: int,
    lose_hold_cents: int,
) -> dict:
    """Hold S and the measured P(W|¬T40). Different from holding s_L."""
    ev = (
        s * p_w_given_survive * win_cents
        + s * (1.0 - p_w_given_survive) * lose_hold_cents
        + (1.0 - s) * stop_cents
    )
    return {
        "S": s,
        "P_W_given_not_T40": p_w_given_survive,
        "win_cents": win_cents,
        "stop_cents": stop_cents,
        "lose_hold_cents": lose_hold_cents,
        "ev_cents": ev,
        "note": "Holds S and historical survivor mix 750/751. Not a forecast.",
    }


def program_math(s_display: float, s_exact: float) -> dict:
    """Locked 2026–27 selection-program arithmetic. Spec only. Not a result."""
    lebronner_be = -LEBRONNER_STOP_CENTS / (LEBRONNER_WIN_CENTS - LEBRONNER_STOP_CENTS)
    pullback = ev_sl_zero(s_display, PULLBACK_WIN_CENTS, PULLBACK_STOP_CENTS)
    pullback_exact = ev_sl_zero(s_exact, PULLBACK_WIN_CENTS, PULLBACK_STOP_CENTS)
    halt_if(pullback["breakeven_S"] is None, "HALT pullback breakeven")
    lifts = []
    for pp in DELTA_S_TARGETS_PP:
        s = s_display + pp / 100.0
        rec = ev_sl_zero(s, LEBRONNER_WIN_CENTS, LEBRONNER_STOP_CENTS)
        lifts.append(
            {
                "delta_S_pp": pp,
                "S": s,
                "ev_cents": rec["ev_cents"],
                "note": "Lebronner +20/−35, s_L=0, display baseline + k pp. Not measured.",
            }
        )
    return {
        "status": "SPEC_ONLY",
        "implementation_authorized": False,
        "live_authorized": False,
        "objective": (
            "Convert an uncertain, marginal unconditional edge into a "
            "conditional selection problem. Viability must not require "
            "terminal miscalibration."
        ),
        "pipeline": [
            "historical universe",
            "conditional state filters",
            "better entry price",
            "higher conditional survival probability",
            "positive EV",
        ],
        "target_object": "P(not T40 | FIRST75, X_tau)",
        "baseline": {
            "p": P_COUNTERFACTUAL,
            "S_display": s_display,
            "S_exact": s_exact,
            "lebronner_ev_cents": 55.0 * s_display - 35.0,
            "lebronner_breakeven_S": lebronner_be,
            "pp_to_breakeven": 100.0 * (lebronner_be - s_display),
        },
        "mechanism_A_price": {
            "entry_cents": PULLBACK_ENTRY_CENTS,
            "win_cents": PULLBACK_WIN_CENTS,
            "stop_cents": PULLBACK_STOP_CENTS,
            "breakeven_S": pullback["breakeven_S"],
            "breakeven_pp_vs_lebronner": 100.0 * (lebronner_be - pullback["breakeven_S"]),
            "ev_at_display_S_cents": pullback["ev_cents"],
            "ev_at_exact_S_cents": pullback_exact["ev_cents"],
            "note": (
                "Mechanical price improvement only. Does not assume the "
                "80→77 pullback improves S. Selection effect is Mechanism B."
            ),
        },
        "delta_S_targets": lifts,
        "iti": {
            "name": "Ian Tali Index",
            "form": "w1 R + w2 Delta + w3 beta + w4 sigma + w5 M",
            "weights_pnl_optimized": False,
            "protocol": [
                "economically motivated feature definitions",
                "coarse pre-specified buckets",
                "training-only calibration",
                "locked thresholds",
                "untouched OOS evaluation",
            ],
            "research_object": "P(not T40 | FIRST75, ITI in A)",
        },
        "layers": [
            "Layer 0 conservative baseline p=73%",
            "Layer 1 path phenomenon P(not T40 | FIRST75)",
            "Layer 2 conditional state selection X_tau",
            "Layer 3 price optimization Ke=77 only if still qualified",
            "Layer 4 execution model (fees, spread, fill, queue, adverse selection)",
            "Layer 5 terminal upside treated as additional uncertainty, not a requirement",
        ],
        "not_the_failed_scoreboard_asof": True,
        "central_experiment": (
            "Can delta, beta, volatility, reversion, and ITI produce a "
            "1–3 pp OOS improvement in S that survives multiple testing "
            "and realistic execution assumptions?"
        ),
    }


def build() -> dict:
    hist75 = rates_from_cells(WIN_NO, WIN_T40, LOSE_NO, LOSE_T40)
    halt_if(hist75["n"] != N75, "HALT N75")
    halt_if(sum(s["n"] for s in SLICES) != N75, "HALT slice n")
    halt_if(sum(s["W"] for s in SLICES) != hist75["W"], "HALT slice W")
    halt_if(sum(s["win_no"] for s in SLICES) != WIN_NO, "HALT slice win_no")
    halt_if(sum(s["win_t40"] for s in SLICES) != WIN_T40, "HALT slice win_t40")
    halt_if(sum(s["lose_no"] for s in SLICES) != LOSE_NO, "HALT slice lose_no")
    halt_if(sum(s["lose_t40"] for s in SLICES) != LOSE_T40, "HALT slice lose_t40")
    hist80 = rates_from_cells(F80_WIN_NO, F80_WIN_T40, F80_LOSE_NO, F80_LOSE_T40)
    halt_if(hist80["n"] != N80, "HALT N80")

    s_w = hist75["s_W"]
    s_l = hist75["s_L"]
    assert s_w is not None and s_l is not None
    cf73 = four_cell_at_p(P_COUNTERFACTUAL, s_w, s_l)
    halt_if(abs(cf73["S"] - (s_l + P_COUNTERFACTUAL * (s_w - s_l))) > 1e-12, "HALT S(p)")

    lebronner = ev_sl_zero(cf73["S"], LEBRONNER_WIN_CENTS, LEBRONNER_STOP_CENTS)
    lebronner_display = ev_sl_zero(S_DISPLAY, LEBRONNER_WIN_CENTS, LEBRONNER_STOP_CENTS)
    native = ev_sl_zero(cf73["S"], NATIVE75_WIN_CENTS, NATIVE75_STOP_CENTS)
    true80 = ev_sl_zero(cf73["S"], TRUE80_WIN_CENTS, TRUE80_STOP_CENTS)
    hist_sl0_native = ev_sl_zero(hist75["S"], NATIVE75_WIN_CENTS, NATIVE75_STOP_CENTS)
    hist_sl0_lebronner = ev_sl_zero(hist75["S"], LEBRONNER_WIN_CENTS, LEBRONNER_STOP_CENTS)

    hist_probs = hist75["cell_probs"]
    cf_probs = {
        "W_and_not_T40": cf73["W_and_not_T40"],
        "W_and_T40": cf73["W_and_T40"],
        "L_and_not_T40": cf73["L_and_not_T40"],
        "L_and_T40": cf73["L_and_T40"],
    }
    sensitivity = [
        {
            "p": p,
            "S": four_cell_at_p(p, s_w, s_l)["S"],
            "label": {
                0.80: "80%",
                0.773535: "77.35% (hist display)",
                0.75: "75%",
                0.73: "73%",
                0.70: "70%",
            }[p],
        }
        for p in SENSITIVITY_P
    ]

    return {
        "name": "Lebronner",
        "written_utc": utc_now(),
        "research_only": True,
        "live_execution_changed": False,
        "candle_path_not_fill": True,
        "sources": SOURCES,
        "historical_first75_pooled_six": hist75,
        "historical_first80_pooled_six": hist80,
        "slices_first75": list(SLICES),
        "alpha": {
            "K75": K75,
            "K80": K80,
            "alpha_75": hist75["p"] - K75,
            "wilson_p": "74.8181–79.7028",
            "clopper_pearson_p": "74.7946–79.7685",
            "wilson_includes_75": True,
            "two_sided_p_vs_75": 0.06824,
            "one_sided_greater_p_vs_75": 0.03571,
            "one_sided_less_p_vs_75": 0.9695,
            "s_L_wilson": "0.0693–2.1876",
            "conclusion": (
                "Observed +2.35 pp vs 75%, but Wilson includes 75%. "
                "Nonzero terminal residual is not established."
            ),
        },
        "sensitivity": {
            "dS_dp": hist75["dS_dp"],
            "formula": "S(p) = s_L + p (s_W - s_L) holding path conditionals",
            "grid": sensitivity,
            "not_a_forecast": True,
        },
        "counterfactual_p_73": cf73,
        "named_ev": {
            "lebronner": {
                **lebronner,
                "display_S": S_DISPLAY,
                "display_ev_cents": lebronner_display["ev_cents"],
                "definition": (
                    "FIRST75 trigger, assumed fill/cost 80¢ so survivor is +20¢; "
                    "user-stated stop −35¢; s_L=0; S from p=0.73 held-path counterfactual."
                ),
                "not_true_80_to_40": True,
            },
            "native_75_plus25_minus35_sl0": native,
            "true_80_to_40_plus20_minus40_sl0": true80,
            "historical_S_sl0_native75": hist_sl0_native,
            "historical_S_sl0_lebronner": hist_sl0_lebronner,
            "historical_four_cell_native75": ev_four_cell(
                hist_probs, NATIVE75_WIN_CENTS, NATIVE75_STOP_CENTS, NATIVE75_LOSE_HOLD_CENTS
            ),
            "cf73_four_cell_native75": ev_four_cell(
                cf_probs, NATIVE75_WIN_CENTS, NATIVE75_STOP_CENTS, NATIVE75_LOSE_HOLD_CENTS
            ),
            "historical_four_cell_lebronner": ev_four_cell(
                hist_probs, LEBRONNER_WIN_CENTS, LEBRONNER_STOP_CENTS, LEBRONNER_LOSE_HOLD_CENTS
            ),
            "cf73_four_cell_lebronner": ev_four_cell(
                cf_probs, LEBRONNER_WIN_CENTS, LEBRONNER_STOP_CENTS, LEBRONNER_LOSE_HOLD_CENTS
            ),
            "cf73_survivor_mix_native75": ev_survivor_mix(
                cf73["S"],
                hist75["P_W_given_not_T40"],
                NATIVE75_WIN_CENTS,
                NATIVE75_STOP_CENTS,
                NATIVE75_LOSE_HOLD_CENTS,
            ),
        },
        "asof_fourcell": {
            "token_first80": "NO_ASOF_LIFT",
            "token_first75": "NO_ASOF_LIFT",
            "features": ["quarter_bin", "score_abs_bin", "lead_state", "home"],
            "first80_oos": {
                "n": 243,
                "logloss_model": 0.836,
                "logloss_uncond": 0.740,
                "delta": 0.096,
                "delta_95": "+0.052 to +0.139",
            },
            "first75_oos": {
                "n": 233,
                "logloss_model": 0.978,
                "logloss_uncond": 0.845,
                "delta": 0.132,
                "delta_95": "+0.086 to +0.178",
            },
            "report": SOURCES["asof"],
        },
        "program": program_math(S_DISPLAY, cf73["S"]),
    }


def _pct(x: float | None, digits: int = 4) -> str:
    if x is None:
        return "—"
    return f"{100.0 * x:.{digits}f}%"


def _pp(x: float, digits: int = 4) -> str:
    return f"{100.0 * x:+.{digits}f}"


def write_report(doc: dict) -> None:
    h = doc["historical_first75_pooled_six"]
    e80 = doc["historical_first80_pooled_six"]
    cf = doc["counterfactual_p_73"]
    lb = doc["named_ev"]["lebronner"]
    native = doc["named_ev"]["native_75_plus25_minus35_sl0"]
    t80 = doc["named_ev"]["true_80_to_40_plus20_minus40_sl0"]
    s_w = h["s_W"]
    s_l = h["s_L"]
    assert s_w is not None and s_l is not None
    ev = doc["named_ev"]
    asof = doc["asof_fourcell"]

    lines = [
        "# Lebronner",
        "",
        "Named archive of the FIRST75 terminal × path experiment: locked",
        "four-cell, α₇₅, as-of `NO_ASOF_LIFT`, the p=73% held-path",
        "counterfactual S ≈ 62.96%, and the named candle-path EV cases.",
        "",
        "Successor name: **SuperASI**. ROLLER +EV alpha decomposition and",
        "in-production 80/40 stop-path EV live in `research/superasi/`.",
        "Lebronner keeps the FIRST75 named −0.37¢ archive.",
        "",
        "```",
        "LIVE EXECUTION = FALSE",
        "CANDLE PATH ≠ ACTUAL FILL",
        "OBSERVED CALIBRATION DEVIATION ≠ PROVEN MARKET INEFFICIENCY",
        "NO FUTURE LABELS IN F_τ",
        "```",
        "",
        "Does not change live FIRST01 / 80/81/83/89. Does not retune FIRST75,",
        "FIRST80, or T40. Reconstructs from locked integers; does not rescan",
        "the tape.",
        "",
        "Source reports:",
        "",
        f"- Decomposition: `{doc['sources']['decomp']}`",
        f"- As-of four-cell: `{doc['sources']['asof']}`",
        f"- Slice script: `{doc['sources']['slice_script']}`",
        f"- 2026–27 selection program (spec only): `{doc['sources']['program']}`",
        "- Lossless FIRST75 / FIRST80 tables: `research/lebronner/TABLES.md`",
        "- SuperASI (rename / in-production EV): `research/superasi/README.md`",
        "",
        "## 1. Named Lebronner number",
        "",
        "FIRST75 is the trigger. The 75¢ quote is assumed to have **cost 80¢**,",
        "so a survivor to expiration yes is **+20¢**. The user-stated stop is",
        "**−35¢**. That −35 is not an 80→40 exit (that would be −40¢).",
        "**s_L = 0**: ¬T40 means expire yes.",
        "",
        "S is not the historical pooled 66.70%. It is the held-path",
        f"counterfactual at p = 73%: **{_pct(cf['S'], 2)}**",
        f"(exact {cf['S']:.6f}; published display 62.96%).",
        "",
        f"**EV = 20S − 35(1 − S) = 55S − 35 = {lb['ev_cents']:.2f}¢** per contract.",
        "",
        f"Display S = 62.96% gives **{lb['display_ev_cents']:.2f}¢** (same to the cent).",
        f"Breakeven S = 35/55 = **{_pct(lb['breakeven_S'], 2)}**.",
        "62.96% is just under that.",
        "",
        "Same S, other locked candle-path payoffs (still s_L = 0, not fills):",
        "",
        "| Case | Win | Stop | Formula | EV at S≈62.96% | Breakeven S |",
        "|---|---:|---:|---|---:|---:|",
        f"| **Lebronner** | +20¢ | −35¢ | 55S − 35 | **{lb['ev_cents']:+.2f}¢** | {_pct(lb['breakeven_S'], 2)} |",
        f"| Native FIRST75 | +25¢ | −35¢ | 60S − 35 | **{native['ev_cents']:+.2f}¢** | {_pct(native['breakeven_S'], 2)} |",
        f"| True 80→40 | +20¢ | −40¢ | 60S − 40 | **{t80['ev_cents']:+.2f}¢** | {_pct(t80['breakeven_S'], 2)} |",
        "",
        "Do not plug 62.96% into the FIRST80 +20/−40 formula and call it",
        "Lebronner. That is a different entry. That row is **−2.22¢**.",
        "",
        "If the measured loser-survivor mix is kept (1 of 751 ¬T40 prints,",
        "i.e. P(W|¬T40)=750/751) at this same S, native EV is",
        f"**{ev['cf73_survivor_mix_native75']['ev_cents']:+.2f}¢**, not materially",
        "different from the s_L = 0 native +2.78¢. Holding s_L instead of the",
        f"survivor mix gives {ev['cf73_four_cell_native75']:+.2f}¢.",
        "",
        "Historical pooled tape (S = 66.70%), same native +25/−35/−75 path:",
        f"**{ev['historical_four_cell_native75']:+.2f}¢** per FIRST75.",
        "Not a live number. Not 2026–27.",
        "",
        "## 2. Locked historical four-cell (six asked rows)",
        "",
        f"N = **{h['n']}**. One observation per FIRST75 event.",
        "",
        "| | ¬T40 | T40 | Terminal |",
        "|---|---:|---:|---:|",
        f"| W | **{h['cells']['W_and_not_T40']}** "
        f"({_pct(h['cell_probs']['W_and_not_T40'])}) | "
        f"{h['cells']['W_and_T40']} ({_pct(h['cell_probs']['W_and_T40'])}) | "
        f"{_pct(h['p'])} |",
        f"| L | {h['cells']['L_and_not_T40']} "
        f"({_pct(h['cell_probs']['L_and_not_T40'])}) | "
        f"{h['cells']['L_and_T40']} ({_pct(h['cell_probs']['L_and_T40'])}) | "
        f"{_pct(1.0 - h['p'])} |",
        f"| | {_pct(h['S'])} | {_pct(1.0 - h['S'])} | 100% |",
        "",
        f"p = P(W | FIRST75) = **{_pct(h['p'])}** (871/1126).",
        f"α₇₅ = p − 0.75 = **{_pp(h['p'] - K75, 2)} pp**.",
        "Wilson 74.82%–79.70% **includes 75%**. Clopper–Pearson 74.79–79.77.",
        "Two-sided exact p = 0.06824. One-sided greater 0.03571, less 0.9695.",
        "Nonzero terminal residual is not established.",
        "",
        f"s_W = P(¬T40 | W) = **{_pct(h['s_W'])}** (750/871).",
        f"s_L = P(¬T40 | L) = **{_pct(h['s_L'])}** (1/255); Wilson 0.07–2.19.",
        f"S = P(¬T40) = **{_pct(h['S'])}** (751/1126).",
        f"P(W ∩ ¬T40) = p · s_W = **{_pct(h['joint_win_survive'])}**.",
        f"P(W | ¬T40) = **{_pct(h['P_W_given_not_T40'])}** (750/751) in this",
        "minute-close sample. That is after the path; it is not in F_τ.",
        "",
        "The single L ∩ ¬T40 is NBA 2Q. Everywhere else in this table, every",
        "measured loser close-touched 40. Minute-close fact, not a continuity",
        "proof. That is why S is 0.09 pp above the product p · s_W.",
        "",
        "## 3. Per-slice FIRST75 (locked)",
        "",
        "| Sport | Slice | N | W | P(W) | α₇₅ | Wilson | two-sided p | CI vs 75% | s_W | s_L | W∩¬T40 | joint | S |",
        "|---|---|---:|---:|---:|---:|---|---:|---|---:|---:|---:|---:|---:|",
    ]
    for s in SLICES:
        rates = rates_from_cells(s["win_no"], s["win_t40"], s["lose_no"], s["lose_t40"])
        lines.append(
            f"| {s['sport']} | {s['slice']} | {s['n']} | {s['W']} | "
            f"{_pct(rates['p'])} | {_pp(rates['p'] - K75, 2)} | {s['wilson']} | "
            f"{s['two_sided_p_vs_75']} | {s['ci_vs_75']} | {_pct(rates['s_W'])} | "
            f"{_pct(rates['s_L'])} | {s['win_no']} | {_pct(rates['joint_win_survive'])} | "
            f"{_pct(rates['S'])} |"
        )
    lines.extend(
        [
            "",
            "Only NCAAB P5 2H first 10 has a Wilson interval that excludes 75%.",
            "The other five include 75%. Weighting is one observation per FIRST75",
            "event, not an unweighted mean of the six rates.",
            "",
            "## 4. Held-path counterfactual at p = 73%",
            "",
            "Hold s_W and s_L at the historical pooled values. **Not a forecast.**",
            "Asks: if terminal probability deteriorated to 73% while the",
            "conditional path distributions stayed exactly as observed, what is",
            "the new four-cell?",
            "",
            f"S(p) = s_L + p(s_W − s_L).  dS/dp = s_W − s_L = **{h['dS_dp']:.6f}**.",
            "A 1 pp drop in p moves S by about 0.857 pp if path conditionals stay fixed.",
            "Δp from 77.3535% to 73% is −4.3535 pp, so ΔS ≈ −3.73 pp.",
            "",
            "| Cell | Historical (p=77.35%) | p=73% held path |",
            "|---|---:|---:|",
            f"| W∩¬T40 | {_pct(h['cell_probs']['W_and_not_T40'])} | {_pct(cf['W_and_not_T40'])} |",
            f"| W∩T40 | {_pct(h['cell_probs']['W_and_T40'])} | {_pct(cf['W_and_T40'])} |",
            f"| L∩¬T40 | {_pct(h['cell_probs']['L_and_not_T40'])} | {_pct(cf['L_and_not_T40'])} |",
            f"| L∩T40 | {_pct(h['cell_probs']['L_and_T40'])} | {_pct(cf['L_and_T40'])} |",
            f"| **S = P(¬T40)** | **{_pct(h['S'])}** | **{_pct(cf['S'])}** |",
            "",
            "That 62.96% is this S(0.73), not a new measurement on the tape.",
            "",
            "| Terminal P(W) | S(p) if path held |",
            "|---:|---:|",
        ]
    )
    for row in doc["sensitivity"]["grid"]:
        mark = "**" if abs(row["p"] - 0.73) < 1e-12 else ""
        lines.append(f"| {mark}{row['label']}{mark} | {mark}{_pct(row['S'])}{mark} |")
    lines.extend(
        [
            "",
            "If p were set to K = 0.75 and s_W held: joint → 64.58%",
            "(Δ −2.03 pp). **Not a forecast.**",
            "",
            "## 5. FIRST80 on the same slices (not retuned)",
            "",
            f"N = **{e80['n']}**. Four-cell {e80['cells']['W_and_not_T40']} / "
            f"{e80['cells']['W_and_T40']} / {e80['cells']['L_and_not_T40']} / "
            f"{e80['cells']['L_and_T40']}.",
            "",
            f"p₈₀ = **{_pct(e80['p'])}**, s_W,₈₀ = **{_pct(e80['s_W'])}**, "
            f"s_L,₈₀ = **{_pct(e80['s_L'] if e80['s_L'] is not None else 0.0)}**, "
            f"joint₈₀ = **{_pct(e80['joint_win_survive'])}**.",
            "",
            "FIRST80 null for α is K = 0.80, not 0.75.",
            "",
            "| Sport | Slice | p₇₅ | s_W,₇₅ | joint₇₅ | p₈₀ | s_W,₈₀ | joint₈₀ |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for s in SLICES:
        rates = rates_from_cells(s["win_no"], s["win_t40"], s["lose_no"], s["lose_t40"])
        lines.append(
            f"| {s['sport']} | {s['slice']} | {_pct(rates['p'])} | {_pct(rates['s_W'])} | "
            f"{_pct(rates['joint_win_survive'])} | {_pct(s['p80'])} | {_pct(s['s_W_80'])} | "
            f"{_pct(s['joint80'])} |"
        )
    lines.extend(
        [
            f"| **pooled six** | asked rows | {_pct(h['p'])} | {_pct(h['s_W'])} | "
            f"{_pct(h['joint_win_survive'])} | {_pct(e80['p'])} | {_pct(e80['s_W'])} | "
            f"{_pct(e80['joint_win_survive'])} |",
            "",
            "The FIRST80 joint is higher mostly because p is higher (83.8% vs",
            "77.4%), not because s_W is a different kind of object. If 2026–27",
            "terminal p moves toward K, watch whether s_W and s_L stay put.",
            "",
            "## 6. As-of four-cell test",
            "",
            "The object is P(four-cell | FIRST_q, F_τ), not another retrospective",
            "rate. Locked F_τ: quarter, |score| bin, lead/trail/tie, home — the",
            "same alpha-decomp bins. W and T40 are labels only. Model = TRAIN",
            "empirical four-cell by stratum, Laplace +1. Baseline = TRAIN",
            "unconditional four-cell. Unaligned rows get the unconditional.",
            "",
            "Locked rule: ESTABLISHED only if VAL and OOS both beat the baseline",
            "on log-loss, and the OOS paired Δ CI excludes 0 on the negative side.",
            "",
            "**Result: `NO_ASOF_LIFT` on both tapes.**",
            "",
            "| Tape | OOS n | log-loss model | log-loss uncond | Δ (model − uncond) | Δ 95% |",
            "|---|---:|---:|---:|---:|---|",
            f"| FIRST80 | {asof['first80_oos']['n']} | {asof['first80_oos']['logloss_model']:.3f} | "
            f"{asof['first80_oos']['logloss_uncond']:.3f} | **+{asof['first80_oos']['delta']:.3f}** | "
            f"{asof['first80_oos']['delta_95']} |",
            f"| FIRST75 | {asof['first75_oos']['n']} | {asof['first75_oos']['logloss_model']:.3f} | "
            f"{asof['first75_oos']['logloss_uncond']:.3f} | **+{asof['first75_oos']['delta']:.3f}** | "
            f"{asof['first75_oos']['delta_95']} |",
            "",
            "The CIs exclude 0 the wrong way: the stratum table is worse than",
            "“ignore the scoreboard and use the historical four-cell.” VALIDATION",
            "says the same. FIRST75 TRAIN is a tiny in-sample dip; that is not",
            "evidence. Q2∪Q3 OOS does not reverse it.",
            "",
            "So: we know the pooled four-cell. We do not yet have an as-of state,",
            "from these bins, that estimates a different expected future",
            "distribution better than the unconditional rates.",
            "",
            f"Details: `{asof['report']}`",
            "",
            "## 7. What this is not",
            "",
            "- Not a live order, fill, or realized P&L.",
            "- Not proof of a tradable inefficiency.",
            "- Lebronner −35¢ is not an 80→40 exit.",
            "- 62.96% is S(p=73%) with path conditionals held, not measured S.",
            "- A high s_W is not an independent FIRST80 path edge.",
            "- L∩¬T40 = 0 is a minute-close measurement, not proof losers cannot skip 40.",
            "- ¬T40 is future information. It is not in F_τ.",
            "- Adding more scoreboard bins after NO_ASOF_LIFT is fishing.",
            "- Path-phenomenon / ITI work is a separate locked program, spec only.",
            "- Not MLB FIRST01.",
            "",
            "## 8. Conditional selection program",
            "",
            "The 2026–27 research objective is to convert this uncertain,",
            "marginal unconditional edge into a **conditional selection problem**.",
            "Full spec: `research/lebronner/PROGRAM.md`.",
            "",
            "Status: **SPEC_ONLY**. Implementation is not authorized. Live is false.",
            "Strategy viability should not require terminal miscalibration.",
            "",
            "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
            "",
        ]
    )
    text = "\n".join(lines) + "\n"
    for dest in (REPORTS, DOCS, WH_OUT):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "REPORT.md").write_text(text)


def write_program(doc: dict) -> None:
    p = doc["program"]
    base = p["baseline"]
    a = p["mechanism_A_price"]
    cf73 = doc["counterfactual_p_73"]
    lines = [
        "# Lebronner program — conditional selection",
        "",
        "How to try to raise Lebronner from the adverse −0.37¢ baseline without",
        "building the strategy on terminal miscalibration. Spec only.",
        "",
        "```",
        "LIVE EXECUTION = FALSE",
        "CANDLE PATH ≠ ACTUAL FILL",
        "OBSERVED CALIBRATION DEVIATION ≠ PROVEN MARKET INEFFICIENCY",
        "NO FUTURE LABELS IN F_τ",
        "SPEC_ONLY — IMPLEMENTATION NOT AUTHORIZED",
        "```",
        "",
        "Does not change live FIRST01 / 80/81/83/89. Does not retune FIRST75,",
        "FIRST80, or T40. Does not reopen the failed scoreboard as-of test.",
        "Does not fit ITI weights to historical P&L.",
        "",
        "Counts and the named −0.37¢: `research/lebronner/REPORT.md`.",
        "Successor name SuperASI (ROLLER +EV / in-production EV stop-path):",
        "`research/superasi/README.md`.",
        "",
        "## Objective",
        "",
        "Convert an uncertain, marginal unconditional edge into a",
        "**conditional selection problem**.",
        "",
        "```",
        "historical universe",
        "  → conditional state filters",
        "  → better entry price",
        "  → higher conditional survival probability",
        "  → positive EV",
        "```",
        "",
        "Every additional filter can overfit. The system is designed around",
        "**prospective falsification**, not historical P&L search.",
        "",
        f"**Status:** `{p['status']}`. Implementation authorized:",
        f"{p['implementation_authorized']}. Live authorized: {p['live_authorized']}.",
        "",
        "## Layer 0 — Conservative baseline (the control universe)",
        "",
        "Deliberately adverse counterfactual, path conditionals held:",
        "",
        f"- P(W | FIRST75) = **73%** (not the historical 77.35%)",
        f"- S = P(¬T40 | FIRST75) = **{_pct(base['S_display'], 2)}** "
        f"(exact {base['S_exact']:.6f})",
        f"- Lebronner payoffs: +20¢ / −35¢, s_L = 0",
        f"- **EV = 55S − 35 = {base['lebronner_ev_cents']:.2f}¢**",
        f"- Breakeven S = **{_pct(base['lebronner_breakeven_S'], 2)}**",
        f"- Gap to breakeven = **{base['pp_to_breakeven']:.2f} pp**",
        "",
        "### The new distribution at a 73% terminal rate",
        "",
        "Holding the conditional path terms fixed (historical s_W and s_L).",
        "**Not a forecast.** This is the mathematically consistent counterfactual.",
        "",
        "| | ¬T40 | T40 | Terminal |",
        "|---|---:|---:|---:|",
        f"| **W** | **{_pct(cf73['W_and_not_T40'])}** | {_pct(cf73['W_and_T40'])} | **73.0000%** |",
        f"| **L** | {_pct(cf73['L_and_not_T40'])} | {_pct(cf73['L_and_T40'])} | 27.0000% |",
        f"| | **{_pct(cf73['S'])}** | {_pct(1.0 - cf73['S'])} | 100% |",
        "",
        f"W∩¬T40 = p · s_W = 0.73 × s_W. S = p s_W + (1−p) s_L = **{_pct(cf73['S'])}**.",
        "That 62.96% is this S(0.73), not a new measurement on the tape.",
        "",
        "This is valuable because it is a **conservative control**.",
        "The question is not “the historical sample made money.” The question is:",
        "",
        "> Suppose terminal conditions deteriorate. Can information available",
        "> **before entry** improve the conditional path distribution enough",
        "> to overcome this adverse baseline?",
        "",
        "Terminal calibration residual is **Layer 5 upside**, not a requirement.",
        "",
        "## Layer 1 — Path phenomenon",
        "",
        "The unconditional entry-time object remains:",
        "",
        "`S = P(¬T40 | FIRST75)`",
        "",
        "That is already measured on the locked six-row universe (66.70%",
        "historical; 62.96% in this 73% world). Filters must beat **this**",
        "baseline, not a new in-sample EV.",
        "",
        "## Layer 2 — Conditional state selection",
        "",
        "Let X_τ be information observable at the potential entry time.",
        "The research object is",
        "",
        "`S(X) = P(¬T40 | FIRST75, X_τ)`",
        "",
        "not historical P&L. A filter is useful only if it produces a robust",
        "",
        "`ΔS(X) = S(X) − S(FIRST75)`",
        "",
        "evaluated **out of sample**.",
        "",
        "Do not search hundreds of indicators for the highest historical EV.",
        "Each filter needs a hypothesis about **why the future path distribution",
        "changes**.",
        "",
        "Candidate observables (hypothesis class, not a fitted model):",
        "",
        "- Δ_market (empirical market sensitivity)",
        "- β (response to game-state / underlying changes)",
        "- σ (local price volatility)",
        "- game state, clock, score differential (already failed as an as-of",
        "  four-cell table: `NO_ASOF_LIFT` — do not reopen those bins)",
        "- price trajectory / reversion state",
        "- phenomenon entries (volatility and delta market dynamics)",
        "- ITI (Ian Tali Index)",
        "",
        "The failed scoreboard as-of test used quarter, |score|, lead/trail/tie,",
        "home. Adding more of those bins after OOS miss is fishing. This program",
        "is a **different feature class** and requires a new locked protocol",
        "before any implementation.",
        "",
        "## Layer 3 — Price optimization (Mechanism A vs B)",
        "",
        "Wait for a roughly 3¢ reversion. If it does not revert toward 77, do",
        "not enter. Two mechanisms must be separated.",
        "",
        "### Mechanism A — mechanical price improvement",
        "",
        "Observe a qualifying state near K = 80¢. Require a pullback and enter",
        f"at K_e = **{a['entry_cents']}¢**. With a 40¢ exit: winner **+{a['win_cents']}¢**,",
        f"stop **{a['stop_cents']}¢**.",
        "",
        f"Breakeven S = 37 / 60 = **{_pct(a['breakeven_S'], 2)}**.",
        f"Lebronner +20/−35 breakeven is 35/55 = **{_pct(base['lebronner_breakeven_S'], 2)}**.",
        f"The better price alone lowers required survival by **{a['breakeven_pp_vs_lebronner']:.2f} pp**.",
        "",
        "That is mechanical. It is not predictive alpha. At the unchanged",
        f"62.96% S, this payoff is **{a['ev_at_display_S_cents']:+.2f}¢**",
        "(still s_L = 0, still not a fill).",
        "",
        "### Mechanism B — selection effect of the pullback",
        "",
        "Requiring 80→77 trades a different population:",
        "",
        "`P(¬T40 | FIRST75, pullback to 77)`",
        "",
        "That rate can be higher, lower, or the same. A pullback can be",
        "deteriorating game information. **Do not assume reversion improves S",
        "because it improves the price.** Measure the selection effect",
        "separately from Mechanism A.",
        "",
        "## Layer 4 — Execution model",
        "",
        "Any claimed EV must later subtract realistic fees, spread, fill",
        "probability, queue loss, partial fills, and adverse selection.",
        "A 1 pp historical improvement is not sufficient once those are in.",
        "Candle path ≠ fill. FIRST80 asked-six stop-path / in-production EV",
        "haircuts are archived under SuperASI, not as a Lebronner filter",
        "and not as a live liquidation rule:",
        "`research/superasi/EV_DECOMPOSITION.md`.",
        "The FIRST75 +20/−35 execution layer is still not a fill model.",
        "",
        "## Layer 5 — Terminal upside, not a requirement",
        "",
        "If a robust path-selection model exists **and** favorites remain",
        "overpriced (P(W | FIRST_q) > K_q), the four-cell is more favorable",
        "than the 73% baseline. Those are two sources:",
        "",
        "1. Path selection improves P(¬T40 | X).",
        "2. Terminal calibration deviation persists.",
        "",
        "The combined world can have large estimated EV. It is **not**",
        "“very, very certain.” Correct language:",
        "",
        "> high estimated expected value with quantified uncertainty.",
        "",
        "Markets and sports distributions can both change. Do not require",
        "Source 2 for the strategy to function.",
        "",
        "## Ian Tali Index (ITI)",
        "",
        "A constrained state score, not a twenty-parameter P&L fit:",
        "",
        "`ITI(X_τ) = w1 R_τ + w2 Δ_τ + w3 β_τ + w4 σ_τ + w5 M_τ`",
        "",
        "- R_τ — reversion / dislocation",
        "- Δ_τ — current market sensitivity",
        "- β_τ — relative response to underlying / game-state changes",
        "- σ_τ — local price volatility",
        "- M_τ — momentum / market-dynamic state",
        "",
        "Weights are **not** chosen to maximize historical P&L. Initial protocol:",
        "",
        "1. economically motivated feature definitions",
        "2. coarse, pre-specified buckets",
        "3. training-only calibration",
        "4. locked thresholds",
        "5. genuinely untouched OOS evaluation",
        "",
        "Then the object is `P(¬T40 | FIRST75, ITI ∈ A)`.",
        "",
        "ITI is unnamed as a live signal. No weights are stored. No buckets",
        "are locked yet.",
        "",
        "## Target: +1 to +3 pp on S, out of sample",
        "",
        "From the 62.96% adverse baseline, Lebronner +20/−35 needs **+0.68 pp**",
        "to theoretical breakeven. The 1–3 pp figure is a **ΔS target**, not a",
        "Wilson CI width and not a live Wilson rate.",
        "",
        "Lebronner payoffs, s_L = 0, display S = 62.96% + k pp. Not measured.",
        "Before fees, spread, queue, adverse selection, and fill uncertainty.",
        "",
        "| ΔS | Conditional S | EV = 55S − 35 |",
        "|---:|---:|---:|",
        f"| 0 (control) | {_pct(base['S_display'], 2)} | **{base['lebronner_ev_cents']:+.2f}¢** |",
    ]
    for row in p["delta_S_targets"]:
        lines.append(
            f"| +{row['delta_S_pp']} pp | {_pct(row['S'], 2)} | **{row['ev_cents']:+.2f}¢** |"
        )
    lines.extend(
        [
            "",
            "Published conversation rounded +1/+2/+3 to +0.16 / +0.71 / +1.26¢.",
            "Reconstructed 55S − 35 at those display S values is the table above.",
            "A 1 pp in-sample lift is not enough to claim an economic edge.",
            "",
            "## Locked research objective",
            "",
            "```",
            "max_f  EV_OOS(f)",
            "```",
            "",
            "subject to:",
            "",
            "- N_OOS ≥ N_min (to be locked before the first run)",
            "- pre-specified interval / test criteria",
            "- effect persists across independent periods",
            "- feature available at entry (in F_τ, no future labels)",
            "- entry rule frozen before OOS",
            "- execution assumptions explicit",
            "",
            "and the more fundamental condition:",
            "",
            "`P(¬T40 | X)_OOS > P(¬T40)_baseline`",
            "",
            "with the improvement evaluated out of sample, not discovered and",
            "validated on the same tape.",
            "",
            "## Central idea",
            "",
            "Strategy viability should not require terminal miscalibration.",
            "",
            "Base EV comes from robust, prospectively validated conditional path",
            "selection. Terminal calibration deviations are additional",
            "uncertainty / upside.",
            "",
            "## Central experiment (not started)",
            "",
            p["central_experiment"],
            "",
            "That is the research engine of the 2026–27 program. It has not been",
            "run. Do not start it by fishing features on the existing OOS miss.",
            "",
            "## Related objects (not Lebronner filters)",
            "",
            "NCAAB P5 2H first-10 FIRST75 post-τ candle vol and score-β:",
            "`research/lebronner/ncaab_h21_beta_vol/REPORT.md`.",
            "Descriptive only. Does not authorize fading H2_1.",
            "",
            "NCAAB P5 H2 opening adverse-delta normalization is a **rejected",
            "mechanism** (quiet ≠ reversion):",
            "`research/ncaab_h2_opening_vol_shock/CONCLUSION.md`.",
            "Do not import it as a Lebronner filter. Do not hunt a subset.",
            "",
            "Next layer (not a filter): NCAAB P5 residual Δ — Level 2",
            "measurement succeeded, recovery failed. Signed state",
            "transitions failed the residual-variance gate. Stop this",
            "branch. Not a profitable subset:",
            "`research/ncaab_conditional_path_decomp/STATUS.md`.",
            "",
            "Neither starts the central experiment.",
            "",
            "## What this is not",
            "",
            "- Not a live order, fill, or realized P&L.",
            "- Not an implemented filter, ITI, or 77¢ entry rule.",
            "- Not proof that Δ, β, σ, or reversion change S.",
            "- Not a claim that Mechanism B is favorable.",
            "- Not authorization to retune FIRST75 / FIRST80 / T40.",
            "- Not MLB FIRST01. Not W9.",
            "",
            "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
            "",
        ]
    )
    text = "\n".join(lines) + "\n"
    for dest in (REPORTS, DOCS, WH_OUT):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "PROGRAM.md").write_text(text)


def write_outputs(doc: dict | None = None) -> dict:
    doc = doc if doc is not None else build()
    write_report(doc)
    write_program(doc)
    from lebronner_tables import write_tables

    write_tables([REPORTS, DOCS, WH_OUT])
    payload = json.dumps(doc, indent=2) + "\n"
    for dest in (REPORTS, DOCS, WH_OUT):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "summary.json").write_text(payload)
    print(
        json.dumps(
            {
                "name": "Lebronner",
                "S_73": doc["counterfactual_p_73"]["S"],
                "lebronner_ev_cents": doc["named_ev"]["lebronner"]["ev_cents"],
                "native_ev_cents": doc["named_ev"]["native_75_plus25_minus35_sl0"]["ev_cents"],
                "true80_ev_cents": doc["named_ev"]["true_80_to_40_plus20_minus40_sl0"]["ev_cents"],
                "program_status": doc["program"]["status"],
                "out": str(REPORTS),
            },
            indent=2,
        )
    )
    return doc


def main() -> int:
    write_outputs()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
