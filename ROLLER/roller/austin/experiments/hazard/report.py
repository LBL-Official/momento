"""Phase 4 REPORT.md. No policy. No exit rule. No live-ready language."""

from __future__ import annotations

from typing import Any

from roller.austin.experiments.downfall.ids import HEALTHY, HEALTHY_AFTER_RECOVERY, PERSISTENCE_2, PERSISTENCE_3PLUS, RECOVERING, WATCH_NEGATIVE
from roller.austin.experiments.hazard.ids import EXPERIMENT_A, EXPERIMENT_B, HAZARD_SCHEMA_VERSION, MODEL_ID, STATE_SCHEMA_HASH
from roller.austin.experiments.persistence.report import _fmt


def _md_table(headers: list[str], rows: list[list[object]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_fmt(c) for c in row) + " |")
    return lines


def _combine(labels: list[str]) -> str:
    known = [x for x in labels if x]
    if not known:
        return "INSUFFICIENT_SAMPLE"
    if all(x == "INSUFFICIENT_SAMPLE" for x in known):
        return "INSUFFICIENT_SAMPLE"
    useful = [x for x in known if x != "INSUFFICIENT_SAMPLE"]
    if useful and all(x == "SUPPORTED" for x in useful) and "INSUFFICIENT_SAMPLE" not in known:
        return "SUPPORTED"
    if "SUPPORTED" in useful or "MIXED" in useful:
        return "MIXED"
    return "NOT_SUPPORTED"


def _skill_class(row: dict[str, Any] | None) -> str:
    if not row:
        return "INSUFFICIENT_SAMPLE"
    n = int(row.get("eligible_N") or 0)
    if n < 10:
        return "INSUFFICIENT_SAMPLE"
    bss = row.get("bss_vs_H0")
    ci = row.get("bss_ci") or [None, None]
    if bss is None:
        return "INSUFFICIENT_SAMPLE"
    if bss > 0 and ci[0] is not None and ci[0] > 0:
        return "SUPPORTED"
    if bss > 0:
        return "MIXED"
    if ci[1] is not None and ci[1] < 0:
        return "NOT_SUPPORTED"
    return "MIXED"


def _pick(metrics: list[dict[str, Any]], target: str, family: str) -> dict[str, Any] | None:
    return next((r for r in metrics if r.get("target") == target and r.get("family") == family), None)


def _state(rows: list[dict[str, Any]], name: str) -> dict[str, Any]:
    return next((r for r in rows if r.get("core_state") == name), {})


