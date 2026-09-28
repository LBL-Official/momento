#!/usr/bin/env python3
"""Write REPORT.md and summary.json. One verdict. One production line. No 'production ready'."""

from __future__ import annotations

import json
from pathlib import Path

from common import (
    EXPECTED_FIRST80,
    EXPECTED_GAMES,
    EXPECTED_STOPS,
    EXPECTED_SURVIVORS,
    OUT,
    Q_UNCONDITIONAL,
    ev_from_q,
    utc_now,
    write_json,
)


def load(name):
    p = OUT / name
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def pct(x, d=2):
    if x is None:
        return "—"
    return f"{100.0 * x:.{d}f}%"


def num(x, d=3):
    if x is None:
        return "—"
    return f"{x:.{d}f}"


def decide(model, port, uni, forensic):
    selected = model.get("selected_model") or "model0"
    oos = model.get("oos_selected") or {}
    oos_m0 = (model.get("oos") or {}).get("model0") or {}
    gates = model.get("gates") or {}
    pol = (port.get("oos") or {}).get("policy") or {}
    hold = (port.get("oos") or {}).get("hold") or {}
    b0 = oos_m0.get("clustered_brier")
    bs = oos.get("clustered_brier")
    brier_lift = b0 is not None and bs is not None and bs <= 0.95 * b0
    ev_pol = pol.get("mean_R")
    ev_hold = hold.get("mean_R")
    ev_lift = ev_pol is not None and ev_hold is not None and ev_pol >= ev_hold + 0.02
    lead = pol.get("mean_lead_minutes") or 0.0
    useful_lead = lead >= 5.0
    recall = pol.get("recall") or 0.0
    precision = pol.get("precision") or 0.0
    ece_ok = gates.get("ece_ok", False)
    proximity_only = selected in ("model0", "model0b")
    val_improve = gates.get("brier_improve_vs_m0") is True

    reasons = {
        "selected": selected,
        "brier_lift_oos": brier_lift,
        "ev_lift_oos": ev_lift,
        "useful_lead": useful_lead,
        "mean_lead_minutes": lead,
        "precision": precision,
        "recall": recall,
        "ece_ok": ece_ok,
        "val_improve": val_improve,
        "proximity_only": proximity_only,
    }
    # Distance-to-40 is a mechanical competitor, not a dynamic path signal.
    if proximity_only:
        return (
            "VERDICT C — NO ROBUST DYNAMIC SIGNAL",
            "NO PRODUCTION CHANGE",
            reasons,
        )
    if (
        val_improve
        and brier_lift
        and ece_ok
        and ev_lift
        and useful_lead
        and precision >= 0.35
        and recall >= 0.20
    ):
        return (
            "VERDICT A — ROBUST DYNAMIC PATH SIGNAL",
            "CANDIDATE FOR INDEPENDENT PRODUCTION VALIDATION",
            reasons,
        )
    if val_improve or brier_lift:
        return (
            "VERDICT B — WEAK / RESEARCH-ONLY DYNAMIC SIGNAL",
            "RESEARCH-ONLY CANDIDATE" if (ev_lift and useful_lead) else "NO PRODUCTION CHANGE",
            reasons,
        )
    return (
        "VERDICT C — NO ROBUST DYNAMIC SIGNAL",
        "NO PRODUCTION CHANGE",
        reasons,
    )


