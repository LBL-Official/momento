"""Phase 3 REPORT.md. No holy grail. No live-ready language. No policy."""

from __future__ import annotations

from typing import Any

from roller.austin.errors import AustinError
from roller.austin.experiments.downfall.ids import (
    HEALTHY_AFTER_RECOVERY,
    LOCKED_ALIGNMENT_STATUS,
    LOCKED_CLOCK_ORDER,
    PERSISTENCE_2,
    PERSISTENCE_3PLUS,
    RECOVERING,
    WATCH_NEGATIVE,
)
from roller.austin.experiments.downfall.schema import schema_hash, state_schema
from roller.austin.experiments.persistence.report import _ci, _fmt


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
    if useful and all(x == "SUPPORTED" for x in useful):
        return "MIXED"
    if "SUPPORTED" in useful or "MIXED" in useful:
        return "MIXED"
    return "NOT_SUPPORTED"


def _combine_ab(a: str, b: str) -> str:
    return _combine([a, b])


def interpret_downfall(
    stats_a: dict[str, Any],
    stats_b: dict[str, Any],
    *,
    determinism: dict[str, Any],
    leakage: dict[str, Any],
    alignment: dict[str, Any],
) -> dict[str, Any]:
    gate_a = "PASS" if determinism.get("status") == "PASS" and leakage.get("status") == "PASS" else "FAIL"
    gate_b = _combine_ab(stats_a["ordering"]["classification"], stats_b["ordering"]["classification"])
    contrast_a = [r.get("classification") for r in stats_a["contrasts"] if r.get("metric") in {"pnl", "loss_rate"}]
    contrast_b = [r.get("classification") for r in stats_b["contrasts"] if r.get("metric") in {"pnl", "loss_rate"}]
    gate_b = _combine([gate_b, _combine(contrast_a), _combine(contrast_b)])
    branch_a = [r.get("classification") for r in stats_a.get("transition_branches") or []]
    branch_b = [r.get("classification") for r in stats_b.get("transition_branches") or []]
    gate_c = _combine([_combine(branch_a), _combine(branch_b)])
    gate_d = _combine_ab(stats_a["timing_gate"], stats_b["timing_gate"])
    if gate_b == "SUPPORTED" and gate_c == "SUPPORTED" and gate_d == "SUPPORTED":
        phase4 = "PHASE 4 MAY BE JUSTIFIED"
        phase4_class = "SUPPORTED"
    elif gate_a == "PASS" and gate_d in {"NOT_SUPPORTED", "MIXED"} and gate_b in {"SUPPORTED", "MIXED"}:
        phase4 = "VALID STATE MODEL BUT NOT YET A USEFUL DRE PATH MODEL"
        phase4_class = "MIXED"
    else:
        phase4 = "PHASE 4 NOT JUSTIFIED"
        phase4_class = "NOT_SUPPORTED" if gate_b == "NOT_SUPPORTED" and gate_c == "NOT_SUPPORTED" else "MIXED"
    return {
        "gate_a_state_validity": gate_a,
        "gate_b_economic_separation": gate_b,
        "gate_c_transition_information": gate_c,
        "gate_d_timing_remaining_damage": gate_d,
        "phase_4_justified": False,
        "phase_4_decision": phase4,
        "phase_4_classification": phase4_class,
        "alignment_status": alignment.get("status") or LOCKED_ALIGNMENT_STATUS,
        "potential_data_alignment_defect": alignment.get("potential_data_alignment_defect"),
        "ordering_a": stats_a["ordering"],
        "ordering_b": stats_b["ordering"],
        "hazard_model_built": False,
        "policy_status": "UNFROZEN",
        "confirmation_accessed": False,
    }


