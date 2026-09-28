#!/usr/bin/env python3
"""SuperASI — alpha decomposition of ROLLER +EV (rename of Lebronner).

Decomposes in-production EV into terminal efficiency, path efficiency,
and stop-path / liquidation realization. Reconstructs from locked
integers. Does not rescan the tape. Does not change live FIRST01.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

REPO = Path("/Users/user/Desktop/Momento")
REPORTS = REPO / "research" / "superasi"
DOCS = REPO / "docs" / "research" / "superasi"
WH_OUT = (
    REPO
    / "Backtesting Suite"
    / "Data"
    / "NBA"
    / "2025-2026"
    / "warehouse"
    / "derived"
    / "nba"
    / "superasi"
)

# Asked-six FIRST80 four-cell (same clock slices as Lebronner TABLES).
N80 = 1182
F80_WIN_NO = 883
F80_WIN_T40 = 108
F80_LOSE_NO = 0
F80_LOSE_T40 = 191

ENTRY_CENTS = 80
WIN_CENTS = 20
LEDGER_STOP_LOSS_CENTS = 40
PLAN_EV_CENTS = Fraction(5, 2)

# First tradable close ≤40 on the 299 STOP_40 trades (stop_loss.csv).
T40_N = 299
T40_CLOSE_SUM = 10318
T40_PRINTED_40 = 54
T40_LT40 = 245
T40_LE35 = 128
T40_FAST_GAP = 181
MIN5_N = 298
MIN5_CLOSE_SUM = 7291

# ±5m yes_bid_close sums around T40 (t40_surround_pm5.csv).
# offset → (n_candles, sum_bid_close)
SURROUND = {
    -5: (299, 18262),
    -4: (299, 17582),
    -3: (299, 17022),
    -2: (299, 16167),
    -1: (299, 14663),
    0: (299, 10318),
    1: (299, 10102),
    2: (299, 10023),
    3: (299, 10031),
    4: (297, 9945),
    5: (297, 9724),
}
PRE_T40_38_40_TRADES = 1


def halt_if(cond: bool, msg: str) -> None:
    if cond:
        raise RuntimeError(msg)


def _q(x: Fraction, places: int = 6) -> float:
    return round(float(x), places)


def _pct(x: Fraction, places: int = 4) -> str:
    return f"{float(x) * 100:.{places}f}%"


def rates_from_cells(
    win_no: int, win_t40: int, lose_no: int, lose_t40: int
) -> dict:
    n = win_no + win_t40 + lose_no + lose_t40
    halt_if(n <= 0, "HALT empty four-cell")
    w = win_no + win_t40
    lose = lose_no + lose_t40
    p = Fraction(w, n)
    s_w = Fraction(win_no, w) if w else None
    s_l = Fraction(lose_no, lose) if lose else None
    s = Fraction(win_no + lose_no, n)
    joint = Fraction(win_no, n)
    halt_if(s_w is None or s_l is None, "HALT missing path term")
    recon = s_l + p * (s_w - s_l)
    halt_if(recon != s, "HALT S ≠ p·s_W + (1−p)·s_L")
    halt_if(joint != p * s_w, "HALT joint ≠ p·s_W")
    return {
        "n": n,
        "W": w,
        "L": lose,
        "p": p,
        "alpha_vs_K80": p - Fraction(4, 5),
        "s_W": s_w,
        "s_L": s_l,
        "S": s,
        "joint_win_survive": joint,
        "win_no": win_no,
        "win_t40": win_t40,
        "lose_no": lose_no,
        "lose_t40": lose_t40,
    }


def ev_survive_stop(s: Fraction, win_cents: int, stop_loss_cents) -> dict:
    """Rule EV: survive → +win, stop → −L. s_L = 0 on this book."""
    loss = Fraction(stop_loss_cents)
    ev = s * win_cents - (1 - s) * loss
    be_s = loss / (win_cents + loss)
    be_l = (s * win_cents) / (1 - s) if s != 1 else None
    return {
        "S": s,
        "win_cents": win_cents,
        "stop_loss_cents": loss,
        "ev_cents": ev,
        "breakeven_S": be_s,
        "breakeven_L": be_l,
        "formula": f"EV = {win_cents}S − L(1−S)",
    }


def implied_stop_loss(s: Fraction, win_cents: int, ev: Fraction) -> Fraction:
    halt_if(s == 1, "HALT implied L undefined at S=1")
    return (s * win_cents - ev) / (1 - s)


def build() -> dict:
    halt_if(
        F80_WIN_NO + F80_WIN_T40 + F80_LOSE_NO + F80_LOSE_T40 != N80,
        "HALT FIRST80 cells",
    )
    halt_if(F80_WIN_T40 + F80_LOSE_T40 != T40_N, "HALT T40 n")
    halt_if(T40_PRINTED_40 + T40_LT40 != T40_N, "HALT printed+lt40")
    halt_if(T40_CLOSE_SUM != SURROUND[0][1], "HALT T40 sum ≠ offset-0 sum")

    r = rates_from_cells(F80_WIN_NO, F80_WIN_T40, F80_LOSE_NO, F80_LOSE_T40)
    s = r["S"]
    halt_if(s != Fraction(F80_WIN_NO, N80), "HALT S ≠ 883/1182")

    t40_mean_close = Fraction(T40_CLOSE_SUM, T40_N)
    t40_mean_loss = Fraction(T40_N * ENTRY_CENTS - T40_CLOSE_SUM, T40_N)
    halt_if(t40_mean_loss != ENTRY_CENTS - t40_mean_close, "HALT L ≠ 80−exit")

    min5_mean_close = Fraction(MIN5_CLOSE_SUM, MIN5_N)
    min5_mean_loss = Fraction(MIN5_N * ENTRY_CENTS - MIN5_CLOSE_SUM, MIN5_N)

    ledger = ev_survive_stop(s, WIN_CENTS, LEDGER_STOP_LOSS_CENTS)
    t40_ev = ev_survive_stop(s, WIN_CENTS, t40_mean_loss)
    min5_ev = ev_survive_stop(s, WIN_CENTS, min5_mean_loss)
    plan_l = implied_stop_loss(s, WIN_CENTS, PLAN_EV_CENTS)
    plan = ev_survive_stop(s, WIN_CENTS, plan_l)
    halt_if(plan["ev_cents"] != PLAN_EV_CENTS, "HALT plan EV")

    surround = {
        str(off): {
            "n": n,
            "sum_bid_close": total,
            "mean_bid_close": _q(Fraction(total, n), 6),
        }
        for off, (n, total) in SURROUND.items()
    }

    return {
        "name": "SuperASI",
        "legacy_name": "Lebronner",
        "status": "SPEC_ONLY",
        "implementation_authorized": False,
        "live_authorized": False,
        "live_execution": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "constraints": [
            "LIVE EXECUTION = FALSE",
            "CANDLE PATH ≠ ACTUAL FILL",
            "LEDGER 40 ≠ PROVEN FILL",
            "TERMINAL ALPHA ≠ PATH ALPHA",
            "PATH SURVIVAL ≠ INDEPENDENT EDGE",
            "STOP-PATH REALIZATION ≠ LIVE LIQUIDATION RULE",
            "DO NOT CHANGE LIVE FIRST01 / 80/81/83/89",
            "DO NOT START W9",
            "DO NOT RETUNE FIRST80 / T40 FROM THESE TABLES",
        ],
        "mission": (
            "Alpha decomposition of positive-EV strategies generated from "
            "ROLLER. Enhancements attach to in-production EV in research by "
            "decomposing EV and deconstructing terminal efficiency and path "
            "efficiency. SuperASI does not submit orders."
        ),
        "first80_asked_six": {
            "n": N80,
            "four_cell": {
                "W_and_not_T40": F80_WIN_NO,
                "W_and_T40": F80_WIN_T40,
                "L_and_not_T40": F80_LOSE_NO,
                "L_and_T40": F80_LOSE_T40,
            },
            "terminal_p": _q(r["p"]),
            "terminal_p_frac": f"{r['W']}/{r['n']}",
            "alpha_vs_K80_pp": _q(r["alpha_vs_K80"] * 100, 4),
            "s_W": _q(r["s_W"]),
            "s_L": _q(r["s_L"]),
            "S_rule_80_40": _q(r["S"]),
            "S_frac": f"{F80_WIN_NO}/{N80}",
            "joint_win_survive": _q(r["joint_win_survive"]),
            "note": (
                "In-production 80/40 win rate is S = P(¬T40) = 883/1182, "
                "not terminal P(W) = 991/1182. The 108 W∩T40 settled YES "
                "after the stop and are 80/40 losers."
            ),
        },
        "in_production_ev": {
            "label": "FIRST80_ASKED_SIX_80_40_LEDGER",
            "win_cents": WIN_CENTS,
            "stop_loss_cents": LEDGER_STOP_LOSS_CENTS,
            "S": _q(s),
            "ev_cents": _q(ledger["ev_cents"], 4),
            "ev_frac": f"{ledger['ev_cents'].numerator}/{ledger['ev_cents'].denominator}",
            "breakeven_S": _q(ledger["breakeven_S"], 6),
            "breakeven_L_at_S": _q(ledger["breakeven_L"], 4),
        },
        "stop_path": {
            "label": "CANDLE_T40_CLOSE_NOT_FILL",
            "n": T40_N,
            "printed_40": T40_PRINTED_40,
            "first_close_lt40": T40_LT40,
            "first_close_le35": T40_LE35,
            "fast_gap": T40_FAST_GAP,
            "t40_close_sum": T40_CLOSE_SUM,
            "mean_t40_close": _q(t40_mean_close, 4),
            "mean_stop_loss": _q(t40_mean_loss, 4),
            "ev_cents": _q(t40_ev["ev_cents"], 4),
            "min5_n": MIN5_N,
            "min5_close_sum": MIN5_CLOSE_SUM,
            "mean_min5_close": _q(min5_mean_close, 4),
            "mean_min5_stop_loss": _q(min5_mean_loss, 4),
            "min5_ev_cents": _q(min5_ev["ev_cents"], 4),
            "pre_t40_38_40_trades": PRE_T40_38_40_TRADES,
            "surround": surround,
        },
        "research_planning_ev": {
            "label": "USER_STATED_PLUS_2_5",
            "ev_cents": _q(PLAN_EV_CENTS, 2),
            "implied_mean_stop_loss": _q(plan_l, 4),
            "implied_mean_exit": _q(ENTRY_CENTS - plan_l, 4),
            "note": (
                "Planning haircut on in-production 80/40 EV. Not a fill. "
                "Not a retune of the 40 stop rule."
            ),
        },
        "layers": [
            {
                "id": "T",
                "name": "terminal_efficiency",
                "object": "P(W | trigger) − K",
                "source": "research/first75_terminal_path_decomp/TERMINAL_PATH_REPORT.md",
            },
            {
                "id": "P",
                "name": "path_efficiency",
                "object": "s_W, s_L, S, four-cell (W,L)×(¬T40,T40)",
                "source": "research/first80_alpha_decomposition_v1/METHODOLOGY.md",
            },
            {
                "id": "X",
                "name": "stop_path_realization",
                "object": "E[exit | T40] and the ±5m path to T40",
                "source": "research/first80_asked_six_t40_surround_candles/",
            },
            {
                "id": "E",
                "name": "in_production_ev",
                "object": "ledger 80/40 vs T40-close EV vs planning +2.5¢",
                "source": "research/superasi/EV_DECOMPOSITION.md",
            },
        ],
        "sources": {
            "legacy_archive": "research/lebronner/REPORT.md",
            "legacy_program": "research/lebronner/PROGRAM.md",
            "terminal_path": "research/first75_terminal_path_decomp/TERMINAL_PATH_REPORT.md",
            "alpha_decomp_v1": "research/first80_alpha_decomposition_v1/FINAL_RESEARCH_REPORT.md",
            "asked_six_ledger": "research/first80_asked_six_80_40_liquidation/",
            "stop_loss": "research/first80_asked_six_80_40_stop_loss/",
            "surround": "research/first80_asked_six_t40_surround_candles/t40_surround_pm5.csv",
            "roller": "ROLLER/",
        },
    }


def write_readme(doc: dict) -> None:
    lines = [
        "# SuperASI",
        "",
        "Rename of **Lebronner**. Research-only alpha decomposition of",
        "positive-EV strategies generated from ROLLER.",
        "",
        "```",
        "LIVE EXECUTION = FALSE",
        "CANDLE PATH ≠ ACTUAL FILL",
        "LEDGER 40 ≠ PROVEN FILL",
        "TERMINAL ALPHA ≠ PATH ALPHA",
        "PATH SURVIVAL ≠ INDEPENDENT EDGE",
        "DO NOT CHANGE LIVE FIRST01 / 80/81/83/89",
        "DO NOT START W9",
        "```",
        "",
        doc["mission"],
        "",
        f"**Status:** `{doc['status']}`. Implementation authorized: "
        f"{doc['implementation_authorized']}. Live authorized: "
        f"{doc['live_authorized']}.",
        "",
        "Lebronner remains the FIRST75 named-archive label",
        "(`research/lebronner/`). SuperASI is the successor program that",
        "consumes ROLLER +EV objects and attaches stop-path realization to",
        "**in-production EV** without changing the live 80/40 rule.",
        "",
        "## What SuperASI does",
        "",
        "1. Take a ROLLER-generated +EV strategy (first object: asked-six",
        "   FIRST80 80/40).",
        "2. Decompose EV. Do not treat a single ledger number as alpha.",
        "3. Deconstruct **terminal efficiency** — P(W | trigger) vs K.",
        "4. Deconstruct **path efficiency** — s_W, s_L, four-cell, S.",
        "5. Deconstruct **stop-path realization** — E[exit | T40], the",
        "   ±5m window, printed-40 vs blow-through.",
        "6. Publish a research planning EV that haircuts the ledger.",
        "",
        "## What SuperASI does not do",
        "",
        "- Submit, approve, or route orders. Strategy proposes; Risk",
        "  approves; Execution executes.",
        "- Change live FIRST01 / 80/81/83/89 or the 40 stop **rule**.",
        "- Treat candle path as a Kalshi fill.",
        "- Hunt a profitable subset. Do not start W9.",
        "- Import Lebronner −35¢ as an 80→40 exit.",
        "- Park a 40/45 sell at entry, or buy the opponent at 60 at entry.",
        "",
        "## First object — asked-six FIRST80 80/40",
        "",
        f"- N = **{N80}**. Rule survivors S = **{F80_WIN_NO}/{N80}** "
        f"({_pct(Fraction(F80_WIN_NO, N80), 2)}).",
        f"- Terminal P(W) = **991/{N80}**. The 108 W∩T40 are 80/40 losers.",
        f"- Ledger EV at −40¢ = **{_q(Fraction(5700, N80), 2)}¢**.",
        f"- T40-close EV (mean first close {T40_CLOSE_SUM}/{T40_N}¢) = "
        f"**{_q(Fraction(4058, N80), 2)}¢**.",
        f"- Planning EV = **+2.50¢** ⇒ implied mean stop loss "
        f"**{_q(Fraction(14705, T40_N), 1)}¢**.",
        "",
        "Full identities: `research/superasi/EV_DECOMPOSITION.md`.",
        "Named numbers: `research/superasi/REPORT.md`.",
        "",
        "## Documented layers (do not re-derive)",
        "",
        "| Layer | Object | Already documented |",
        "|---|---|---|",
        "| Terminal | P(W) − K | `research/first75_terminal_path_decomp/` |",
        "| Path | four-cell, s_W, s_L | `research/first80_alpha_decomposition_v1/` |",
        "| FIRST75 archive | named −0.37¢ | `research/lebronner/` |",
        "| Stop-path | T40 close, ±5m | `research/first80_asked_six_*` |",
        "| In-production EV | ledger vs haircut | this directory |",
        "",
        "Alpha-decomp v1 classification on the NBA audit book remains",
        "`A_TERMINAL_CALIBRATION_ONLY`. SuperASI does not reopen that as",
        "an independent path edge.",
        "",
        "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
        "",
    ]
    text = "\n".join(lines)
    for dest in (REPORTS, DOCS, WH_OUT):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "README.md").write_text(text)


def write_ev_decomp(doc: dict) -> None:
    r = rates_from_cells(F80_WIN_NO, F80_WIN_T40, F80_LOSE_NO, F80_LOSE_T40)
    s = r["S"]
    t40_l = Fraction(T40_N * ENTRY_CENTS - T40_CLOSE_SUM, T40_N)
    min5_l = Fraction(MIN5_N * ENTRY_CENTS - MIN5_CLOSE_SUM, MIN5_N)
    ledger = ev_survive_stop(s, WIN_CENTS, LEDGER_STOP_LOSS_CENTS)
    t40_ev = ev_survive_stop(s, WIN_CENTS, t40_l)
    min5_ev = ev_survive_stop(s, WIN_CENTS, min5_l)
    plan_l = implied_stop_loss(s, WIN_CENTS, PLAN_EV_CENTS)

    def row(off: int) -> str:
        n, total = SURROUND[off]
        mean = Fraction(total, n)
        return (
            f"| {off:+d} | {n} | {total} | **{float(mean):.1f}** |"
        )

    lines = [
        "# SuperASI — EV decomposition",
        "",
        "In-production EV is not a single number. SuperASI splits it into",
        "terminal efficiency, path efficiency, and stop-path realization.",
        "Candle path, not fills. Does not change the live 80/40 rule.",
        "",
        "```",
        "LIVE EXECUTION = FALSE",
        "CANDLE PATH ≠ ACTUAL FILL",
        "LEDGER 40 ≠ PROVEN FILL",
        "```",
        "",
        "## 1. Locked identities",
        "",
        "Trigger FIRST_q. K is the triggering quote, not a fill.",
        "",
        "```",
        "p   = P(W | FIRST_q)",
        "α   = p − K",
        "s_W = P(¬T40 | W, FIRST_q)",
        "s_L = P(¬T40 | L, FIRST_q)",
        "S   = P(¬T40 | FIRST_q) = p · s_W + (1 − p) · s_L",
        "P(W ∩ ¬T40 | FIRST_q) = p · s_W",
        "```",
        "",
        "These terms are not independent edges. Documented in",
        "`research/first75_terminal_path_decomp/TERMINAL_PATH_REPORT.md`",
        "and `research/first80_alpha_decomposition_v1/METHODOLOGY.md`.",
        "",
        "On asked-six FIRST80, s_L = 0, so S = p · s_W = 883/1182.",
        "",
        "## 2. Two different “win rates”",
        "",
        "| Object | Count | Rate | Role |",
        "|---|---:|---:|---|",
        f"| Terminal P(W) | 991/{N80} | {_pct(r['p'], 2)} | settlement yes |",
        f"| Path S = P(¬T40) | {F80_WIN_NO}/{N80} | {_pct(s, 2)} | **80/40 rule wins** |",
        f"| W∩T40 | {F80_WIN_T40} | {_pct(Fraction(F80_WIN_T40, N80), 2)} | settled yes, 80/40 loser |",
        "",
        "In-production EV uses **S**, not terminal p. Do not plug 83.84%",
        "into +20/−40.",
        "",
        "## 3. In-production EV (ledger)",
        "",
        "```",
        "EV_ledger = 20S − 40(1 − S) = 60S − 40",
        "```",
        "",
        f"S = 883/1182 ⇒ **EV_ledger = {ledger['ev_cents']} = "
        f"{_q(ledger['ev_cents'], 2)}¢**.",
        f"Breakeven S at L=40 is 40/60 = {_pct(ledger['breakeven_S'], 2)}.",
        f"Breakeven L at this S is "
        f"{_q(ledger['breakeven_L'], 2)}¢ (exit ≈ "
        f"{_q(ENTRY_CENTS - ledger['breakeven_L'], 2)}¢).",
        "",
        "This is the labeled 80/40 book. It assumes every T40 exits at 40.",
        "That assumption is the research object SuperASI removes next.",
        "",
        "## 4. Stop-path realization (enhancement)",
        "",
        "```",
        "L_x = E[80 − exit_x | T40]",
        "EV_x = 20S − L_x (1 − S)",
        "```",
        "",
        "exit_x is a **candle** measurement, not a proven Kalshi fill.",
        "",
        "| Mix x | n | Mean exit | Mean L | EV at S=883/1182 |",
        "|---|---:|---:|---:|---:|",
        f"| Ledger 40 | {T40_N} | 40 | 40 | **{_q(ledger['ev_cents'], 2)}¢** |",
        f"| First T40 close | {T40_N} | {T40_CLOSE_SUM}/{T40_N} = {_q(Fraction(T40_CLOSE_SUM, T40_N), 2)} | {_q(t40_l, 2)} | **{_q(t40_ev['ev_cents'], 2)}¢** |",
        f"| Planning +2.5¢ | {T40_N} | {_q(ENTRY_CENTS - plan_l, 2)} | {_q(plan_l, 2)} | **+2.50¢** |",
        f"| 5m min after T40 | {MIN5_N} | {MIN5_CLOSE_SUM}/{MIN5_N} = {_q(Fraction(MIN5_CLOSE_SUM, MIN5_N), 2)} | {_q(min5_l, 2)} | **{_q(min5_ev['ev_cents'], 2)}¢** |",
        "",
        f"Exact 40 on first tradable ≤40 close: **{T40_PRINTED_40}/{T40_N}**.",
        f"First close already <40: **{T40_LT40}/{T40_N}**.",
        f"First close ≤35: **{T40_LE35}/{T40_N}**.",
        f"FAST_GAP (prior >40, through 40, drop ≥10): **{T40_FAST_GAP}/{T40_N}**.",
        "",
        "Keep the 40 **rule**. Do not move the stop to 45. Do not treat 40",
        "as an executable resting sell while the bid is still 50–60.",
        "",
        "## 5. Path to the stop (±5m)",
        "",
        "Source: `research/first80_asked_six_t40_surround_candles/t40_surround_pm5.csv`.",
        "",
        "| Offset | n | Sum bid | Mean close |",
        "|---:|---:|---:|---:|",
        row(-5),
        row(-1),
        row(0),
        row(5),
        "",
        f"Trades with a 38–40 close in the five minutes **before** T40:",
        f"**{PRE_T40_38_40_TRADES}/{T40_N}**. The stop arrives as a one-minute",
        "gap from the high 40s. A 40/45 maker ask does not sit on that path.",
        "",
        "## 6. What a SuperASI enhancement is allowed to change",
        "",
        "Allowed in research:",
        "",
        "- which EV mix is used for planning (ledger / T40-close / +2.5¢)",
        "- how ROLLER +EV is reported after terminal × path × stop-path",
        "- documentation of why the ledger overstates executable EV",
        "",
        "Not allowed:",
        "",
        "- live liquidation style",
        "- FIRST80 / T40 / FIRST01 parameter retune",
        "- treating any mix as a proven fill",
        "",
        "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
        "",
    ]
    text = "\n".join(lines)
    for dest in (REPORTS, DOCS, WH_OUT):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "EV_DECOMPOSITION.md").write_text(text)


def write_report(doc: dict) -> None:
    r = doc["first80_asked_six"]
    e = doc["in_production_ev"]
    x = doc["stop_path"]
    p = doc["research_planning_ev"]
    lines = [
        "# SuperASI",
        "",
        "Successor name for **Lebronner**. Alpha decomposition of +EV",
        "strategies generated from ROLLER. First object: asked-six FIRST80",
        "in-production 80/40 EV, split into terminal, path, and stop-path.",
        "",
        "```",
        "LIVE EXECUTION = FALSE",
        "CANDLE PATH ≠ ACTUAL FILL",
        "LEDGER 40 ≠ PROVEN FILL",
        "SPEC_ONLY — IMPLEMENTATION NOT AUTHORIZED",
        "```",
        "",
        "Does not change live FIRST01 / 80/81/83/89. Does not retune",
        "FIRST75, FIRST80, or T40. Reconstructs from locked integers.",
        "",
        "Lebronner FIRST75 archive (named −0.37¢, p=73% held-path S):",
        "`research/lebronner/REPORT.md`. That −35¢ stop is still not an",
        "80→40 exit.",
        "",
        "## 1. Rename",
        "",
        "| | |",
        "|---|---|",
        "| Legacy | Lebronner |",
        "| Current | SuperASI |",
        f"| Status | `{doc['status']}` |",
        "| Live | FALSE |",
        "| Consumes | ROLLER +EV strategy objects |",
        "| First production-EV object | asked-six FIRST80 80/40 |",
        "",
        "## 2. Asked-six FIRST80 four-cell",
        "",
        f"N = **{r['n']}**. One observation per FIRST80 event.",
        "",
        "| | ¬T40 | T40 | Terminal |",
        "|---|---:|---:|---:|",
        f"| W | **{F80_WIN_NO}** | {F80_WIN_T40} | {_pct(Fraction(991, N80), 4)} |",
        f"| L | {F80_LOSE_NO} | {F80_LOSE_T40} | {_pct(Fraction(191, N80), 4)} |",
        f"| | {_pct(Fraction(F80_WIN_NO, N80), 4)} | {_pct(Fraction(T40_N, N80), 4)} | 100% |",
        "",
        f"p = **{r['terminal_p_frac']}** = {_pct(Fraction(991, N80), 2)}. "
        f"α₈₀ = **{r['alpha_vs_K80_pp']:+.2f} pp**.",
        f"s_W = 883/991. s_L = 0. S = **{r['S_frac']}** = {_pct(Fraction(F80_WIN_NO, N80), 2)}.",
        "",
        r["note"],
        "",
        "## 3. In-production EV vs research mixes",
        "",
        "| Mix | Mean stop L | EV |",
        "|---|---:|---:|",
        f"| Ledger 80/40 | 40¢ | **{e['ev_cents']:+.2f}¢** |",
        f"| First T40 close | {x['mean_stop_loss']:.2f}¢ | **{x['ev_cents']:+.2f}¢** |",
        f"| Planning (user) | {p['implied_mean_stop_loss']:.2f}¢ | **{p['ev_cents']:+.2f}¢** |",
        f"| 5m min after T40 | {x['mean_min5_stop_loss']:.2f}¢ | **{x['min5_ev_cents']:+.2f}¢** |",
        "",
        "Planning +2.5¢ is the SuperASI research haircut on in-production",
        "EV. It is not a live retune and not a proven fill.",
        "",
        "## 4. Stop-path (299 T40 trades)",
        "",
        f"- Exact 40 first print: **{x['printed_40']}/{x['n']}**.",
        f"- First print <40: **{x['first_close_lt40']}/{x['n']}**.",
        f"- First print ≤35: **{x['first_close_le35']}/{x['n']}**.",
        f"- FAST_GAP: **{x['fast_gap']}/{x['n']}**.",
        f"- Mean T40 close: **{x['mean_t40_close']:.2f}¢** (sum {x['t40_close_sum']}).",
        f"- Mean bid at t−1: **{x['surround']['-1']['mean_bid_close']:.1f}¢**.",
        f"- 38–40 close in the five minutes before T40: **{x['pre_t40_38_40_trades']}/{x['n']}**.",
        "",
        "CSV: `research/first80_asked_six_t40_surround_candles/t40_surround_pm5.csv`.",
        "",
        "## 5. Layers",
        "",
        "Identities: `research/superasi/EV_DECOMPOSITION.md`.",
        "Program home: `research/superasi/README.md`.",
        "FIRST75 named cases stay on `research/lebronner/`.",
        "",
        "## 6. What this is not",
        "",
        "- Not a live order, fill, or realized P&L.",
        "- Not authorization to flatten at 45.",
        "- Not a hedge. Opponent-at-60 at entry is not a lock.",
        "- Not an independent FIRST80 path edge (v1 remains A).",
        "- Not MLB FIRST01. Not W9.",
        "",
        "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
        "",
    ]
    text = "\n".join(lines)
    for dest in (REPORTS, DOCS, WH_OUT):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "REPORT.md").write_text(text)


def write_outputs(doc: dict | None = None) -> dict:
    doc = doc if doc is not None else build()
    write_readme(doc)
    write_ev_decomp(doc)
    write_report(doc)
    payload = json.dumps(doc, indent=2) + "\n"
    for dest in (REPORTS, DOCS, WH_OUT):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "summary.json").write_text(payload)
    print(
        json.dumps(
            {
                "name": doc["name"],
                "legacy_name": doc["legacy_name"],
                "S": doc["first80_asked_six"]["S_frac"],
                "ev_ledger_cents": doc["in_production_ev"]["ev_cents"],
                "ev_t40_cents": doc["stop_path"]["ev_cents"],
                "ev_plan_cents": doc["research_planning_ev"]["ev_cents"],
                "status": doc["status"],
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