def interpret_hazard(
    stats_a: dict[str, Any],
    stats_b: dict[str, Any],
    *,
    leakage: dict[str, Any],
    crossfit: dict[str, Any],
) -> dict[str, Any]:
    gate_a = "PASS" if leakage.get("status") == "PASS" and crossfit.get("status") == "PASS" else "FAIL"
    loss_a = _skill_class(_pick(stats_a["metrics"], "TARGET_terminal_loss", "H1"))
    loss_b = _skill_class(_pick(stats_b["metrics"], "TARGET_terminal_loss", "H1"))
    loss_a2 = _skill_class(_pick(stats_a["metrics"], "TARGET_terminal_loss", "H2"))
    loss_b2 = _skill_class(_pick(stats_b["metrics"], "TARGET_terminal_loss", "H2"))
    gate_b = _combine([loss_a, loss_b, loss_a2, loss_b2])
    rec_labels = []
    for stats in (stats_a, stats_b):
        for target in ("TARGET_recovery_t1", "TARGET_recovery_by_t2", "TARGET_recovery_by_t3"):
            rec_labels.append(_skill_class(_pick(stats["metrics"], target, "H1")))
    miss_b = next((r for r in stats_b.get("missingness") or [] if r.get("target") == "TARGET_recovery_t1"), {})
    if int(miss_b.get("eligible") or 0) < 10:
        rec_labels.append("INSUFFICIENT_SAMPLE")
    gate_c = _combine(rec_labels)
    dyn_labels = []
    for stats in (stats_a, stats_b):
        for row in stats.get("dynamic") or []:
            if int(row.get("N_trades") or 0) < 5:
                dyn_labels.append("INSUFFICIENT_SAMPLE")
            elif row.get("mean_delta_p_loss_H1") is None:
                dyn_labels.append("INSUFFICIENT_SAMPLE")
            elif abs(float(row["mean_delta_p_loss_H1"])) > 0:
                dyn_labels.append("MIXED")
            else:
                dyn_labels.append("NOT_SUPPORTED")
    gate_d = _combine(dyn_labels)
    time_labels = []
    for stats in (stats_a, stats_b):
        remaining = [r for r in stats.get("timing_summary") or [] if r.get("mean_adverse_cents_remaining") is not None]
        if not remaining:
            time_labels.append("INSUFFICIENT_SAMPLE")
            continue
        if any((r.get("mean_adverse_cents_remaining") or 0) > 0 for r in remaining) and any(
            (r.get("p_spread") or 0) > 0 for r in remaining
        ):
            time_labels.append("MIXED")
        elif any((r.get("mean_adverse_cents_remaining") or 0) > 0 for r in remaining):
            time_labels.append("MIXED")
        else:
            time_labels.append("NOT_SUPPORTED")
    gate_e = _combine(time_labels)
    watch_a = _state(stats_a.get("by_state") or [], WATCH_NEGATIVE)
    healthy_a = _state(stats_a.get("by_state") or [], HEALTHY)
    watch_b = _state(stats_b.get("by_state") or [], WATCH_NEGATIVE)
    healthy_b = _state(stats_b.get("by_state") or [], HEALTHY)
    dir_a = (
        watch_a.get("p_terminal_loss_H1") is not None
        and healthy_a.get("p_terminal_loss_H1") is not None
        and watch_a["p_terminal_loss_H1"] > healthy_a["p_terminal_loss_H1"]
    )
    dir_b = (
        watch_b.get("p_terminal_loss_H1") is not None
        and healthy_b.get("p_terminal_loss_H1") is not None
        and watch_b["p_terminal_loss_H1"] > healthy_b["p_terminal_loss_H1"]
    )
    recovering_b = _state(stats_b.get("by_state") or [], RECOVERING)
    b_recovery_thin = int(miss_b.get("eligible") or 0) < 20 or int(recovering_b.get("N") or 0) == 0
    if miss_b.get("eligible", 0) == 0 or b_recovery_thin:
        gate_f = "MIXED" if dir_a and dir_b else ("MIXED" if dir_a or dir_b else "NOT_SUPPORTED")
        transfer_note = "WATCH vs HEALTHY p_loss can agree, but B recovery is thin or missing and counts against transfer."
    elif dir_a or dir_b:
        gate_f = "MIXED"
        transfer_note = "Directional p_loss consistency is incomplete across members."
    else:
        gate_f = "NOT_SUPPORTED"
        transfer_note = "WATCH vs HEALTHY p_loss is not directionally consistent."
    if gate_a != "PASS":
        phase5 = "PHASE 5 NOT JUSTIFIED"
        phase5_class = "NOT_SUPPORTED"
        phase5_note = "Gate A failed. Phase 4 is incomplete."
        complete = False
    elif all(g == "SUPPORTED" for g in (gate_b, gate_c, gate_d, gate_e, gate_f)):
        phase5 = "PHASE 5 MAY BE JUSTIFIED"
        phase5_class = "SUPPORTED"
        phase5_note = "PIT, LOGO skill, recovery, update, timing, and transfer all SUPPORTED. Policy is still unwritten."
        complete = True
    elif gate_c in {"INSUFFICIENT_SAMPLE", "NOT_SUPPORTED"} and gate_b in {"SUPPORTED", "MIXED"}:
        phase5 = "LOSS-RISK MODEL ONLY / RECOVERY INSUFFICIENT"
        phase5_class = "MIXED" if gate_b != "NOT_SUPPORTED" else "NOT_SUPPORTED"
        phase5_note = "Terminal-loss estimates exist; recovery is not robust enough for a DRE policy."
        complete = True
    elif gate_e in {"NOT_SUPPORTED"} and gate_b in {"SUPPORTED", "MIXED"}:
        phase5 = "VALID HAZARD DESCRIPTION NOT YET AN ACTIONABLE DRE SIGNAL"
        phase5_class = "MIXED"
        phase5_note = "Probability information appears after remaining damage is gone, or is not timed early enough."
        complete = True
    else:
        phase5 = "PHASE 5 NOT JUSTIFIED"
        phase5_class = "NOT_SUPPORTED" if gate_b == "NOT_SUPPORTED" else "MIXED"
        phase5_note = "The PIT → LOGO improvement → recovery → update → early-enough → support chain does not hold."
        complete = True
    return {
        "gate_a_probability_validity": gate_a,
        "gate_b_terminal_loss_information": gate_b,
        "gate_c_recovery_information": gate_c,
        "gate_d_dynamic_update": gate_d,
        "gate_e_timing": gate_e,
        "gate_f_transfer_support": gate_f,
        "phase_5_decision": phase5,
        "phase_5_classification": phase5_class,
        "phase_5_note": phase5_note,
        "phase_4_complete": complete,
        "transfer_note": transfer_note,
        "A_terminal_loss_H1": loss_a,
        "B_terminal_loss_H1": loss_b,
        "A_terminal_loss_H2": loss_a2,
        "B_terminal_loss_H2": loss_b2,
    }