def _econ_row(row: dict[str, Any]) -> list[object]:
    return [
        row.get("core_state") or row.get("archetype") or row.get("transition"),
        row.get("N_trades"),
        row.get("loss_rate"),
        row.get("mean_pnl_hold_after_state"),
        row.get("T40_rate"),
        row.get("mean_future_MAE"),
        row.get("mean_future_MFE"),
        row.get("recover_ge_80"),
    ]


def _mermaid(letter: str, counts: list[dict[str, Any]]) -> list[str]:
    lines = [f"```mermaid", "flowchart LR"]
    interesting = [
        r
        for r in counts
        if int(r.get("count") or 0) > 0
        and r.get("from_state") not in {None, "PRE_ENTRY"}
        and r.get("to_state") not in {None, "PRE_ENTRY"}
    ]
    interesting = sorted(interesting, key=lambda r: -int(r.get("count") or 0))[:16]
    if not interesting:
        lines.append("    EMPTY[no adjacent valid transitions]")
    for row in interesting:
        frm = str(row["from_state"]).replace("_", "")
        to = str(row["to_state"]).replace("_", "")
        lines.append(f"    {frm} -->|{row['count']}| {to}")
    lines.extend(["```", "", f"{letter} observed adjacent valid PRIMARY counts only. Not a hazard.", ""])
    return lines


