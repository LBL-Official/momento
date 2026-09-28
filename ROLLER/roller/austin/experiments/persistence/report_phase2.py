"""Phase 2 REPORT.md. Discovery only. No live-ready language."""

from __future__ import annotations

from typing import Any

from roller.austin.experiments.persistence.report import _ci, _fmt


def _md_table(headers: list[str], rows: list[list[object]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_fmt(c) for c in row) + " |")
    return lines


def _class_of(rows: list[dict[str, Any]]) -> str:
    labels = {r.get("classification") for r in rows}
    if "SUPPORTED" in labels and labels <= {"SUPPORTED"}:
        return "SUPPORTED"
    if labels <= {"INSUFFICIENT_SAMPLE", None}:
        return "INSUFFICIENT_SAMPLE"
    if "SUPPORTED" in labels:
        return "MIXED"
    if "MIXED" in labels:
        return "MIXED"
    return "NOT_SUPPORTED"


def _supported_features(rows: list[dict[str, Any]]) -> list[str]:
    return [str(r.get("feature")) for r in rows if r.get("classification") == "SUPPORTED"]


def _combine_ab(a: str, b: str) -> str:
    pair = {a, b}
    if pair == {"SUPPORTED"}:
        return "SUPPORTED"
    if pair <= {"INSUFFICIENT_SAMPLE"}:
        return "INSUFFICIENT_SAMPLE"
    if "SUPPORTED" in pair or "MIXED" in pair:
        return "MIXED"
    return "NOT_SUPPORTED"