def _metric_rows(metrics: list[dict[str, Any]], target: str) -> list[list[object]]:
    out = []
    for family in ("H0", "H1", "H2"):
        row = _pick(metrics, target, family) or {}
        out.append(
            [
                family,
                row.get("eligible_N"),
                row.get("event_N"),
                row.get("unavailable_N"),
                row.get("brier"),
                row.get("bss_vs_H0"),
                row.get("log_loss"),
                row.get("delta_log_loss_vs_H0"),
                row.get("roc_auc"),
            ]
        )
    return out


def _state_rows(by_state: list[dict[str, Any]]) -> list[list[object]]:
    order = (HEALTHY, WATCH_NEGATIVE, PERSISTENCE_2, PERSISTENCE_3PLUS, RECOVERING, HEALTHY_AFTER_RECOVERY)
    out = []
    for name in order:
        row = _state(by_state, name)
        rec_na = name in {HEALTHY, RECOVERING, HEALTHY_AFTER_RECOVERY}
        out.append(
            [
                name,
                row.get("N"),
                row.get("p_terminal_loss_H1"),
                "N/A" if rec_na else row.get("p_recovery_t1_H1"),
                "N/A" if rec_na else row.get("p_recovery_by_t2_H1"),
                "N/A" if rec_na else row.get("p_recovery_by_t3_H1"),
            ]
        )
    return out