def render_report(payload: dict[str, Any]) -> str:
    schema = state_schema()
    a = payload["A"]
    b = payload["B"]
    interp = payload["interpretation"]
    audits = payload["audits"]
    manifest = payload["manifest"]
    alignment = payload["alignment_verdict"]
    lines = [
        "AUSTIN DRE",
        "PHASE 3 — DOWNFALL STATE MODEL",
        "",
        "RESEARCH ONLY",
        "",
        "MODEL FROZEN",
        "STATE SCHEMA FROZEN FOR V1",
        "POLICY UNFROZEN",
        "CONFIRMATION UNTOUCHED",
        "",
        "HAZARD MODEL NOT BUILT",
        "EXECUTION DISABLED",
        "",
        "# 1. EXECUTIVE RESEARCH SUMMARY",
        "",
        "Phase 3 assigns a deterministic PIT downfall state from observed Austin EV history.",
        "It does not rewrite Phase 2. Phase 2 actionability remains NOT MET.",
        "Confirmation was not read. No policy was selected. No hazard model was fit.",
        f"Gate A state validity: {interp['gate_a_state_validity']}",
        f"Gate B economic separation: {interp['gate_b_economic_separation']}",
        f"Gate C transition information: {interp['gate_c_transition_information']}",
        f"Gate D timing / remaining damage: {interp['gate_d_timing_remaining_damage']}",
        f"Phase 4 decision: {interp['phase_4_decision']}",
        "",
        "# 2. PHASE IDENTITY",
        "",
        f"phase {manifest.get('phase')}",
        f"phase_name {manifest.get('phase_name')}",
        f"model_id {manifest.get('model_id')}",
        f"source_phase_2 {manifest.get('source_phase_2')}",
        f"state_schema_version {manifest.get('state_schema_version')}",
        f"state_schema_hash {manifest.get('state_schema_hash')}",
        f"phase_2_actionability_gate {manifest.get('phase_2_actionability_gate')}",
        f"phase_3_authorization {manifest.get('phase_3_authorization')}",
        "",
        "# 3. PHASE-2 HANDOFF",
        "",
        "Clock-order first-negative counts are copied, not recomputed:",
        f"A {LOCKED_CLOCK_ORDER[a['experiment_id']]}",
        f"B {LOCKED_CLOCK_ORDER[b['experiment_id']]}",
        "Temporary / persistent labels remain future-derived Phase 2 outcomes.",
        "They do not define Phase 3 PIT states.",
        "Phase 2 report and statistics hashes were verified before this run.",
        f"phase_3_justified remains false. Acceptance remains: valid state diagnosis — not an actionable risk mechanism.",
        "",
        "# 4. MODEL / COHORT LOCKS",
        "",
        f"model_manifest_hash {manifest.get('model_manifest_hash')}",
        f"feature_schema_hash {manifest.get('feature_schema_hash')}",
        f"A_discovery_cohort_hash {manifest.get('A_discovery_cohort_hash')}",
        f"A_confirmation_cohort_hash {manifest.get('A_confirmation_cohort_hash')}",
        f"B_discovery_cohort_hash {manifest.get('B_discovery_cohort_hash')}",
        f"B_confirmation_cohort_hash {manifest.get('B_confirmation_cohort_hash')}",
        "Confirmation hashes are identity only. Confirmation outcomes were not used.",
        f"bootstrap seed {manifest.get('bootstrap_seed')} B {manifest.get('bootstrap_B')} cluster {manifest.get('cluster_unit')}",
        "",
        "# 5. DOWNFALL STATE SCHEMA",
        "",
        f"version {schema['version']}",
        f"states {' '.join(schema['states'])}",
        f"gap_rule {schema['gap_rule']}",
        "Overlays do not modify core_state.",
        "No CRITICAL / TERMINAL / FAILURE / EXIT.",
        f"schema_hash {schema_hash(schema)}",
        "",
        "# 6. STATE ASSIGNMENT INTEGRITY",
        "",
        f"determinism {audits['determinism']['status']} checked {audits['determinism']['n_checked']} failed {audits['determinism']['n_failed']}",
        f"leakage {audits['leakage']['status']} checked {audits['leakage']['n_checked']} failed {audits['leakage']['n_failed']}",
        "Assignment uses history through t only. Outcome keys are forbidden in derive_downfall_state.",
        "Missing PRIMARY slots emit UNRESOLVED and break the streak.",
        "",
        "# 7. STATE POPULATIONS",
        "",
        "A and B are never pooled as a headline.",
        "",
        "### A",
        "",
        *_md_table(
            ["state", "N rows", "N first entries", "pct discovery trades"],
            [
                [r["core_state"], r["N_state_rows"], r["N_trades_entering"], r["pct_discovery_trades"]]
                for r in a["populations"]
            ],
        ),
        "",
        "### B",
        "",
        *_md_table(
            ["state", "N rows", "N first entries", "pct discovery trades"],
            [
                [r["core_state"], r["N_state_rows"], r["N_trades_entering"], r["pct_discovery_trades"]]
                for r in b["populations"]
            ],
        ),
        "",
        "# 8. STATE ECONOMICS",
        "",
        "First trade × state entry only. Subsequent PNL is hold-after-that-state, not a fill.",
        "",
        "### A",
        "",
        *_md_table(
            ["state", "N", "loss rate", "mean PNL", "T40", "MAE", "MFE", "recover>=80"],
            [_econ_row(r) for r in a["economics"]],
        ),
        "",
        "### B",
        "",
        *_md_table(
            ["state", "N", "loss rate", "mean PNL", "T40", "MAE", "MFE", "recover>=80"],
            [_econ_row(r) for r in b["economics"]],
        ),
        "",
        "# 9. STATE ORDERING",
        "",
        "Question: does HEALTHY → WATCH → PERSISTENCE_2 → PERSISTENCE_3PLUS show progressively worse subsequent economics?",
        f"A {a['ordering']['classification']} monotonic={a['ordering']['monotonic']} {a['ordering'].get('note') or ''}",
        f"A by metric {a['ordering'].get('by_metric')}",
        f"B {b['ordering']['classification']} monotonic={b['ordering']['monotonic']} {b['ordering'].get('note') or ''}",
        f"B by metric {b['ordering'].get('by_metric')}",
        "",
        "# 10. RECOVERY STATES",
        "",
        f"RECOVERING and {HEALTHY_AFTER_RECOVERY} are not depth ranks.",
        "Compare them to PERSISTENCE_2 in the predeclared contrasts.",
        "",
        "# 11. STATE CONTRASTS",
        "",
        "Clustered bootstrap, internal_game_id, seed 80, B 1000. A and B separate.",
        "",
        "### A",
        "",
        *_md_table(
            ["contrast", "metric", "n_left", "n_right", "delta", "class"],
            [
                [r["contrast"], r["metric"], r["n_left"], r["n_right"], _ci(r), r["classification"]]
                for r in a["contrasts"]
            ],
        ),
        "",
        "### B",
        "",
        *_md_table(
            ["contrast", "metric", "n_left", "n_right", "delta", "class"],
            [
                [r["contrast"], r["metric"], r["n_left"], r["n_right"], _ci(r), r["classification"]]
                for r in b["contrasts"]
            ],
        ),
        "",
        "# 12. STATE TRANSITION GRAPH",
        "",
        "Adjacent valid PRIMARY rows only. No interpolated edges.",
        "",
        "### A",
        "",
        *_mermaid("A", a["transition_counts"]),
        "### B",
        "",
        *_mermaid("B", b["transition_counts"]),
        "# 13. TRANSITION MATRIX",
        "",
        "Conditional frequencies are descriptive. They are not a loss hazard.",
        "",
        "### A nonzero",
        "",
        *_md_table(
            ["from", "to", "count", "frequency"],
            [
                [r["from_state"], r["to_state"], r["count"], r.get("conditional_frequency")]
                for r in a["transition_rates"]
                if int(r.get("count") or 0) > 0
            ],
        ),
        "",
        "### B nonzero",
        "",
        *_md_table(
            ["from", "to", "count", "frequency"],
            [
                [r["from_state"], r["to_state"], r["count"], r.get("conditional_frequency")]
                for r in b["transition_rates"]
                if int(r.get("count") or 0) > 0
            ],
        ),
        "",
        "# 14. TRANSITION ECONOMICS",
        "",
        "First occurrence per trade of the four required branches.",
        "",
        "### A",
        "",
        *_md_table(
            ["transition", "N", "loss rate", "mean PNL", "T40", "MAE", "MFE", "recover>=80"],
            [_econ_row(r) for r in a["transition_economics"]],
        ),
        "",
        *_md_table(
            ["branch contrast", "metric", "n_left", "n_right", "delta", "class"],
            [
                [r["contrast"], r["metric"], r["n_left"], r["n_right"], _ci(r), r["classification"]]
                for r in a.get("transition_branches") or []
            ],
        ),
        "",
        "### B",
        "",
        *_md_table(
            ["transition", "N", "loss rate", "mean PNL", "T40", "MAE", "MFE", "recover>=80"],
            [_econ_row(r) for r in b["transition_economics"]],
        ),
        "",
        *_md_table(
            ["branch contrast", "metric", "n_left", "n_right", "delta", "class"],
            [
                [r["contrast"], r["metric"], r["n_left"], r["n_right"], _ci(r), r["classification"]]
                for r in b.get("transition_branches") or []
            ],
        ),
        "",
        "# 15. PATH ARCHETYPES",
        "",
        "Mutually exclusive first-match labels. Not ranked. No winner or loser path names.",
        "",
        "### A",
        "",
        *_md_table(
            ["archetype", "N", "loss rate", "mean PNL", "T40", "MAE", "MFE", "recover>=80"],
            [_econ_row(r) for r in a["archetype_economics"]],
        ),
        "",
        "### B",
        "",
        *_md_table(
            ["archetype", "N", "loss rate", "mean PNL", "T40", "MAE", "MFE", "recover>=80"],
            [_econ_row(r) for r in b["archetype_economics"]],
        ),
        "",
        "# 16. STATE DEPTH",
        "",
        "Research ordinal only: HEALTHY 0, WATCH 1, PERSISTENCE_2 2, PERSISTENCE_3PLUS 3.",
        f"A economically ordered {a['depth'][0].get('economically_ordered') if a['depth'] else None} {a['depth'][0].get('note') if a['depth'] else ''}",
        f"B economically ordered {b['depth'][0].get('economically_ordered') if b['depth'] else None} {b['depth'][0].get('note') if b['depth'] else ''}",
        "",
        *_md_table(
            ["member", "state", "depth", "N", "loss", "mean PNL"],
            [
                ["A", r["core_state"], r["state_depth"], r["N_trades"], r["loss_rate"], r["mean_pnl_hold_after_state"]]
                for r in a["depth"]
            ]
            + [
                ["B", r["core_state"], r["state_depth"], r["N_trades"], r["loss_rate"], r["mean_pnl_hold_after_state"]]
                for r in b["depth"]
            ],
        ),
        "",
        "# 17. CI OVERLAY",
        "",
        "CI_CROSSES_ZERO vs CI_NEGATIVE inside each core state. Overlay does not change core_state.",
        "",
        *_md_table(
            ["member", "state", "n neg", "n cross", "delta", "class"],
            [
                ["A", r["core_state"], r["n_CI_NEGATIVE"], r["n_CI_CROSSES_ZERO"], _ci(r), r["classification"]]
                for r in a["ci_overlay"]
            ]
            + [
                ["B", r["core_state"], r["n_CI_NEGATIVE"], r["n_CI_CROSSES_ZERO"], _ci(r), r["classification"]]
                for r in b["ci_overlay"]
            ],
        ),
        "",
        "# 18. SUPPORT / MANIFOLD",
        "",
        "LOW_HISTORICAL_SUPPORT rows remain included. Threshold 2.5 was not refit.",
        "",
        *_md_table(
            ["member", "state", "N", "low-support rate", "mean ESS", "median distance"],
            [
                ["A", r["core_state"], r["N_trades"], r["LOW_HISTORICAL_SUPPORT_rate"], r["mean_ESS"], r["median_distance"]]
                for r in a["support_overlay"]
            ]
            + [
                ["B", r["core_state"], r["N_trades"], r["LOW_HISTORICAL_SUPPORT_rate"], r["mean_ESS"], r["median_distance"]]
                for r in b["support_overlay"]
            ],
        ),
        "",
        "# 19. MARKET DAMAGE AT STATE ENTRY",
        "",
        "Price and score are context. They do not define core_state.",
        "",
        *_md_table(
            ["member", "state", "mean price", "mean price travel", "mean adverse remaining"],
            [
                ["A", r["core_state"], r.get("mean_current_price"), r.get("mean_price_travel"), r.get("mean_adverse_cents_remaining")]
                for r in a["economics"]
                if r["core_state"] in {WATCH_NEGATIVE, PERSISTENCE_2, PERSISTENCE_3PLUS, RECOVERING}
            ]
            + [
                ["B", r["core_state"], r.get("mean_current_price"), r.get("mean_price_travel"), r.get("mean_adverse_cents_remaining")]
                for r in b["economics"]
                if r["core_state"] in {WATCH_NEGATIVE, PERSISTENCE_2, PERSISTENCE_3PLUS, RECOVERING}
            ],
        ),
        "",
        "# 20. INTERVENTION WINDOW REMAINING",
        "",
        "Descriptive remaining damage only. Not an instruction.",
        "",
        *_md_table(
            ["member", "state", "N", "mean adverse ¢", "mean minutes to worst", "mean minutes to settlement"],
            [
                ["A", r["core_state"], r["N_trades"], r.get("mean_adverse_cents_remaining"), r.get("mean_minutes_to_worst_price"), r.get("mean_minutes_to_settlement")]
                for r in a["remaining_damage"]
            ]
            + [
                ["B", r["core_state"], r["N_trades"], r.get("mean_adverse_cents_remaining"), r.get("mean_minutes_to_worst_price"), r.get("mean_minutes_to_settlement")]
                for r in b["remaining_damage"]
            ],
        ),
        "",
        "# 21. STATE TIMING",
        "",
        "STATE TIMING is not validated early warning.",
        "Phase 1 AVAILABLE warning among eventual losses remains A = 0 / 15 and B = 0 / 12.",
        "",
        *_md_table(
            ["member", "state", "result", "N", "minutes to T40", "minutes to worst", "adverse ¢"],
            [
                ["A", r["core_state"], r["eventual_result"], r["N_trades"], r.get("mean_minutes_to_T40", r.get("mean_minutes_to_worst_price")), r.get("mean_minutes_to_worst_price"), r.get("mean_adverse_cents_remaining")]
                for r in a["timing_summary"]
            ]
            + [
                ["B", r["core_state"], r["eventual_result"], r["N_trades"], r.get("mean_minutes_to_T40", r.get("mean_minutes_to_worst_price")), r.get("mean_minutes_to_worst_price"), r.get("mean_adverse_cents_remaining")]
                for r in b["timing_summary"]
            ],
        ),
        "",
        "# 22. H2_1 ALIGNMENT STATUS",
        "",
        f"status {alignment.get('status')}",
        f"potential_data_alignment_defect {alignment.get('potential_data_alignment_defect')}",
        f"n_clock_wall_mismatch {alignment.get('n_clock_wall_mismatch')}",
        f"n_aligned {alignment.get('n_aligned')}",
        "Copied from Phase 2. Timestamps were not repaired.",
        "",
        "# 23. STATISTICAL UNCERTAINTY",
        "",
        "Clustered bootstrap by internal_game_id. Seed 80. B 1000.",
        "Small first-entry cells stay INSUFFICIENT_SAMPLE. They are not filled.",
        "A and B are never combined into one OOS headline.",
        "",
        "# 24. LEAKAGE / INTEGRITY",
        "",
        f"model hash {audits['model']['status']}",
        f"cohort hash {audits['cohort']['status']}",
        f"confirmation protection {audits['confirmation']['status']}",
        f"Phase 2 unchanged {audits['phase2']['status']}",
        f"determinism {audits['determinism']['status']}",
        f"leakage {audits['leakage']['status']}",
        "Confirmation result files remain absent. POLICY_FREEZE.json remains absent.",
        "",
        "# 25. WHAT THE DATA SHOWS",
        "",
        "Austin EV sign history can be mapped onto a frozen eight-state language without using future outcomes.",
        f"Observed ordering is not assumed: A {a['ordering']['classification']}; B {b['ordering']['classification']}.",
        f"Recovery-versus-deeper branch information: {interp['gate_c_transition_information']}.",
        "",
        "# 26. WHAT AUSTIN MAY BE MEASURING",
        "",
        "The state language is a compression of already-computed hold-80-to-settlement EV sign and streak.",
        "It may be measuring persistence of a negative conditional EV, not a new predictive feature.",
        "CI and support overlays describe uncertainty and manifold distance; they do not create a new core state.",
        "",
        "# 27. WHAT HAS NOT BEEN PROVEN",
        "",
        "No loss hazard. No recovery probability. No policy. No confirmation. No live rule.",
        "Candle path is not a fill. Missing L2 remains SOURCE_UNAVAILABLE.",
        "A state is not an early warning. Phase 1 warning remains 0/15 and 0/12.",
        "",
        "# 28. WHETHER PHASE 4 IS JUSTIFIED",
        "",
        f"{interp['phase_4_decision']}",
        f"classification {interp['phase_4_classification']}",
        "Phase 4 is not started.",
        "",
        "PHASE 4 — NOT STARTED",
        "",
    ]
    text = "\n".join(lines)
    lowered = text.lower()
    if "holy grail" in lowered or "austin works" in lowered or "live ready" in lowered or "production ready" in lowered:
        raise AustinError("LOCK_MISMATCH", "downfall report used forbidden language")
    return text