def interpret_phase2(
    stats_a: dict[str, Any],
    stats_b: dict[str, Any],
    *,
    alignment: dict[str, Any],
) -> dict[str, Any]:
    a_econ = stats_a["economics"]["persistent_minus_temporary"]
    b_econ = stats_b["economics"]["persistent_minus_temporary"]
    gate_a = _combine_ab(a_econ["pnl"]["classification"], b_econ["pnl"]["classification"])
    if gate_a == "MIXED" and (
        a_econ["loss_rate"]["classification"] == "SUPPORTED" or b_econ["loss_rate"]["classification"] == "SUPPORTED"
    ):
        gate_a = "MIXED"

    a_t0 = _supported_features(stats_a.get("pit_comparison") or [])
    b_t0 = _supported_features(stats_b.get("pit_comparison") or [])
    a_t1 = _supported_features(stats_a.get("t1_comparison") or [])
    b_t1 = _supported_features(stats_b.get("t1_comparison") or [])
    a_t2 = _supported_features(stats_a.get("t2_comparison") or [])
    b_t2 = _supported_features(stats_b.get("t2_comparison") or [])

    def step_status(a_feats: list[str], b_feats: list[str]) -> str:
        if a_feats and b_feats:
            return "SUPPORTED"
        if a_feats or b_feats:
            return "MIXED"
        a_cls = _class_of(stats_a.get("pit_comparison") or []) if a_feats == a_t0 else (
            _class_of(stats_a.get("t1_comparison") or []) if a_feats == a_t1 else _class_of(stats_a.get("t2_comparison") or [])
        )
        b_cls = _class_of(stats_b.get("pit_comparison") or []) if b_feats == b_t0 else (
            _class_of(stats_b.get("t1_comparison") or []) if b_feats == b_t1 else _class_of(stats_b.get("t2_comparison") or [])
        )
        if a_cls == "INSUFFICIENT_SAMPLE" and b_cls == "INSUFFICIENT_SAMPLE":
            return "INSUFFICIENT_SAMPLE"
        return "NOT_SUPPORTED"

    t0_status = step_status(a_t0, b_t0)
    t1_status = step_status(a_t1, b_t1)
    t2_status = step_status(a_t2, b_t2)
    if "SUPPORTED" in {t0_status, t1_status, t2_status}:
        gate_b = "SUPPORTED"
        earliest = "t0" if t0_status == "SUPPORTED" else ("t1" if t1_status == "SUPPORTED" else "t2")
    elif "MIXED" in {t0_status, t1_status, t2_status}:
        gate_b = "MIXED"
        earliest = "t0" if t0_status in {"SUPPORTED", "MIXED"} else ("t1" if t1_status in {"SUPPORTED", "MIXED"} else "t2")
    elif {t0_status, t1_status, t2_status} <= {"INSUFFICIENT_SAMPLE"}:
        gate_b = "INSUFFICIENT_SAMPLE"
        earliest = "NONE"
    else:
        gate_b = "NOT_SUPPORTED"
        earliest = "NONE"

    a_warn = ((stats_a.get("warning_preserved") or {}).get("warning_before_damage_recall_among_losses") or {})
    b_warn = ((stats_b.get("warning_preserved") or {}).get("warning_before_damage_recall_among_losses") or {})
    a_before = (a_warn.get("n") or 0) > 0
    b_before = (b_warn.get("n") or 0) > 0
    a_win = (stats_a.get("window") or {}).get("t1") or {}
    b_win = (stats_b.get("window") or {}).get("t1") or {}
    remaining = None
    for block in (a_win, b_win, (stats_a.get("window") or {}).get("t0") or {}, (stats_b.get("window") or {}).get("t0") or {}):
        val = block.get("mean_adverse_cents_remaining")
        if val is not None:
            remaining = val if remaining is None else max(remaining, val)
    if gate_b in {"NOT_SUPPORTED", "INSUFFICIENT_SAMPLE"}:
        gate_c = "NOT_SUPPORTED" if gate_b == "NOT_SUPPORTED" else "INSUFFICIENT_SAMPLE"
        timing_note = "PIT distinguishability is not established, so timing cannot be an actionable mechanism."
    elif a_before or b_before:
        gate_c = "MIXED"
        timing_note = "Some Discovery AVAILABLE warnings exist, but they are not the Phase 1 loss-warning result."
    elif remaining is not None and remaining > 0:
        gate_c = "MIXED"
        timing_note = (
            "Some adverse cents remain after t0/t1 on persistent paths, but Discovery AVAILABLE "
            "warning among eventual losses remains 0. Hindsight persistence is not the same as a before-damage signal."
        )
    else:
        gate_c = "NOT_SUPPORTED"
        timing_note = "Distinguishability, if any, does not appear before the existing damage events."

    align_status = alignment.get("status") or "INSUFFICIENT_TO_DETERMINE"
    gate_d = align_status
    defect = bool(alignment.get("potential_data_alignment_defect"))

    if defect:
        phase3 = False
        acceptance = "alignment defect — stop; do not repair inside Phase 2"
    elif gate_a == "SUPPORTED" and gate_b == "SUPPORTED" and gate_c == "SUPPORTED":
        phase3 = True
        acceptance = "PHASE 3 MAY BE JUSTIFIED"
    elif gate_a in {"SUPPORTED", "MIXED"} and gate_b in {"NOT_SUPPORTED", "INSUFFICIENT_SAMPLE"}:
        phase3 = False
        acceptance = "interesting hindsight classification — not yet a DRE mechanism"
    elif gate_a in {"SUPPORTED", "MIXED"} and gate_b in {"SUPPORTED", "MIXED"} and gate_c != "SUPPORTED":
        phase3 = False
        acceptance = "valid state diagnosis — not an actionable risk mechanism"
    else:
        phase3 = False
        acceptance = "Phase 3 is not yet justified"

    extra = gate_a
    return {
        "gate_a_persistence_economics": gate_a,
        "gate_b_pit_distinguishability": gate_b,
        "gate_c_timing": gate_c,
        "gate_d_data_integrity": gate_d,
        "persistence_contains_additional_information": extra,
        "earliest_distinguishable_checkpoint": earliest,
        "t0_status": t0_status,
        "t1_status": t1_status,
        "t2_status": t2_status,
        "supported_features": {"A_t0": a_t0, "B_t0": b_t0, "A_t1": a_t1, "B_t1": b_t1, "A_t2": a_t2, "B_t2": b_t2},
        "meaningful_adverse_movement_still_remains": gate_c,
        "timing_note": timing_note,
        "phase_3_justified": phase3,
        "acceptance": acceptance,
        "justifies_new_preregistered_v2_policy_experiment": False,
        "future_hypothesis": (
            "If later work preregisters a delay-based persistence rule, it must be a new Phase 5 object. "
            "Phase 2 does not create a policy and does not freeze one."
        ),
    }