def render_report(payload: dict[str, Any]) -> str:
    a = payload["A"]
    b = payload["B"]
    interp = payload["interpretation"]
    audits = payload["audits"]
    manifest = payload["manifest"]
    lines = [
        "AUSTIN DRE",
        "PHASE 4 — LOSS HAZARD / RECOVERY MODEL",
        "",
        "DISCOVERY ONLY",
        "",
        "PHASE 2 FINALIZED",
        "PHASE 3 COMPLETE",
        "",
        "AUSTIN MODEL FROZEN",
        "DOWNFALL STATE SCHEMA FROZEN",
        "",
        "POLICY UNFROZEN",
        "CONFIRMATION UNTOUCHED",
        "",
        "EXECUTION DISABLED",
        "",
        "# 1. EXECUTIVE RESEARCH SUMMARY",
        "",
        "Phase 4 fits a frozen Jeffreys Beta-Binomial leave-one-game-out layer on Phase 3 first-entry states.",
        "These are terminal-loss / recovery / next-deterioration estimates only. They are not an action rule.",
        f"Phase 5 decision: {interp['phase_5_decision']}.",
        interp["phase_5_note"],
        "A and B are never pooled as a headline.",
        "",
        "# 2. WATERFALL / PRIOR-PHASE FINALIZATION",
        "",
        "Phase 2 FINALIZED. Actionability NOT MET. Historical Phase 2 artifacts were not rewritten.",
        "Phase 3 COMPLETE / MIXED. Historical Phase 3 artifacts were not rewritten.",
        f"Phase 2 REPORT hash `{manifest['phase_2_report_hash']}`.",
        f"Phase 3 REPORT hash `{manifest['phase_3_report_hash']}`.",
        "",
        "# 3. PHASE 4 IDENTITY",
        "",
        f"MODEL_ID `{MODEL_ID}`. Schema `{HAZARD_SCHEMA_VERSION}`. Families H0 member / H1 core_state / H2 core_state×CI_state.",
        "No extra families. No price/score/time/EV buckets. No classifier. No DRE score.",
        "",
        "# 4. MODEL / COHORT LOCKS",
        "",
        f"Austin model `{manifest['source_austin_model']}` hash `{manifest['model_manifest_hash']}`.",
        f"Training N=604. K=25. State schema downfall_state_v1 hash `{STATE_SCHEMA_HASH}`.",
        f"Hazard schema hash `{manifest['hazard_schema_hash']}`.",
        f"A discovery `{manifest['A_discovery_hash']}`. B discovery `{manifest['B_discovery_hash']}`.",
        "",
        "# 5. PHASE 3 HANDOFF",
        "",
        "Evaluation unit is Phase 3 first trade×core_state entries. Timeline rows are not independent N.",
        "Phase 3 result remains MIXED. Phase 4 does not upgrade Phase 3 into a useful path model by assertion.",
        "",
        "# 6. HAZARD SCHEMA",
        "",
        "Jeffreys prior 0.5/0.5. `p_hat=(y+0.5)/(n+1)`. n=0 → UNAVAILABLE. H2 never falls back to H1.",
        "LOGO drops `internal_game_id`. Gap / UNRESOLVED breaks recovery continuity. No interpolation.",
        "",
        "# 7. TARGET DEFINITIONS",
        "",
        "TARGET_terminal_loss = 1 if FIRST80 settles LOSS.",
        "TARGET_recovery_t1/t2/t3 = next 1/2/3 adjacent valid PRIMARY rows with EV present.",
        "TARGET_deeper_distress_next uses STATE_DEPTH only. Recovery states are not depths.",
        "TARGET_T40_before_recovery is secondary. T40 already at entry is NOT_APPLICABLE.",
        "",
        "# 8. CROSS-FIT METHODOLOGY",
        "",
        "Every scoring p_hat rebuilds the Beta table after dropping that row's internal_game_id.",
        f"same_game_present_in_training=false on {audits['crossfit']['n_predictions']} predictions.",
        "",
        "# 9. MEMBER BASE RATES",
        "",
        "H0 is member-only. A and B have separate base rates. Do not pool.",
        "",
        "# 10. TERMINAL LOSS RISK — H0/H1/H2",
        "",
        "## A",
        "",
    ]
    lines.extend(
        _md_table(
            ["Model", "Eligible N", "Losses", "Unavailable", "Brier", "BSS vs H0", "Log loss", "Δ log loss", "ROC AUC"],
            _metric_rows(a["metrics"], "TARGET_terminal_loss"),
        )
    )
    lines.extend(["", f"H1 BSS CI {a.get('loss_bss_ci_H1')}. H2 BSS CI {a.get('loss_bss_ci_H2')}.", "", "## B", ""])
    lines.extend(
        _md_table(
            ["Model", "Eligible N", "Losses", "Unavailable", "Brier", "BSS vs H0", "Log loss", "Δ log loss", "ROC AUC"],
            _metric_rows(b["metrics"], "TARGET_terminal_loss"),
        )
    )
    lines.extend(["", f"H1 BSS CI {b.get('loss_bss_ci_H1')}. H2 BSS CI {b.get('loss_bss_ci_H2')}.", ""])
    lines.extend(["# 11. TERMINAL LOSS CALIBRATION", "", "Fixed bins [0,0.2), [0.2,0.4), [0.4,0.6), [0.6,0.8), [0.8,1]. N<10 is not strong evidence.", ""])
    for letter, stats in (("A", a), ("B", b)):
        lines.extend([f"## {letter}", ""])
        cal = [r for r in stats.get("loss_calibration") or [] if r.get("family") == "H1"]
        lines.extend(
            _md_table(
                ["bin", "N", "mean p", "observed", "strong"],
                [[f"{r['bin_lo']}-{r['bin_hi']}", r["N"], r["mean_predicted"], r["observed_rate"], r["strong_evidence"]] for r in cal],
            )
        )
        lines.append("")
    for idx, (title, target) in enumerate(
        (("12. RECOVERY T1 MODEL", "TARGET_recovery_t1"), ("13. RECOVERY T2 MODEL", "TARGET_recovery_by_t2"), ("14. RECOVERY T3 MODEL", "TARGET_recovery_by_t3")),
        start=12,
    ):
        lines.extend([f"# {title}", ""])
        for letter, stats in (("A", a), ("B", b)):
            lines.extend([f"## {letter}", ""])
            lines.extend(
                _md_table(
                    ["Model", "Eligible N", "Recovery N", "Unavailable N", "Brier", "BSS", "Log loss"],
                    [
                        [
                            fam,
                            (_pick(stats["metrics"], target, fam) or {}).get("eligible_N"),
                            (_pick(stats["metrics"], target, fam) or {}).get("event_N"),
                            (_pick(stats["metrics"], target, fam) or {}).get("unavailable_N"),
                            (_pick(stats["metrics"], target, fam) or {}).get("brier"),
                            (_pick(stats["metrics"], target, fam) or {}).get("bss_vs_H0"),
                            (_pick(stats["metrics"], target, fam) or {}).get("log_loss"),
                        ]
                        for fam in ("H0", "H1", "H2")
                    ],
                )
            )
            lines.append("")
    lines.extend(
        [
            "# 15. DEEPER-DISTRESS MODEL",
            "",
            "Next adjacent valid core_state has greater STATE_DEPTH. Recovery destinations are not depths.",
            "",
        ]
    )
    for letter, stats in (("A", a), ("B", b)):
        lines.extend([f"## {letter}", ""])
        lines.extend(
            _md_table(
                ["Model", "Eligible N", "Event N", "Unavailable N", "Brier", "BSS"],
                [
                    [
                        fam,
                        (_pick(stats["metrics"], "TARGET_deeper_distress_next", fam) or {}).get("eligible_N"),
                        (_pick(stats["metrics"], "TARGET_deeper_distress_next", fam) or {}).get("event_N"),
                        (_pick(stats["metrics"], "TARGET_deeper_distress_next", fam) or {}).get("unavailable_N"),
                        (_pick(stats["metrics"], "TARGET_deeper_distress_next", fam) or {}).get("brier"),
                        (_pick(stats["metrics"], "TARGET_deeper_distress_next", fam) or {}).get("bss_vs_H0"),
                    ]
                    for fam in ("H0", "H1", "H2")
                ],
            )
        )
        lines.append("")
    lines.extend(["# 16. STATE-CONDITIONAL HAZARDS", ""])
    for letter, stats in (("A", a), ("B", b)):
        lines.extend([f"## {letter}", ""])
        lines.extend(
            _md_table(
                ["State", "N", "p(loss)", "p(recovery t1)", "p(recovery by t2)", "p(recovery by t3)"],
                _state_rows(stats.get("by_state") or []),
            )
        )
        lines.append("")
    lines.extend(["# 17. STATE × CI HAZARDS", "", "H2 cells with n=0 stay UNAVAILABLE. No H2→H1 fallback.", ""])
    for letter, stats in (("A", a), ("B", b)):
        lines.extend([f"## {letter}", ""])
        lines.extend(
            _md_table(
                ["state", "CI", "N", "p_loss H2", "label"],
                [[r.get("core_state"), r.get("CI_state"), r.get("N"), r.get("p_terminal_loss_H2"), r.get("label")] for r in stats.get("by_state_ci") or []],
            )
        )
        lines.append("")
    lines.extend(["# 18. DYNAMIC RISK CONTRAST", "", "Do not force monotonicity.", ""])
    for letter, stats in (("A", a), ("B", b)):
        lines.extend([f"## {letter}", ""])
        lines.extend(
            _md_table(
                ["from", "to", "N", "Δ p_loss H1", "Δ p_recovery t1 H1"],
                [[r.get("from_state"), r.get("to_state"), r.get("N_trades"), r.get("mean_delta_p_loss_H1"), r.get("mean_delta_p_recovery_t1_H1")] for r in stats.get("dynamic") or []],
            )
        )
        lines.append("")
    lines.extend(
        [
            "# 19. HAZARD TRAJECTORIES",
            "",
            "First downside-state sequence per trade. Δ p_loss / Δ p_recovery are descriptive.",
            "",
            "# 20. TRANSITION-RISK ANALYSIS",
            "",
            "H1/H2 probabilities are taken at the FROM state only. Destination is evaluation.",
            "",
        ]
    )
    for letter, stats in (("A", a), ("B", b)):
        lines.extend([f"## {letter}", ""])
        lines.extend(
            _md_table(
                ["from", "to", "N", "mean p_loss H1 at FROM"],
                [[r.get("from_state"), r.get("to_state"), r.get("N"), r.get("mean_p_loss_from")] for r in stats.get("transition_summary") or []],
            )
        )
        lines.append("")
    lines.extend(["# 21. AUSTIN EV VS HAZARD", ""])
    for letter, stats in (("A", a), ("B", b)):
        lines.extend([f"## {letter}", ""])
        lines.extend(
            _md_table(
                ["contrast", "N", "Spearman", "CI lo", "CI hi"],
                [[r.get("contrast"), r.get("n"), r.get("spearman"), r.get("ci_lo"), r.get("ci_hi")] for r in stats.get("ev_vs_hazard") or []],
            )
        )
        lines.append("")
    lines.extend(
        [
            "# 22. CI INFORMATION VALUE",
            "",
            f"A H2 vs H1 terminal-loss class: {interp['A_terminal_loss_H2']}. B: {interp['B_terminal_loss_H2']}.",
            "H2 is not declared a winner.",
            "",
            "# 23. SUPPORT / MANIFOLD",
            "",
        ]
    )
    for letter, stats in (("A", a), ("B", b)):
        lines.extend([f"## {letter}", ""])
        lines.extend(
            _md_table(
                ["state", "N", "mean ESS", "mean median distance", "low cell N"],
                [[r.get("core_state"), r.get("N"), r.get("mean_ESS"), r.get("mean_median_distance"), r.get("low_cell_support_N")] for r in stats.get("support") or []],
            )
        )
        lines.append("")
    lines.extend(["# 24. T40-BEFORE-RECOVERY DIAGNOSTIC", ""])
    for letter, stats in (("A", a), ("B", b)):
        row = (stats.get("t40") or [{}])[0]
        lines.append(
            f"{letter}: negative={row.get('N_negative_entries')} observable={row.get('N_observable')} "
            f"T40-before-recovery={row.get('n_T40_before_recovery')} N/A={row.get('N_not_applicable')} unavailable={row.get('N_unavailable')}"
        )
    lines.extend(["", "# 25. TIMING / REMAINING DAMAGE", "", "Phase 1 warning remains 0/15 and 0/12. This is not validated early warning.", ""])
    for letter, stats in (("A", a), ("B", b)):
        lines.extend([f"## {letter}", ""])
        lines.extend(
            _md_table(
                ["state", "N", "mean adverse ¢ remaining", "mean minutes to worst", "mean p_loss H1"],
                [
                    [r.get("core_state"), r.get("N"), r.get("mean_adverse_cents_remaining"), r.get("mean_minutes_to_worst_price"), r.get("mean_p_loss")]
                    for r in stats.get("timing_summary") or []
                ],
            )
        )
        lines.append("")
    lines.extend(
        [
            "# 26. CALIBRATION / DISCRIMINATION",
            "",
            "Brier and log loss are primary. ROC/PR AUC only when both classes are present. No thresholded accuracy headline.",
            "",
            "# 27. STATISTICAL UNCERTAINTY",
            "",
            "Game-clustered bootstrap. cluster=internal_game_id. seed=80. B=1000.",
            "",
            "# 28. LEAKAGE / INTEGRITY",
            "",
            f"Leakage {audits['leakage']['status']}. Crossfit {audits['crossfit']['status']}. Confirmation accessed=false.",
            f"Phase 2 finalization {audits['phase2']['status']}. Phase 3 finalization {audits['phase3']['status']}.",
            "",
            "# 29. WHAT THE DATA SHOWS",
            "",
            f"Gate B terminal-loss information: {interp['gate_b_terminal_loss_information']}.",
            f"Gate C recovery information: {interp['gate_c_recovery_information']}.",
            interp["transfer_note"],
            "",
            "# 30. WHAT AUSTIN ADDS",
            "",
            "Austin contributes the frozen first-entry state keys and hold-80-to-settlement EV used as a covariate, not a policy.",
            "",
            "# 31. WHAT HAS NOT BEEN PROVEN",
            "",
            "No fill. No live EV. No exit rule. No confirmation. No Phase 5 policy. Candle path is not a fill.",
            "",
            "# 32. WHETHER PHASE 5 IS JUSTIFIED",
            "",
            interp["phase_5_decision"],
            interp["phase_5_note"],
            "",
            "PHASE 5 — NOT STARTED",
            "",
            "POLICY UNFROZEN",
            "CONFIRMATION UNTOUCHED",
            "EXECUTION DISABLED",
            "",
        ]
    )
    return "\n".join(lines)
