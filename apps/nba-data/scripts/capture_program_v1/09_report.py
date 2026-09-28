#!/usr/bin/env python3
"""STEP 15 — REPORT.md and summary.json. Verdict is QUESTION B OPEN."""

from __future__ import annotations

import shutil

from common import (
    DIR_BASELINE,
    DIR_CAP,
    DIR_EXEC,
    DIR_FEE,
    DIR_FILL,
    DIR_LEDGER,
    DIR_PORT,
    DIR_STOP,
    DIR_VAL,
    FROZEN_GROSS_EV_R,
    FROZEN_N,
    FROZEN_P,
    FROZEN_STOPS_CLOSE,
    FROZEN_SURVIVORS,
    OUT,
    REP,
    SPEC_DIR,
    load_json,
    provenance,
    write_json,
)


def pct(x, d=2):
    if x is None:
        return "—"
    return f"{100.0 * x:.{d}f}%" if abs(x) <= 1.5 else f"{x:.{d}f}%"


def num(x, d=4):
    if x is None:
        return "—"
    return f"{x:.{d}f}"


def main() -> int:
    base = load_json(DIR_BASELINE / "summary.json")
    exec_c = load_json(DIR_EXEC / "catalog.json")
    fill = load_json(DIR_FILL / "summary.json")
    stop = load_json(DIR_STOP / "summary.json")
    fee = load_json(DIR_FEE / "summary.json")
    cap = load_json(DIR_CAP / "summary.json")
    port = load_json(DIR_PORT / "summary.json")
    post = load_json(DIR_PORT / "posterior_edge.json")
    ns = load_json(DIR_PORT / "nonstationarity.json")
    live = load_json(DIR_LEDGER / "summary.json")
    val = load_json(OUT / "validation.json") if (OUT / "validation.json").exists() else {}

    regions = exec_c.get("region_counts") or {}
    featured = port.get("featured") or {}
    pub = featured.get("A_iid_path_f5_published") or {}
    p65 = featured.get("A_iid_p65_f5_pub") or {}
    fill70 = featured.get("A_iid_fill70_f5_pub") or {}

    identity = cap.get("identity") or []
    id_path_1 = next((r for r in identity if r.get("world") == "path_73_98" and r.get("p_fill") == 1.0), {})
    id_path_07 = next((r for r in identity if r.get("world") == "path_73_98" and r.get("p_fill") == 0.7), {})

    lines = []
    a = lines.append
    a("# NBA 80/40 Capture Program v1 — report")
    a("")
    a("Research only. Identifier: `MOMENTO_NBA_CAPTURE_PROGRAM_V1`.")
    a("")
    a("**Question A: CLOSED** on 1-minute candles. No production filter.")
    a("**Question B: OPEN.** Capture as realized EV is unmeasured.")
    a("")
    a("**NO LIVE NBA. NO PRODUCTION FILTER. QUESTION B OPEN.**")
    a("")
    a("LIVE EXECUTION CHANGED: FALSE")
    a("")
    a("```text")
    a("FEE MODEL STATUS: UNRESOLVED")
    a("```")
    a("")
    a("This report does not conclude that the strategy is profitable.")
    a("Historical path EV is not realized executable EV.")
    a("")
    a("## 1. Frozen historical path (Question A)")
    a("")
    a("Status: **OBSERVED candle path**. Not executed fills.")
    a("")
    a(f"- Universe: {FROZEN_N}")
    a(f"- Survivors: {FROZEN_SURVIVORS}")
    a(f"- Close-path 40: {FROZEN_STOPS_CLOSE}")
    a(f"- Survival: {pct(FROZEN_P, 2)} ({FROZEN_SURVIVORS}/{FROZEN_N})")
    a(f"- EV_gross = 3p − 2: **{num(FROZEN_GROSS_EV_R)} R**")
    a("- p_BE (zero fee, 40¢ stop): **66.67%**")
    a(f"- Reproduced without modifying source: {base.get('reproduced')}")
    a("")
    a("```text")
    a("HISTORICAL PATH")
    a("NOT EXECUTED FILLS")
    a("```")
    a("")
    a("## 2. Core equation")
    a("")
    a("```text")
    a("EV_realized = P(F) · EV_filled − C_execution")
    a("```")
    a("")
    a("A 74% candle statistic with negative realized execution EV is not a strategy.")
    a("")
    a("## 3. Execution waterfall (live)")
    a("")
    wf = live.get("waterfall") or {}
    a("| Stage | n | Status |")
    a("| --- | ---: | --- |")
    for key, label in (
        ("signals", "Signals"),
        ("orders_attempted", "Orders attempted"),
        ("orders_filled", "Orders filled"),
        ("partial_fills", "Partial fills"),
        ("full_positions", "Full positions"),
        ("stop_events", "Stop events"),
        ("stop_fills", "Stop fills"),
        ("settlements", "Settlements"),
    ):
        row = wf.get(key) or {}
        a(f"| {label} | {row.get('n', 0)} | {row.get('status', 'UNAVAILABLE')} |")
    a("")
    a(f"Live episodes: **{live.get('n_episodes', 0)}**. Fabricated: {live.get('fabricated')}.")
    a("")
    a("## 4. Economic surface (simulated)")
    a("")
    a(f"- Grid rows: {exec_c.get('n_rows')}")
    a(f"- REGION A (EV_R ≥ 0.10 under stated assumptions): {regions.get('A_robust')}")
    a(f"- REGION B (0 < EV_R < 0.10): {regions.get('B_sensitive')}")
    a(f"- REGION C (EV_R ≤ 0): {regions.get('C_unprofitable')}")
    a("- Label: `SIMULATED_EXECUTION_SCENARIO`. Not a production claim.")
    a("")
    a("At the historical 73.98% path, zero fees, exact 40¢ stop, P_fill=1, α=1:")
    a(f"EV_realized = EV_gross = {num(fill.get('e0_ev_realized_R'))} R (E0 idealized).")
    a("")
    a("## 5. Entry capture")
    a("")
    a("| Item | Status |")
    a("| --- | --- |")
    a("| Observed maker fill rate | UNAVAILABLE |")
    a("| Partial-fill distribution | UNAVAILABLE |")
    a("| Time-to-fill | UNAVAILABLE |")
    a("| Missed-signal rate | UNAVAILABLE |")
    a("| E0–E3 grids | SIMULATED |")
    a("")
    a(f"E0 reproduces path EV: {fill.get('e0_matches_path_ev')}.")
    a("")
    a("## 6. Stop capture")
    a("")
    s0 = stop.get("s0_close_path") or {}
    s1 = stop.get("s1_wick") or {}
    a("| Model | n | Stops | p | Status |")
    a("| --- | ---: | ---: | ---: | --- |")
    a(f"| S0 close-path | {s0.get('n')} | {s0.get('stops')} | {pct(s0.get('p'))} | OBSERVED candle path |")
    a(f"| S1 wick / bid_low | {s1.get('n')} | {s1.get('stops_bid_low')} | {pct(s1.get('p'))} | ESTIMATED proxy |")
    a("| S2 stop prints 40→30 | — | — | — | SIMULATED_EXECUTION_SCENARIO |")
    a("")
    a("Observed stop-fill price distribution: **UNAVAILABLE**.")
    a("Close-40 and wick-40 remain separate. Wick is not an executable 40.00 fill.")
    a("")
    a("## 7. Fees")
    a("")
    a("```text")
    a("FEE MODEL STATUS: UNRESOLVED")
    a("```")
    a("")
    a("| Model | Status |")
    a("| --- | --- |")
    a("| ZERO_FEE_MODEL | SIMULATED |")
    a("| PUBLISHED_SCHEDULE_ESTIMATE | ESTIMATED |")
    a("| CUSTOM_STRESS_MODEL | SIMULATED |")
    a("| OBSERVED_PRODUCTION_MODEL | UNAVAILABLE |")
    a("")
    chk = (fee.get("audit_checkpoint") or {})
    a(f"Published-schedule checkpoint vs frozen audit e6: {chk.get('matches_frozen_audit_e6')}.")
    a("")
    a("## 8. Capacity")
    a("")
    a("SIGNAL CAPACITY (frozen overlap, not fills):")
    a("")
    a("| Cap | Accepted | Skipped | Max open |")
    a("| --- | ---: | ---: | ---: |")
    a("| 1 | 505 | 725 | 1 |")
    a("| 5 | 1,192 | 38 | 5 |")
    a("| Unlimited | 1,230 | 0 | 8 |")
    a("")
    a("EXECUTABLE CAPITAL CAPACITY: **UNAVAILABLE**.")
    a("")
    a("| World (f=5%, zero fee, stop 40) | P_fill | EV / trade (bankroll) | N for +2% week |")
    a("| --- | ---: | ---: | ---: |")
    a(
        f"| Path 73.98% | 100% | {pct(id_path_1.get('ev_bankroll_f5'), 3)} | "
        f"{num(id_path_1.get('n_for_2pct'), 1)} |"
    )
    a(
        f"| Path 73.98% | 70% | {pct(id_path_07.get('ev_bankroll_f5'), 3)} | "
        f"{num(id_path_07.get('n_for_2pct'), 1)} |"
    )
    a("")
    a("If EV_realized ≤ 0, N_required is undefined. Identity, not a forecast.")
    a("")
    a("## 9. Portfolio simulation")
    a("")
    a("```text")
    a("SCENARIO ANALYSIS")
    a("NOT A PERFORMANCE FORECAST")
    a("```")
    a("")
    a(f"IID paths per featured scenario: {port.get('n_mc')}.")
    a("Do not read any compounded terminal multiple as an expected return.")
    a("")
    a("| Scenario | Median × | P5 × | P(DD≥20%) |")
    a("| --- | ---: | ---: | ---: |")
    for key, label in (
        ("A_iid_path_f5_published", "Path 73.98%, fill=1, published fees, f=5%"),
        ("A_iid_fill70_f5_pub", "Path 73.98%, fill=70%, published fees, f=5%"),
        ("A_iid_p65_f5_pub", "Regime p=65%, fill=1, published fees, f=5%"),
        ("A_iid_gov1_f5_pub", "Governor 1 DD schedule, otherwise path/published/f=5%"),
        ("B_weekly_blocks_f5_pub", "Season weekly-block bootstrap, published fees, f=5%"),
        ("B_monthly_blocks_f5_pub", "Season monthly-block bootstrap, published fees, f=5%"),
        ("W_iid_8_path_f5_pub", "Weekly slice: 8 trades, path 73.98%, fill=1"),
        ("W_iid_8_fill70_f5_pub", "Weekly slice: 8 trades, fill=70%"),
        ("W_iid_8_p65_f5_pub", "Weekly slice: 8 trades, p=65%"),
    ):
        row = featured.get(key) or {}
        a(
            f"| {label} | {num(row.get('median_equity_multiple'), 3)} | "
            f"{num(row.get('p5_equity_multiple'), 3)} | {pct(row.get('p_dd_20'))} |"
        )
    a("")
    a("## 10. Posterior edge monitor")
    a("")
    a(f"- Prior: p≈{post.get('prior_p')} (haircut, not a claim of the true rate)")
    a(f"- Prior mean / 95% CI: {num(post.get('prior_mean'))} / {post.get('prior_ci95')}")
    a(f"- P(p > 66.67% | prior): {pct(post.get('P_p_gt_p_be_gross_prior'))}")
    a("- Historical candle-path update is **ESTIMATED**, not live fills:")
    a(f"  posterior mean {num(post.get('posterior_mean'))}, CI {post.get('posterior_ci95')}")
    a(f"  P(p > 66.67% | candle path): {pct(post.get('P_p_gt_p_be_gross_hist'))}")
    a(f"- Live observations: **{post.get('live_observations')}**. Live posterior = prior.")
    a("")
    a("## 11. Non-stationarity (candle path, not fills)")
    a("")
    roll = ns.get("rolling") or {}
    a(f"- Last 25 / 50 / 100 / full: {pct(roll.get('last_25'))} / {pct(roll.get('last_50'))} / {pct(roll.get('last_100'))} / {pct(roll.get('full'))}")
    a(f"- CUSUM: {(ns.get('cusum') or {}).get('status')}")
    a(f"- Beta-binomial tail (last-25 failures | historical posterior): {num(ns.get('beta_binomial_p_tail_last25_failures'), 3)}")
    a(f"- Status: **{ns.get('change_detection_status')}**")
    a("- Do not declare edge decay from a short losing streak.")
    a("")
    a("## 12. Promotion gates")
    a("")
    a("| Gate | Result |")
    a("| --- | --- |")
    a("| 1 Entry capture | FAIL / UNAVAILABLE |")
    a("| 2 Stop capture | FAIL / UNAVAILABLE |")
    a("| 3 Fees | FAIL / UNRESOLVED |")
    a("| 4 Net EV observed | FAIL / UNAVAILABLE |")
    a("| 5 Executable capacity | FAIL / UNAVAILABLE |")
    a("| 6 Live risk | NOT EVALUATED ON LIVE DATA |")
    a("")
    a("## 13. Validation")
    a("")
    a(f"- Frozen source unmodified: {val.get('frozen_source_unmodified')}")
    a(f"- Reproduced 1,230 / 910 / 320: {val.get('reproduced_1230_910_320')}")
    a(f"- Live ledger rows: {val.get('live_ledger_rows')}")
    a(f"- Validator ok: {val.get('ok')}")
    a("")
    a("## 14. Next decision (not made here)")
    a("")
    a("The next useful step is to choose an initial capture mode after explicit authorization:")
    a("")
    a("- `paper ledger`")
    a("- `tiny real orders`")
    a("- `full simulated execution`")
    a("")
    a("This program does not arm any of them.")
    a("")
    a("## Verdict")
    a("")
    a("```text")
    a("VERDICT = QUESTION B OPEN")
    a("```")
    a("")
    a("Not VERDICT A. Not VERDICT B. Not VERDICT C.")
    a("Observed execution does not yet exist, so no economic robustness claim is allowed.")
    a("")
    a("LIVE EXECUTION CHANGED: FALSE")
    a("")

    text = "\n".join(lines) + "\n"
    REP.mkdir(parents=True, exist_ok=True)
    (REP / "REPORT.md").write_text(text)
    (OUT / "REPORT.md").write_text(text)

    for name in (
        "README.md",
        "MISSION.md",
        "QUESTION_A_FROZEN.md",
        "QUESTION_B_EXECUTION.md",
        "ECONOMIC_MODEL.md",
        "EXECUTION_ASSUMPTIONS.md",
        "FEE_MODEL.md",
        "CAPACITY_MODEL.md",
        "LIVE_LEDGER_SCHEMA.md",
        "PROMOTION_GATES.md",
        "RISK_MODEL.md",
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

    summary = {
        **provenance(),
        "question_a": "CLOSED",
        "question_b": "OPEN",
        "verdict": "QUESTION B OPEN",
        "production_filter": False,
        "live_nba": False,
        "live_execution_changed": False,
        "FEE_MODEL_STATUS": "UNRESOLVED",
        "frozen": {
            "n": FROZEN_N,
            "survivors": FROZEN_SURVIVORS,
            "stops": FROZEN_STOPS_CLOSE,
            "p": FROZEN_P,
            "ev_gross_R": FROZEN_GROSS_EV_R,
        },
        "regions": regions,
        "e0_ev_realized_R": fill.get("e0_ev_realized_R"),
        "live_episodes": live.get("n_episodes"),
        "portfolio_featured": {
            k: {
                "median": (featured.get(k) or {}).get("median_equity_multiple"),
                "p5": (featured.get(k) or {}).get("p5_equity_multiple"),
                "p_dd_20": (featured.get(k) or {}).get("p_dd_20"),
            }
            for k in (
                "A_iid_path_f5_published",
                "A_iid_fill70_f5_pub",
                "A_iid_p65_f5_pub",
                "A_iid_gov1_f5_pub",
                "B_weekly_blocks_f5_pub",
                "B_monthly_blocks_f5_pub",
                "W_iid_8_path_f5_pub",
                "W_iid_8_fill70_f5_pub",
                "W_iid_8_p65_f5_pub",
            )
        },
        "posterior": {
            "prior_mean": post.get("prior_mean"),
            "P_gt_be_prior": post.get("P_p_gt_p_be_gross_prior"),
            "hist_mean": post.get("posterior_mean"),
            "P_gt_be_hist": post.get("P_p_gt_p_be_gross_hist"),
            "live_n": post.get("live_observations"),
        },
        "change_detection_status": ns.get("change_detection_status"),
        "promotion_gates": {
            "gate1_entry": "FAIL_UNAVAILABLE",
            "gate2_stop": "FAIL_UNAVAILABLE",
            "gate3_fees": "FAIL_UNRESOLVED",
            "gate4_net_ev": "FAIL_UNAVAILABLE",
            "gate5_capacity": "FAIL_UNAVAILABLE",
            "gate6_risk": "NOT_EVALUATED_ON_LIVE_DATA",
        },
        "validation": val,
        "next_capture_mode_unarmed": [
            "paper_ledger",
            "tiny_real_orders",
            "full_simulated_execution",
        ],
    }
    write_json(OUT / "summary.json", summary)
    write_json(REP / "summary.json", summary)
    print("REPORT written; VERDICT = QUESTION B OPEN; LIVE EXECUTION CHANGED: FALSE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