def _econ_table(letter: str, stats: dict[str, Any]) -> list[str]:
    econ = stats["economics"]
    temp = econ["temporary"]
    pers = econ["persistent"]
    means_t = econ.get("temporary_means") or {}
    means_p = econ.get("persistent_means") or {}
    delta = econ["persistent_minus_temporary"]
    n_t = temp.get("N_trades")
    n_p = pers.get("N_trades")
    rows = [
        ["N", n_t, n_p, None, ""],
        ["Win rate", temp.get("win_rate"), pers.get("win_rate"), None, ""],
        ["Loss rate", temp.get("loss_rate"), pers.get("loss_rate"), delta["loss_rate"].get("observed_delta"), _ci(delta["loss_rate"])],
        ["Mean subsequent PNL", temp.get("mean_pnl_hold_after_t0"), pers.get("mean_pnl_hold_after_t0"), delta["pnl"].get("observed_delta"), _ci(delta["pnl"])],
        ["Median subsequent PNL", temp.get("median_pnl_hold_after_t0"), pers.get("median_pnl_hold_after_t0"), None, ""],
        ["T40 rate", temp.get("T40_rate"), pers.get("T40_rate"), delta["t40"].get("observed_delta"), _ci(delta["t40"])],
        ["Future MAE", temp.get("mean_future_MAE"), pers.get("mean_future_MAE"), delta["mae"].get("observed_delta"), _ci(delta["mae"])],
        ["Future MFE", temp.get("mean_future_MFE"), pers.get("mean_future_MFE"), delta["mfe"].get("observed_delta"), _ci(delta["mfe"])],
        ["Recover ≥50", temp.get("recover_ge_50"), pers.get("recover_ge_50"), None, ""],
        ["Recover ≥60", temp.get("recover_ge_60"), pers.get("recover_ge_60"), None, ""],
        ["Recover ≥70", temp.get("recover_ge_70"), pers.get("recover_ge_70"), None, ""],
        ["Recover ≥80", temp.get("recover_ge_80"), pers.get("recover_ge_80"), None, ""],
        ["First-negative EV", means_t.get("mean_first_negative_EV"), means_p.get("mean_first_negative_EV"), None, ""],
        ["EV change from entry", means_t.get("mean_EV_deterioration_from_entry"), means_p.get("mean_EV_deterioration_from_entry"), None, ""],
        ["Price at t0", means_t.get("mean_price_at_first_negative"), means_p.get("mean_price_at_first_negative"), None, ""],
        ["Price travel", means_t.get("mean_price_travel"), means_p.get("mean_price_travel"), None, ""],
        ["Game time remaining", means_t.get("mean_game_time_remaining"), means_p.get("mean_game_time_remaining"), None, ""],
    ]
    return [
        f"### {letter} · TEMPORARY VS PERSISTENT",
        "",
        f"N first-negative {econ['n_first_negative']}",
        f"N temporary {econ['n_temporary']}",
        f"N persistent {econ['n_persistent']}",
        f"N unresolved {econ['n_unresolved']}",
        "",
        *_md_table(["Metric", "Temporary", "Persistent", "Difference", "95% CI"], rows),
        "",
    ]


def _landmark_table(letter: str, rows: list[dict[str, Any]]) -> list[str]:
    body = [
        [
            r.get("landmark"),
            r.get("N_trades"),
            r.get("loss_rate"),
            r.get("mean_pnl_hold_after_t0"),
            r.get("T40_rate"),
            r.get("mean_future_MAE"),
            r.get("mean_future_MFE"),
        ]
        for r in rows
    ]
    return [
        f"### {letter} · PERSISTENCE LANDMARKS",
        "",
        "Nested descriptive groups. No best row. Missing later states do not imply persistence.",
        "",
        *_md_table(
            ["State", "N", "Loss rate", "Mean future PNL", "T40 rate", "Future MAE", "Future MFE"],
            body,
        ),
        "",
    ]