def main() -> int:
    uni_sum = load("trade_universe_summary.json")
    panel = load("panel_summary.json")
    targets = load("target_summary.json")
    uni = load("univariate_results_train.json")
    model = load("model_results.json")
    port = load("portfolio_simulation.json")
    leak = load("leakage_audit.json")
    forensic = load("alignment_forensics.json")
    tgt = load("target_summary.json")

    verdict, production, reasons = decide(model, port, uni, forensic)

    h0 = (uni.get("tests") or {}).get("H0_minutes_since_entry") or {}
    h0b = (uni.get("tests") or {}).get("H0b_distance_to_40") or {}
    h1 = (uni.get("tests") or {}).get("H1_momentum_5m") or {}
    h6 = (uni.get("tests") or {}).get("H6_net_score") or {}
    h7 = (uni.get("tests") or {}).get("H7_path_archetype_rule") or {}

    oos_sel = model.get("oos_selected") or {}
    val_sel = model.get("validation_selected") or {}
    frozen = (port.get("frozen_policy") or {})
    oos_pol = (port.get("oos") or {}).get("policy") or {}
    oos_hold = (port.get("oos") or {}).get("hold") or {}
    val_pol = (port.get("validation") or {}).get("policy") or {}
    val_hold = (port.get("validation") or {}).get("hold") or {}
    arch = load("models/survival/path_archetypes.json")
    stab = load("models/survival/archetype_stability.json")

    # Alignment quality on panel (V3 state-level)
    align_counts = {}
    try:
        import pyarrow.parquet as pq

        t = pq.read_table(OUT / "post_entry_game_states.parquet", columns=["alignment_confidence"])
        from collections import Counter

        align_counts = dict(Counter(t.column("alignment_confidence").to_pylist()))
    except Exception:
        align_counts = {}

    lines = []
    a = lines.append
    a("# Dynamic Path Engine V3 — report")
    a("")
    a("Research only. Frozen 80/40 labels. Does not change live trading, Path Engine V1,")
    a("Game Path Engine V2, Risk, or Kalshi execution.")
    a("")
    a(f"**{verdict}**")
    a("")
    a(f"Production line: **{production}**")
    a("")
    a("The report does not claim production ready.")
    a("")
    a("## Frozen baseline")
    a("")
    a(f"- Games: {uni_sum.get('games')} (expected {EXPECTED_GAMES})")
    a(f"- First-80: {uni_sum.get('first80')} (expected {EXPECTED_FIRST80})")
    a(f"- Close-path 40: {uni_sum.get('Y_40_CLOSE')} (expected {EXPECTED_STOPS})")
    a(f"- Survivors: {uni_sum.get('survivors')} (expected {EXPECTED_SURVIVORS})")
    a(f"- Reproduction: {'PASS' if uni_sum.get('baseline_ok') else 'FAIL'}")
    a(f"- Unconditional q = {pct(Q_UNCONDITIONAL)} ; EV = 1−3q ≈ {num(ev_from_q(Q_UNCONDITIONAL), 3)} R")
    a("")
    a("## Panel")
    a("")
    a(f"- Trajectories with ≥1 alive minute: {panel.get('n_trajectories_with_panel')}")
    a(f"- Panel observations: {panel.get('n_panel_rows')}")
    a(f"- Median alive minutes: {panel.get('median_alive_minutes')}")
    a(f"- Cap: {panel.get('max_alive_minutes_cap')} minutes")
    a(f"- Risk-set rule: `{panel.get('risk_set_rule')}`")
    a(f"- Unconditional H_40_5M row rate: {pct(tgt.get('H_40_5M_rate'))}")
    a("")
    a("## Alignment (quality, not a filter)")
    a("")
    a(f"- V3 state-level confidence counts: {align_counts}")
    a(f"- V2 HIGH vs MEDIUM forensics conclusion: **{forensic.get('conclusion')}** (`{forensic.get('conclusion_code')}`)")
    a("- Confidence is a data-quality label. It is not a preregistered trading feature.")
    a("")
    a("## 1. Unconditional post-entry hazard profile")
    a("")
    a("Model 0 is the TRAIN barrier probability in the next 5 minutes, conditional on still being alive, by minutes-since-entry.")
    a("")
    a("| minutes since entry | n_rows | H_40_5M |")
    a("| --- | ---: | ---: |")
    for b in h0.get("buckets") or []:
        a(f"| {b.get('lo')}–{b.get('hi')} | {b.get('n_rows')} | {pct(b.get('rate'))} |")
    a("")
    a("## 2. When is barrier risk highest?")
    a("")
    rates = [(b.get("rate") or -1, b) for b in (h0.get("buckets") or []) if b.get("n_rows")]
    if rates:
        rates.sort(reverse=True)
        top = rates[0][1]
        a(f"Highest TRAIN H_40_5M bin: {top.get('lo')}–{top.get('hi')} minutes, rate {pct(top.get('rate'))} (n={top.get('n_rows')}).")
    a("Distance-to-40 (H0b) is the obvious mechanical competitor:")
    a("")
    a("| distance to 40 (cents) | n_rows | H_40_5M |")
    a("| --- | ---: | ---: |")
    for b in h0b.get("buckets") or []:
        a(f"| {b.get('lo')}–{b.get('hi')} | {b.get('n_rows')} | {pct(b.get('rate'))} |")
    a("")
    a("A useful dynamic model must beat proximity rediscovery, not merely restate that 42¢ is more dangerous than 79¢.")
    a("")
    a("## 3. Does market deterioration predict future deterioration?")
    a("")
    a(f"- H1 5m momentum TRAIN status: {h1.get('status')}")
    a(f"- Spearman (quintile mid vs rate): {num(h1.get('spearman_mid_vs_rate'), 3)}")
    a("Same-bar 1-minute candles cannot order intra-minute shocks. Momentum is a candle-close proxy.")
    a("")
    a("## 4. Does game-state deterioration predict barrier risk?")
    a("")
    a(f"- H6 net score since entry TRAIN status: {h6.get('status')}")
    a("Game features are UNAVAILABLE unless alignment is HIGH or MEDIUM at that state timestamp.")
    a("")
    a("## 5. Does the market response to game events contain information?")
    a("")
    a("Event-response labels are algorithmic (`path_archetype_rule`). They are not manual path reading.")
    a("")
    if isinstance(h7.get("buckets"), dict):
        a("| label | n_rows | H_40_5M |")
        a("| --- | ---: | ---: |")
        for k, v in h7["buckets"].items():
            a(f"| {k} | {v.get('n_rows')} | {pct(v.get('rate'))} |")
    a("")
    a("A relationship is an empirical association. It is not labeled overreaction.")
    a("")
    a("## 6. Stable post-entry path archetypes?")
    a("")
    a("K-means (k=6) on TRAIN last-alive path summaries. Descriptive only. Not a live Z_t feature.")
    a("")
    for c in arch.get("clusters") or []:
        a(f"- cluster {c.get('cluster')}: n={c.get('n')} q={pct(c.get('q'))}")
    a("")
    a(f"VAL/OOS assignment file written. Stability JSON keys: {list(stab.keys()) if stab else 'none'}.")
    a("If cluster barrier ranks are unstable across splits, archetypes are rejected as filters (they were never promoted).")
    a("")
    a("## 7. Can a model predict barrier events with meaningful lead time?")
    a("")
    a(f"- Validation-selected model: `{model.get('selected_model')}`")
    a(f"- VAL clustered Brier: {num(val_sel.get('clustered_brier'), 5)}  AUC: {num(val_sel.get('auc'), 3)}")
    a(f"- OOS clustered Brier: {num(oos_sel.get('clustered_brier'), 5)}  AUC: {num(oos_sel.get('auc'), 3)}")
    a(f"- OOS ECE: {num(oos_sel.get('ece'), 4)}")
    a(f"- Frozen policy: P{frozen.get('policy')} thresh={frozen.get('thresh')} persist={frozen.get('persist')} (VAL mean_R)")
    a(f"- OOS mean lead minutes (true warnings): {num(oos_pol.get('mean_lead_minutes'), 2)}")
    a(f"- OOS lead buckets: {oos_pol.get('lead_buckets')}")
    a("")
    a("Prediction quality is not trading utility. A 1-minute warning can be economically useless.")
    a("")
    a("## 8. False-positive cost of warnings")
    a("")
    a(f"- OOS precision: {pct(oos_pol.get('precision'))}")
    a(f"- OOS recall: {pct(oos_pol.get('recall'))}")
    a(f"- OOS false warnings: {oos_pol.get('false_warnings')}")
    a(f"- OOS true barrier warnings: {oos_pol.get('true_barrier_warnings')}")
    a(f"- OOS false-exit mean R: {num(oos_pol.get('false_exit_mean_R'), 3)}")
    a(f"- OOS true-exit mean R: {num(oos_pol.get('true_exit_mean_R'), 3)}")
    a("")
    a("## 9. Can a dynamic warning improve EV versus hold-to-40?")
    a("")
    a(f"- VAL hold mean R: {num(val_hold.get('mean_R'), 3)} ; policy: {num(val_pol.get('mean_R'), 3)}")
    a(f"- OOS hold mean R: {num(oos_hold.get('mean_R'), 3)} ; policy: {num(oos_pol.get('mean_R'), 3)}")
    a("Early-exit R uses SIMULATED next-candle yes_bid_close. Not a fill. Same-bar 1m order is unknown.")
    a("")
    a("## 10. Can it reduce maximum drawdown?")
    a("")
    ph = ((port.get("portfolio_hold") or {}).get("fractional") or {})
    pp = ((port.get("portfolio_policy") or {}).get("fractional") or {})
    a(f"- Hold fractional max DD: {pct(ph.get('max_dd'))}")
    a(f"- Policy fractional max DD: {pct(pp.get('max_dd'))}")
    a("Research bankroll $10,000 / 2% / max concurrent 5. Not live MLB 12.5% allocations.")
    a("")
    a("## 11. Does any improvement survive untouched OOS?")
    a("")
    a(f"- Selected on VALIDATION: `{model.get('selected_model')}`")
    a(f"- OOS is a single frozen pass: `{model.get('oos_pass')}`")
    a(f"- OOS clustered Brier selected vs Model 0: {num(oos_sel.get('clustered_brier'), 5)} vs {num((model.get('oos') or {}).get('model0', {}).get('clustered_brier'), 5)}")
    a("")
    a("## 12. Is the result economically usable?")
    a("")
    a(f"- Decision reasons: `{json.dumps(reasons)}`")
    a("- A good classifier is not necessarily a good trading signal.")
    a("- Conservative execution, clustered rows, and false-exit destruction of the 74% survival path are binding.")
    a("")
    a("## Leakage")
    a("")
    a(f"- Rows with source timestamp after state: {leak.get('n_rows_source_after_state')}")
    a(f"- Fail columns: {leak.get('n_fail_columns')}")
    a("- SAME_BAR_1M_LIMITATION applies to all 1-minute candle features.")
    a("")
    a("## Risk stress (IID Bernoulli; not a forecast)")
    a("")
    ruin = port.get("ruin_stress_iid") or {}
    a("| assumed survival | p(DD≥20%) | p(ruin) | p5 terminal |")
    a("| --- | ---: | ---: | ---: |")
    for k, v in ruin.items():
        a(f"| {k} | {pct(v.get('p_dd_20'))} | {pct(v.get('p_ruin'))} | {num(v.get('p5_terminal'), 0)} |")
    a("")
    a("Trades are not IID. Month-block bootstrap is in `portfolio_simulation.json`.")
    a("")
    a("## Production")
    a("")
    a(f"- Status: **{production}**")
    a("- Live execution changed: **false**")
    a("")
    a(f"Generated {utc_now()}")
    a("")
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n")

    write_json(
        OUT / "summary.json",
        {
            "engine": "NBA_DYNAMIC_PATH_ENGINE_V3",
            "written_utc": utc_now(),
            "research_only": True,
            "live_execution_changed": False,
            "frozen_baseline": {
                "games": uni_sum.get("games"),
                "first80": uni_sum.get("first80"),
                "close40": uni_sum.get("Y_40_CLOSE"),
                "survivors": uni_sum.get("survivors"),
                "reproduction": "PASS" if uni_sum.get("baseline_ok") else "FAIL",
                "q": Q_UNCONDITIONAL,
                "ev": ev_from_q(Q_UNCONDITIONAL),
            },
            "n_trajectories": panel.get("n_trajectories_with_panel"),
            "n_panel_rows": panel.get("n_panel_rows"),
            "alignment_quality_v3_states": align_counts,
            "alignment_forensics": {
                "conclusion": forensic.get("conclusion"),
                "code": forensic.get("conclusion_code"),
            },
            "unconditional_H5": uni.get("unconditional_H5"),
            "best_train_signals": uni.get("promoted_train"),
            "validation_selected_model": model.get("selected_model"),
            "oos_selected": oos_sel,
            "warning_lead_oos": {
                "mean_lead_minutes": oos_pol.get("mean_lead_minutes"),
                "buckets": oos_pol.get("lead_buckets"),
            },
            "false_positive_oos": {
                "precision": oos_pol.get("precision"),
                "recall": oos_pol.get("recall"),
                "false_exit_mean_R": oos_pol.get("false_exit_mean_R"),
            },
            "counterfactual_policy": {
                "frozen": frozen,
                "val_hold_mean_R": val_hold.get("mean_R"),
                "val_policy_mean_R": val_pol.get("mean_R"),
                "oos_hold_mean_R": oos_hold.get("mean_R"),
                "oos_policy_mean_R": oos_pol.get("mean_R"),
            },
            "portfolio_fractional": {
                "hold": ph,
                "policy": pp,
            },
            "ruin_stress": ruin,
            "verdict": verdict,
            "production_line": production,
            "leakage_fail": leak.get("n_fail_columns"),
        },
    )
    print(verdict)
    print(production)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
