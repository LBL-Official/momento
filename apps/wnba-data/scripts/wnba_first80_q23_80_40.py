#!/usr/bin/env python3
"""WNBA FIRST80 80→40 restricted to Q2 and Q3 entries.

Uses the frozen n=589 FIRST80 tape and ESPN PBP quarter alignment.
Does not redefine FIRST80. Candle path, not fills.

Also reports how many Q2∪Q3 40-losers first close-touch 40 with
≤5:00 remaining in the 4th quarter.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
NBA_SCRIPTS = Path("/Users/user/Desktop/Momento/apps/nba-data/scripts")
# WNBA scripts first so first80_quarter_barrier_survival is the WNBA module.
sys.path.insert(0, str(NBA_SCRIPTS))
sys.path.insert(0, str(SCRIPTS))

import first80_quarter_barrier_survival as Q  # noqa: E402
import nba_80_40_execution_audit as A  # noqa: E402
import wnba_80_40_execution_audit as W  # noqa: E402
import wnba_pbp_align as P  # noqa: E402
import first80_q2_40_loser_late_clock as LATE  # noqa: E402

# Importing W locks the a-priori WNBA splits on A.
assert A.SPLIT_RESEARCH_END == "2025-10-31"
assert A.SPLIT_VAL_END == "2026-07-15"
assert Q.EXPECTED_N == 589

OUT = (
    Path(
        "/Users/user/Desktop/Momento/Backtesting Suite/Data/WNBA/2025-2026/warehouse"
    )
    / "derived"
    / "wnba"
    / "first80_q23_80_40"
)
REPORTS = Path("/Users/user/Desktop/Momento/research/wnba_first80_q23_80_40")
DOCS = Path("/Users/user/Desktop/Momento/docs/research/wnba_first80_q23_80_40")

Q23 = ("Q2", "Q3")
# Locked to the already-published quarter-barrier partition (2026-09-04).
EXPECTED_Q2 = 127
EXPECTED_Q3 = 119
EXPECTED_Q23 = EXPECTED_Q2 + EXPECTED_Q3
EXPECTED_JOINTS = {
    "Q2": {
        "n": 127,
        "W": 105,
        "T40": 38,
        "win_no_t40": 89,
        "win_t40": 16,
        "loss_no_t40": 0,
        "loss_t40": 22,
    },
    "Q3": {
        "n": 119,
        "W": 100,
        "T40": 25,
        "win_no_t40": 94,
        "win_t40": 6,
        "loss_no_t40": 0,
        "loss_t40": 19,
    },
    "Q2∪Q3": {
        "n": 246,
        "W": 205,
        "T40": 63,
        "win_no_t40": 183,
        "win_t40": 22,
        "loss_no_t40": 0,
        "loss_t40": 41,
    },
}
# Frozen after the first Q2∪Q3 last-5 measurement. Do not retune the clock.
EXPECTED_LAST5 = {"Q2": 13, "Q3": 13, "Q2∪Q3": 26}
CLOSING_PERIOD = 4
OT_MIN_PERIOD = 5
LAST5_MIN = 5
R_CENTS = A.R_CENTS


class IdentityHalt(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_rows() -> list[dict]:
    frozen = Q.load_frozen_first80()
    Q.halt_unless_identity(frozen)
    xwalk = P.load_crosswalk()
    pbp_cache: dict = {}
    rows = []
    for rec in frozen:
        align = Q.align_entry(rec, xwalk, pbp_cache)
        won = bool(rec["expiration_result_yes"])
        t40 = bool(rec.get("stop_close_triggered"))
        t40_ts = rec.get("first_40_close_ts")
        espn_id = align.get("espn_game_id")
        actions = (Q._pbp_pack(espn_id, pbp_cache) if espn_id else None) or []
        t40_clock = {
            "t40_period": None,
            "t40_period_remaining_s": None,
            "t40_remaining_clock": None,
        }
        if t40 and t40_ts is not None and actions:
            ck = P.snap_clock(actions, int(t40_ts))
            t40_clock = {
                "t40_period": ck["period"],
                "t40_period_remaining_s": ck["period_remaining_s"],
                "t40_remaining_clock": Q.format_clock(ck["period_remaining_s"])
                if ck.get("period") == CLOSING_PERIOD
                else Q.format_clock(ck["game_seconds_remaining"]),
            }
        rows.append(
            {
                "event_id": rec.get("event_id"),
                "ticker": rec.get("ticker"),
                "team": rec.get("team"),
                "game_date": rec.get("game_date"),
                "dataset_split": A.dataset_split(rec.get("game_date")),
                "regime": W.wnba_regime(rec.get("game_date")),
                "W": won,
                "T40": t40,
                "first_80_timestamp": rec.get("first_80_timestamp"),
                "first_40_close_ts": t40_ts,
                "entry_quarter_bucket": align["entry_quarter_bucket"],
                "alignment_confidence": align["alignment_confidence"],
                "alignment_reason": align["alignment_reason"],
                **t40_clock,
            }
        )
    return rows


def joints(rows: list[dict]) -> dict:
    n = len(rows)
    w = sum(1 for r in rows if r["W"])
    t40 = sum(1 for r in rows if r["T40"])
    win_no = sum(1 for r in rows if r["W"] and not r["T40"])
    win_t40 = sum(1 for r in rows if r["W"] and r["T40"])
    lose_no = sum(1 for r in rows if (not r["W"]) and not r["T40"])
    lose_t40 = sum(1 for r in rows if (not r["W"]) and r["T40"])
    wr, lo, hi = A.wilson(win_no, n)
    ev_cents = None if n == 0 else (win_no * R_CENTS + t40 * (-2 * R_CENTS)) / n
    return {
        "n": n,
        "W": w,
        "T40": t40,
        "win_no_t40": win_no,
        "win_t40": win_t40,
        "loss_no_t40": lose_no,
        "loss_t40": lose_t40,
        "p_win_pct": A.rate(w, n),
        "strategy_win_rate_pct": wr,
        "strategy_win_rate_ci95": [lo, hi],
        "gross_ev_R": None if ev_cents is None else round(ev_cents / R_CENTS, 4),
        "gross_ev_cents": None if ev_cents is None else round(ev_cents, 4),
    }


def by_split(rows: list[dict]) -> dict:
    out = {}
    for split in ("IN_SAMPLE", "VALIDATION", "OOS"):
        out[split] = joints([r for r in rows if r["dataset_split"] == split])
    return out


def last5_t40(period, remaining_s) -> bool:
    return LATE.hit_with_at_most_k_min(
        period,
        remaining_s,
        LAST5_MIN,
        closing_period=CLOSING_PERIOD,
        ot_min_period=OT_MIN_PERIOD,
    )


def _joint_keys(block: dict) -> dict:
    return {k: block[k] for k in EXPECTED_JOINTS["Q2∪Q3"]}


def halt_unless_published_joints(name: str, block: dict) -> None:
    got = _joint_keys(block)
    exp = EXPECTED_JOINTS[name]
    if got != exp:
        raise IdentityHalt(f"HALT {name} joints {got} expected {exp}")


def loser_late_clock(rows: list[dict], bucket: str | None) -> dict:
    if bucket is None:
        tagged = [{**r, "_slice": "Q2∪Q3"} for r in rows]
        return LATE.analyze_slice(
            tagged,
            entry_field="_slice",
            bucket="Q2∪Q3",
            expected_n=EXPECTED_Q23,
            expected_losers=EXPECTED_JOINTS["Q2∪Q3"]["loss_t40"],
            expected_t40=EXPECTED_JOINTS["Q2∪Q3"]["T40"],
            closing_period=CLOSING_PERIOD,
            ot_min_period=OT_MIN_PERIOD,
            closing_label="4Q",
            label="Q2∪Q3",
        )
    return LATE.analyze_slice(
        rows,
        entry_field="entry_quarter_bucket",
        bucket=bucket,
        expected_n=EXPECTED_JOINTS[bucket]["n"],
        expected_losers=EXPECTED_JOINTS[bucket]["loss_t40"],
        expected_t40=EXPECTED_JOINTS[bucket]["T40"],
        closing_period=CLOSING_PERIOD,
        ot_min_period=OT_MIN_PERIOD,
        closing_label="4Q",
        label=bucket,
    )


def analyze(rows: list[dict] | None = None) -> dict:
    rows = rows if rows is not None else load_rows()
    part = dict(Counter(r["entry_quarter_bucket"] for r in rows))
    if part.get("Q2") != EXPECTED_Q2 or part.get("Q3") != EXPECTED_Q3:
        raise IdentityHalt(f"HALT Q2/Q3 partition {part} expected Q2={EXPECTED_Q2} Q3={EXPECTED_Q3}")
    q23 = [r for r in rows if r["entry_quarter_bucket"] in Q23]
    if len(q23) != EXPECTED_Q23:
        raise IdentityHalt(f"HALT Q23 n={len(q23)}")
    q2_j = joints([r for r in q23 if r["entry_quarter_bucket"] == "Q2"])
    q3_j = joints([r for r in q23 if r["entry_quarter_bucket"] == "Q3"])
    q23_j = joints(q23)
    halt_unless_published_joints("Q2", q2_j)
    halt_unless_published_joints("Q3", q3_j)
    halt_unless_published_joints("Q2∪Q3", q23_j)
    leak = [r for r in q23 if (not r["W"]) and not r["T40"]]
    if leak:
        raise IdentityHalt(f"HALT Q23 LOSS∧¬T40 n={len(leak)}")

    late_union = loser_late_clock(q23, None)
    late_union["bucket"] = "Q2∪Q3"
    late_by = {
        "Q2": loser_late_clock(q23, "Q2"),
        "Q3": loser_late_clock(q23, "Q3"),
        "Q2∪Q3": late_union,
    }
    last5 = {}
    for name, block in late_by.items():
        hit = next(c for c in block["cumulative_at_most_k_min"] if c["at_most_min"] == LAST5_MIN)
        if hit["n"] != EXPECTED_LAST5[name]:
            raise IdentityHalt(
                f"HALT {name} last-5 Q4 40-losers n={hit['n']} expected {EXPECTED_LAST5[name]}"
            )
        last5[name] = {
            "n_losers": block["n_losers"],
            "n_t40": block["n_t40"],
            "n_last_5_q4": hit["n"],
            "pct_of_losers": hit["pct_of_losers"],
            "pct_of_t40": hit["pct_of_t40"],
            "pct_of_slice": hit["pct_of_slice"],
        }

    summary = {
        "written_utc": utc_now(),
        "research_only": True,
        "candle_path_not_fill": True,
        "live_execution_changed": False,
        "universe": "KXWNBAGAME FIRST80 with ESPN PBP entry in Q2 or Q3",
        "quarter_definition": (
            "ESPN PBP period of last play with observed wall <= first_80_timestamp; "
            "WNBA regulation 4 x 10:00"
        ),
        "last_5_definition": (
            "first tradable yes_bid_close <= 40 while period==4 and period remaining <= 5:00. "
            "OT is not last-5 regulation."
        ),
        "excluded_from_q23": {
            "Q1": part.get("Q1", 0),
            "Q4": part.get("Q4", 0),
            "OT": part.get("OT", 0),
            "UNALIGNED": part.get("UNALIGNED", 0),
        },
        "partition": part,
        "q2": q2_j,
        "q3": q3_j,
        "q23": q23_j,
        "splits_q23": by_split(q23),
        "last_5_minutes_40_losers": last5,
        "late_clock": late_by,
    }
    return {"summary": summary, "rows": q23}


def write_report(summary: dict) -> None:
    q = summary["q23"]
    last = summary["last_5_minutes_40_losers"]
    excl = summary["excluded_from_q23"]
    lines = [
        "# WNBA FIRST80 80→40 — Q2 and Q3 only",
        "",
        "Research only. Same frozen FIRST80 / close-40 rule, restricted to",
        "ESPN-aligned **2nd-quarter and 3rd-quarter** entries.",
        "",
        "```",
        "LIVE EXECUTION = FALSE",
        "CANDLE PATH ≠ ACTUAL FILL",
        "```",
        "",
        f"Universe: **{q['n']}** FIRST80 prints (Q2={summary['q2']['n']}, Q3={summary['q3']['n']}) "
        "out of the frozen settled FIRST80 tape (n=589). Excluded from this cut: "
        f"Q1={excl['Q1']}, Q4={excl['Q4']}, OT={excl['OT']}, "
        f"UNALIGNED={excl['UNALIGNED']} (no ESPN quarter tag; not treated as Q2 or Q3).",
        "",
        "## 1. Observed 80→40 path (Q2 ∪ Q3)",
        "",
        "| | Q2 | Q3 | Q2 ∪ Q3 |",
        "|---|---:|---:|---:|",
    ]
    for key, label in (
        ("n", "FIRST80"),
        ("W", "Wins (Kalshi yes)"),
        ("win_no_t40", "WIN ∧ ¬T40"),
        ("win_t40", "WIN ∧ T40"),
        ("loss_no_t40", "LOSS ∧ ¬T40"),
        ("loss_t40", "LOSS ∧ T40"),
        ("T40", "T40 close"),
    ):
        lines.append(
            f"| {label} | {summary['q2'][key]} | {summary['q3'][key]} | {q[key]} |"
        )
    lines.extend(
        [
            "",
            f"Strategy win rate (hold unless close-stop): **{q['strategy_win_rate_pct']}%**  ",
            f"95% Wilson CI: **{q['strategy_win_rate_ci95'][0]}% – {q['strategy_win_rate_ci95'][1]}%** "
            f"(n = {q['n']})",
            "",
            f"P(Kalshi yes \\| FIRST80, Q2∪Q3) = **{q['p_win_pct']}%**  ",
            f"Gross EV (+20¢ / −40¢ candle path) = **{q['gross_ev_R']} R**",
            "",
            "### Splits (a priori; not retuned)",
            "",
        ]
    )
    for split, v in summary["splits_q23"].items():
        lines.append(
            f"- **{split}**: n={v['n']} win={v['strategy_win_rate_pct']}% "
            f"CI {v['strategy_win_rate_ci95']} EV_R={v['gross_ev_R']}"
        )
    u = last["Q2∪Q3"]
    lines.extend(
        [
            "",
            "## 2. 40-losers in the last 5 minutes",
            "",
            "A **40-loser** is a FIRST80 that expired no and close-touched 40",
            "(LOSS ∧ T40). Clock is **4Q remaining** at the first tradable",
            "`yes_bid_close ≤ 40¢`. OT is not last-5 regulation.",
            "",
            "| Entry | 40-losers | T40 in last 5:00 of 4Q | % of losers |",
            "|---|---:|---:|---:|",
            f"| Q2 | {last['Q2']['n_losers']} | {last['Q2']['n_last_5_q4']} | {last['Q2']['pct_of_losers']}% |",
            f"| Q3 | {last['Q3']['n_losers']} | {last['Q3']['n_last_5_q4']} | {last['Q3']['pct_of_losers']}% |",
            f"| **Q2 ∪ Q3** | **{u['n_losers']}** | **{u['n_last_5_q4']}** | **{u['pct_of_losers']}%** |",
            "",
            "Cumulative 4Q remaining at the 40 print (Q2 ∪ Q3 losers):",
            "",
        ]
    )
    for row in summary["late_clock"]["Q2∪Q3"]["cumulative_at_most_k_min"]:
        lines.append(
            f"- {row['label']}: **{row['n']}** ({row['pct_of_losers']}% of losers)"
        )
    lines.extend(
        [
            "",
            "Discrete bins (Q2 ∪ Q3 losers):",
            "",
        ]
    )
    for row in summary["late_clock"]["Q2∪Q3"]["discrete_bins"]:
        lines.append(f"- {row['bin']}: {row['n']} ({row['pct_of_losers']}%)")
    lines.extend(
        [
            "",
            "## 3. What this is not",
            "",
            "- Not a live order, fill, or realized P&L.",
            "- Not Q1 / Q4 / OT / unaligned FIRST80.",
            "- Not MLB FIRST01.",
            "",
            "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
            "",
        ]
    )
    text = "\n".join(lines) + "\n"
    for dest in (OUT, REPORTS, DOCS):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "REPORT.md").write_text(text)


def write_outputs(result: dict) -> None:
    summary = result["summary"]
    for dest in (OUT, REPORTS, DOCS):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        (dest / "q23_trades.json").write_text(json.dumps(result["rows"]) + "\n")
    write_report(summary)
    q = summary["q23"]
    last = summary["last_5_minutes_40_losers"]["Q2∪Q3"]
    print(
        json.dumps(
            {
                "q23": q["n"],
                "win_rate_pct": q["strategy_win_rate_pct"],
                "ci95": q["strategy_win_rate_ci95"],
                "gross_ev_R": q["gross_ev_R"],
                "losers": last["n_losers"],
                "last_5_q4_losers": last["n_last_5_q4"],
                "pct_of_losers": last["pct_of_losers"],
                "out": str(OUT),
                "live_execution_changed": False,
            },
            indent=2,
        )
    )


def main() -> int:
    write_outputs(analyze())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