def _pit_table(letter: str, title: str, rows: list[dict[str, Any]]) -> list[str]:
    wanted = {
        "first_negative_EV": "EV",
        "EV": "EV",
        "EV_DEPTH_BELOW_ZERO": "EV depth",
        "EV_CHANGE_FROM_ENTRY": "ΔEV from entry",
        "EV_CHANGE_FROM_PREVIOUS": "ΔEV from previous",
        "EV_SLOPE_FROM_ENTRY": "EV slope",
        "EV_change_from_t0": "ΔEV from t0",
        "EV_velocity": "EV velocity",
        "CI_LOWER": "CI lower",
        "CI_lower": "CI lower",
        "CI_UPPER": "CI upper",
        "CI_upper": "CI upper",
        "CI_WIDTH": "CI width",
        "CI_width": "CI width",
        "PRICE_TRAVEL": "Price travel",
        "price_change_from_t0": "Price change",
        "SCORE_DIFF_TRAVEL": "Score diff travel",
        "score_diff_change_from_t0": "Score diff change",
        "TIME_SINCE_ENTRY": "Time since entry",
        "GAME_TIME_REMAINING": "Time remaining",
        "ESS": "ESS",
        "MEDIAN_DISTANCE": "Median distance",
        "median_distance": "Median distance",
    }
    body = []
    for row in rows:
        name = wanted.get(str(row.get("feature")))
        if name is None:
            continue
        ci = row.get("ci") or [None, None]
        body.append(
            [
                name,
                row.get("temporary_mean"),
                row.get("persistent_mean"),
                row.get("difference"),
                f"[{_fmt(ci[0])}, {_fmt(ci[1])}]" if ci else "UNAVAILABLE",
                row.get("effect_size"),
            ]
        )
    return [
        f"### {letter} · {title}",
        "",
        *_md_table(["Feature", "Temporary", "Persistent", "Difference", "95% CI", "Effect size"], body),
        "",
    ]


