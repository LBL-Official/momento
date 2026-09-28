#!/usr/bin/env python3
"""Write warehouse REPORT.md. LIVE EXECUTION CHANGED: FALSE."""

from __future__ import annotations

import shutil

from common import OUT, REP, SPEC_DIR, load_json, utc_now, write_json


def pct(x, d=2):
    if x is None:
        return "—"
    return f"{x:.{d}f}%"


def num(x, d=4):
    if x is None:
        return "—"
    return f"{x:.{d}f}"


def main() -> int:
    board = load_json(OUT / "scoreboard.json")
    val = load_json(OUT / "validation.json") if (OUT / "validation.json").exists() else {}
    b = board.get("baseline") or {}
    m = board.get("models") or {}
    sp = board.get("splits_close_stop") or {}
    sc = board.get("splits_conservative") or {}
    port = board.get("portfolio_close_stop") or {}
    rs = board.get("research_5pct_scenario") or {}
    lines = []
    a = lines.append
    a("# NBA 80/40 Capture Program v1 — report")
    a("")
    a("Research only. Identifier: `MOMENTO_NBA_CAPTURE_PROGRAM_V1`.")
    a("")
    a("**Question A: CLOSED on 1-minute candles.** No production filter.")
    a("**Question B: OPEN.** Capture as realized EV is unmeasured.")
    a("")
    a("**NO LIVE NBA. NO PRODUCTION FILTER. QUESTION B OPEN.**")
    a("")
    a("LIVE EXECUTION CHANGED: FALSE")
    a("")
    a("This report does not conclude that the strategy makes 74%.")
    a("")
    a("## Frozen close-path baseline")
    a("")
    a(f"- Games: {b.get('games')}")
    a(f"- FIRST-80: {b.get('first80_settled')}")
    a(f"- Survivors: {b.get('survivors_no40')}")
    a(f"- Close-path 40: {b.get('stops_40_close')}")
    a(f"- Survival: {pct(b.get('strategy_win_rate_pct'))} CI {b.get('strategy_win_rate_ci95')}")
    a(f"- Gross EV: {num((m.get('original_close_stop') or {}).get('gross_ev_R'))} R")
    a("")
    a("## Chronological close-stop survival (did not collapse)")
    a("")
    a("| Split | n | Survival |")
    a("| --- | ---: | ---: |")
    for name in ("IN_SAMPLE", "VALIDATION", "OOS"):
        row = sp.get(name) or {}
        a(f"| {name} | {row.get('n')} | {pct(row.get('win_rate_pct'))} |")
    a("")
    a("## Question B scoreboard (candle proxies)")
    a("")
    a("| Model | n | Win rate | Gross EV R |")
    a("| --- | ---: | ---: | ---: |")
    for key, label in (
        ("original_close_stop", "Close-stop"),
        ("high_fill_close_stop", "HIGH fill, close-stop"),
        ("all_fills_wick_stop", "Wick-stop"),
        ("conservative_high_wick", "Conservative HIGH+wick"),
    ):
        row = m.get(key) or {}
        a(f"| {label} | {row.get('n')} | {pct(row.get('win_rate_pct'))} | {num(row.get('gross_ev_R'))} |")
    a("")
    a("Fill filter is noise. Wick-stop is the EV gap. Conservative CI includes breakeven.")
    a("")
    a("## Conservative chronological")
    a("")
    a("| Split | n | Survival |")
    a("| --- | ---: | ---: |")
    for name in ("IN_SAMPLE", "VALIDATION", "OOS"):
        row = sc.get(name) or {}
        a(f"| {name} | {row.get('n')} | {pct(row.get('win_rate_pct'))} |")
    a("")
    a("## Capacity (gross path sim, not fills)")
    a("")
    a(f"- Unlimited max concurrent first-80s: {port.get('max_open_unlimited')}")
    a(f"- Cap=1 accepted/skipped: {port.get('cap1_accepted')} / {port.get('cap1_skipped')}")
    a(f"- Cap=5 accepted/skipped: {port.get('cap5_accepted')} / {port.get('cap5_skipped')}")
    a("")
    a("## Research 5% bankroll scenario (not live)")
    a("")
    a(f"- ≈ {rs.get('approx_ev_bankroll_pct_at_74pct')}% of bankroll / trade at ~74% (ESTIMATED)")
    a(f"- ≈ {rs.get('approx_ev_bankroll_pct_at_69_3pct')}% of bankroll / trade at ~69.3% (ESTIMATED)")
    a(f"- Fills for a +2% week at those EVs: {num(rs.get('fills_for_2pct_week_at_74pct'), 1)} / {num(rs.get('fills_for_2pct_week_at_69_3pct'), 1)}")
    a("- Not a forecast. Not MLB 12.5%.")
    a("")
    a("## Engine B validator")
    a("")
    a(f"- Episode files: {val.get('n_files')} ok={val.get('n_ok')} fail={val.get('n_fail')}")
    a("- Status upgrades are forbidden.")
    a("")
    a("## V1–V4")
    a("")
    qa = board.get("question_a") or {}
    a(f"- V1 {qa.get('v1')}; V2 {qa.get('v2')}; V3 {qa.get('v3')}; V4 {qa.get('v4')}")
    a(f"- V4 skip-high-p VAL lift {qa.get('v4_skip_high_p_val_lift_R')} R; OOS {qa.get('v4_skip_high_p_oos_lift_R')} R")
    a("")
    a("LIVE EXECUTION CHANGED: FALSE")
    a("")
    text = "\n".join(lines) + "\n"
    REP.mkdir(parents=True, exist_ok=True)
    (REP / "REPORT.md").write_text(text)
    (OUT / "REPORT.md").write_text(text)
    for name in (
        "README.md",
        "ENGINE_A_RULE.md",
        "ENGINE_B_LEDGER.md",
        "QUESTION_B_SCOREBOARD.md",
        "WEEKLY_CAPACITY.md",
        "NON_GOALS.md",
        "PROSPECTIVE_CAPTURE.md",
    ):
        src = SPEC_DIR / name
        if src.exists():
            shutil.copyfile(src, REP / name)
    write_json(
        OUT / "summary.json",
        {
            "written_utc": utc_now(),
            "program": "MOMENTO_NBA_CAPTURE_PROGRAM_V1",
            "question_a": "CLOSED_ON_1M_CANDLES",
            "question_b": "OPEN",
            "production_filter": False,
            "live_nba": False,
            "live_execution_changed": False,
            "scoreboard": str(OUT / "scoreboard.json"),
            "validation": val,
        },
    )
    print("REPORT written; LIVE EXECUTION CHANGED: FALSE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