def render_phase2_report(payload: dict[str, Any]) -> str:
    a = payload["A"]
    b = payload["B"]
    interp = payload["interpretation"]
    align = payload.get("alignment_verdict") or {}
    manifest = payload["manifest"]
    lines = [
        "AUSTIN DRE",
        "PHASE 2 — PERSISTENCE MECHANISM",
        "",
        "DISCOVERY ONLY",
        "",
        "MODEL FROZEN",
        "POLICY UNFROZEN",
        "CONFIRMATION UNTOUCHED",
        "",
        "LIVE FEED UNAVAILABLE",
        "EXECUTION DISABLED",
        "",
        "# 1. EXECUTIVE RESEARCH SUMMARY",
        "",
        "Phase 2 asks whether persistence of a negative Austin EV contains incremental information",
        "beyond EV < 0, whether that distinction is visible at t0/t1/t2, and whether it appears",
        "while meaningful adverse movement still remains.",
        "",
        f"Gate A persistence economics: {interp['gate_a_persistence_economics']}",
        f"Gate B PIT distinguishability: {interp['gate_b_pit_distinguishability']}",
        f"Gate C timing: {interp['gate_c_timing']}",
        f"Gate D H2_1 alignment: {interp['gate_d_data_integrity']}",
        f"Earliest predetermined checkpoint with any PIT separation: {interp['earliest_distinguishable_checkpoint']}",
        f"Phase 3 justified: {interp['phase_3_justified']}",
        f"Acceptance reading: {interp['acceptance']}",
        "",
        interp["timing_note"],
        "",
        "Temporary / persistent labels are future-derived descriptive outcomes. They are not PIT features.",
        "",
        "# 2. PHASE IDENTITY",
        "",
        f"phase {manifest.get('phase')}",
        f"phase_name {manifest.get('phase_name')}",
        f"audit_id {manifest.get('audit_id')}",
        f"source_suite {manifest.get('source_suite')}",
        f"source_experiment_A {manifest.get('source_experiment_A')}",
        f"source_experiment_B {manifest.get('source_experiment_B')}",
        f"observation_schedule {manifest.get('observation_schedule')}",
        f"EV_definition {manifest.get('EV_definition')}",
        f"confirmation_accessed {manifest.get('confirmation_accessed')}",
        f"policy_status {manifest.get('policy_status')}",
        f"policy_selected {manifest.get('policy_selected')}",
        f"execution_enabled {manifest.get('execution_enabled')}",
        f"submits {manifest.get('submits')}",
        "",
        "# 3. MODEL / COHORT LOCKS",
        "",
        f"model_version {manifest.get('model_version')}",
        f"dataset_version {manifest.get('dataset_version')}",
        f"model_manifest_hash {manifest.get('model_manifest_hash')}",
        f"feature_schema_hash {manifest.get('feature_schema_hash')}",
        f"pca_version {manifest.get('pca_version')}",
        f"K {manifest.get('K')}",
        f"A discovery hash {manifest.get('A_discovery_cohort_hash')}",
        f"A confirmation hash {manifest.get('A_confirmation_cohort_hash')}",
        f"B discovery hash {manifest.get('B_discovery_cohort_hash')}",
        f"B confirmation hash {manifest.get('B_confirmation_cohort_hash')}",
        f"git_commit {manifest.get('git_commit')} reason={manifest.get('git_commit_reason')}",
        "NCAAB is query-only. It does not enter scaler, PCA, or KNN.",
        "",
        "# 4. WHY PHASE 2 EXISTS",
        "",
        "Phase 1 showed Austin can mark worse states. EV < 0 is not 'this trade will lose.'",
        "H1_2 discovery first-negative (timestamp-order interpretation) was 67 / 47 temporary /",
        "15 persistent / 5 unresolved. H2_1 was 22 / 5 / 5 / 12. Phase 1 AVAILABLE warning",
        "among eventual losses remains A 0/15 and B 0/12. Phase 2 does not rerun Phase 1",
        "and does not redefine that warning.",
        "",
        "# 5. FIRST-NEGATIVE POPULATIONS",
        "",
        "t0 is the earliest valid PRIMARY_GRID Austin state with conditional_EV < 0.",
        "Diagnostic 42/41/40/T40/ENTRY rows do not define t0 unless they are PRIMARY_GRID.",
        "",
        f"A N first-negative {a['economics']['n_first_negative']} temporary {a['economics']['n_temporary']} persistent {a['economics']['n_persistent']} unresolved {a['economics']['n_unresolved']}",
        f"B N first-negative {b['economics']['n_first_negative']} temporary {b['economics']['n_temporary']} persistent {b['economics']['n_persistent']} unresolved {b['economics']['n_unresolved']}",
        "",
        "Later is PRIMARY_GRID clock order. Discovery interpretation used timestamp order,",
        "so class counts can differ without changing Phase 1 files.",
        "",
        "# 6. TEMPORARY VS PERSISTENT NEGATIVE EV",
        "",
        "TEMPORARY_NEGATIVE_EV = later valid PRIMARY EV >= 0 exists.",
        "PERSISTENT_NEGATIVE_EV = later valid PRIMARY EV exists and all stay < 0.",
        "UNRESOLVED_NO_LATER_VALID_EV = no later valid PRIMARY EV.",
        "Missing later observations never imply persistent.",
        "",
        *_econ_table("A · H1_2", a),
        *_econ_table("B · H2_1", b),
        "# 7. ECONOMIC SEPARATION",
        "",
        f"A Δ PNL {_ci(a['economics']['persistent_minus_temporary']['pnl'])}",
        f"A Δ loss rate {_ci(a['economics']['persistent_minus_temporary']['loss_rate'])}",
        f"B Δ PNL {_ci(b['economics']['persistent_minus_temporary']['pnl'])}",
        f"B Δ loss rate {_ci(b['economics']['persistent_minus_temporary']['loss_rate'])}",
        "",
        "A and B are never pooled as the headline. Appendix A+B is descriptive only.",
        "",
        "# 8. PIT DIFFERENCES AT t0",
        "",
        "Question: before seeing the future Austin path, were persistent-negative trades already different at t0?",
        "Differences are not a rule.",
        "",
        *_pit_table("A", "t0 PIT", a.get("pit_comparison") or []),
        *_pit_table("B", "t0 PIT", b.get("pit_comparison") or []),
        f"t0 status A/B features SUPPORTED: {interp['supported_features']['A_t0']} / {interp['supported_features']['B_t0']}",
        "",
        "# 9. t1 TRAJECTORY",
        "",
        "t1 is the next valid PRIMARY_GRID state only. No interpolation.",
        "Question: does one additional predetermined checkpoint materially improve separation?",
        "",
        *_pit_table("A", "t1", a.get("t1_comparison") or []),
        *_pit_table("B", "t1", b.get("t1_comparison") or []),
        f"t1 status: {interp['t1_status']}",
        "",
        "# 10. t2 TRAJECTORY",
        "",
        "Question: by two subsequent 2-minute checkpoints, is persistent deterioration clearly distinguishable?",
        "Descriptive only. No optimal checkpoint search.",
        "",
        *_pit_table("A", "t2", a.get("t2_comparison") or []),
        *_pit_table("B", "t2", b.get("t2_comparison") or []),
        f"t2 status: {interp['t2_status']}",
        "",
        "# 11. t3 / LONGER PERSISTENCE",
        "",
        *_landmark_table("A · H1_2", a.get("landmarks") or []),
        *_landmark_table("B · H2_1", b.get("landmarks") or []),
        f"A availability {(a.get('availability') or {})}",
        f"B availability {(b.get('availability') or {})}",
        "",
        "# 12. EV DEPTH / VELOCITY / ACCELERATION",
        "",
        "Derivatives use game-clock minutes between valid PRIMARY points. Missing stays UNAVAILABLE.",
        "No smoothing. No cutoff search.",
        "",
        f"A dynamics {a.get('dynamics')}",
        f"B dynamics {b.get('dynamics')}",
        "",
        "# 13. RECOVERY BEHAVIOR",
        "",
        f"A recovery {a.get('recovery')}",
        f"B recovery {b.get('recovery')}",
        "",
        "# 14. DOWNFALL BEHAVIOR",
        "",
        f"A downfall {a.get('downfall')}",
        f"B downfall {b.get('downfall')}",
        "",
        "# 15. T40 / MAE / MFE",
        "",
        f"A T40 temporary {_fmt(a['economics']['temporary']['T40_rate'])} persistent {_fmt(a['economics']['persistent']['T40_rate'])}",
        f"B T40 temporary {_fmt(b['economics']['temporary']['T40_rate'])} persistent {_fmt(b['economics']['persistent']['T40_rate'])}",
        f"A MAE temporary {_fmt(a['economics']['temporary']['mean_future_MAE'])} persistent {_fmt(a['economics']['persistent']['mean_future_MAE'])}",
        f"B MAE temporary {_fmt(b['economics']['temporary']['mean_future_MAE'])} persistent {_fmt(b['economics']['persistent']['mean_future_MAE'])}",
        f"A MFE temporary {_fmt(a['economics']['temporary']['mean_future_MFE'])} persistent {_fmt(a['economics']['persistent']['mean_future_MFE'])}",
        f"B MFE temporary {_fmt(b['economics']['temporary']['mean_future_MFE'])} persistent {_fmt(b['economics']['persistent']['mean_future_MFE'])}",
        "",
        "# 16. INTERVENTION WINDOW REMAINING",
        "",
        "Descriptive object only. Not a trading instruction. Phase 5+ would simulate an intervention.",
        "",
        f"A window {a.get('window')}",
        f"B window {b.get('window')}",
        "",
        "# 17. WARNING-TIME INTERPRETATION",
        "",
        "Discovery warning definition is preserved. It is not redefined to look better.",
        f"A AVAILABLE={a['warning_preserved']['n_WARNING_AVAILABLE']} TOO_LATE={a['warning_preserved']['n_WARNING_TOO_LATE']} NONE={a['warning_preserved']['n_NO_WARNING']}",
        f"B AVAILABLE={b['warning_preserved']['n_WARNING_AVAILABLE']} TOO_LATE={b['warning_preserved']['n_WARNING_TOO_LATE']} NONE={b['warning_preserved']['n_NO_WARNING']}",
        f"A warning-before-damage among losses {a['warning_preserved']['warning_before_damage_recall_among_losses']}",
        f"B warning-before-damage among losses {b['warning_preserved']['warning_before_damage_recall_among_losses']}",
        f"A Phase 2 timing {a.get('warning_timing_summary')}",
        f"B Phase 2 timing {b.get('warning_timing_summary')}",
        "",
        "# 18. SUPPORT / MANIFOLD ANALYSIS",
        "",
        "Low-support states are retained. The question is whether persistence is only off-manifold.",
        "",
        f"A support {a.get('support')}",
        f"B support {b.get('support')}",
        "",
        "# 19. H2_1 ALIGNMENT AUDIT",
        "",
        f"status={align.get('status')}",
        f"potential_data_alignment_defect={align.get('potential_data_alignment_defect')}",
        f"n_clock_wall_mismatch={align.get('n_clock_wall_mismatch')} n_aligned={align.get('n_aligned')}",
        f"median_pbp_minus_entry_seconds={_fmt(align.get('median_pbp_minus_entry_seconds'))}",
        f"median_wall_minus_entry_seconds={_fmt(align.get('median_wall_minus_entry_seconds'))}",
        str(align.get("note") or ""),
        "Phase 2 does not repair timestamps. A reconstruction change would need a new version.",
        "",
        "# 20. STATISTICAL UNCERTAINTY",
        "",
        "cluster=internal_game_id seed=80 B=1000. A and B never pooled as the headline.",
        "Appendix A+B is labeled POOLED DESCRIPTIVE — NOT CONFIRMATION.",
        "",
        "# 21. LEAKAGE / INTEGRITY",
        "",
        f"model hash {payload['audits']['model']['status']}",
        f"leakage {payload['audits']['leakage']['status']}",
        f"confirmation protection {payload['audits']['confirmation']['status']}",
        "PIT vectors at t0/t1/t2 exclude future labels, future T40, future MAE/MFE, and eventual outcome.",
        "Mutating bars/PBP after a checkpoint must leave that checkpoint's descriptor unchanged.",
        "",
        "# 22. WHAT THE DATA SHOWS",
        "",
        f"A Δ PNL {_ci(a['economics']['persistent_minus_temporary']['pnl'])}",
        f"B Δ PNL {_ci(b['economics']['persistent_minus_temporary']['pnl'])}",
        f"Gate A {interp['gate_a_persistence_economics']}",
        f"Gate B {interp['gate_b_pit_distinguishability']} earliest={interp['earliest_distinguishable_checkpoint']}",
        f"Gate C {interp['gate_c_timing']}",
        "",
        "# 23. WHAT AUSTIN MAY BE MEASURING",
        "",
        "A first negative EV is a distress mark. Persistence of that mark is a later Austin-state",
        "description. It is not automatically terminal economic decline, and it is not a live signal.",
        "",
        "# 24. WHAT HAS NOT BEEN PROVEN",
        "",
        "No live rule. No fill. No executable exit. No new policy. No confirmation. No Austin V3.",
        "No threshold search. No Phase 3 downfall-state model.",
        "",
        "# 25. WHETHER PHASE 3 IS JUSTIFIED",
        "",
        f"{interp['phase_3_justified']}",
        interp["acceptance"],
        interp["future_hypothesis"],
        "",
        "Phase 3 is not started automatically.",
        "",
        "## Appendix · POOLED DESCRIPTIVE — NOT CONFIRMATION",
        "",
        f"pooled first-negative N={payload['pooled']['n_first_negative']}",
        "Not a headline. Not confirmation.",
        "",
        "POLICY STATUS = UNFROZEN",
        "CONFIRMATION A = NOT RUN",
        "CONFIRMATION B = NOT RUN",
        "EXECUTION = DISABLED",
        "NEXT PHASE = PHASE 3 — NOT STARTED",
        "",
    ]
    return "\n".join(lines)
