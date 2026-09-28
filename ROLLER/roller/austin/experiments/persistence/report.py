"""Persistence mechanism REPORT.md. No holy grail. No live ready."""

from __future__ import annotations

from typing import Any


def _fmt(value: object, digits: int = 4) -> str:
    if value is None:
        return "UNAVAILABLE"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _ci(block: dict[str, Any] | None) -> str:
    if not block:
        return "UNAVAILABLE"
    ci = block.get("ci") or [None, None]
    return f"{_fmt(block.get('observed_delta'))} CI=[{_fmt(ci[0])}, {_fmt(ci[1])}] {block.get('classification')}"


def _member_table(letter: str, stats: dict[str, Any]) -> list[str]:
    econ = stats["economics"]
    temp = econ["temporary"]
    pers = econ["persistent"]
    delta = econ["persistent_minus_temporary"]
    return [
        f"## {letter}",
        "",
        "FIRST NEGATIVE EV POPULATION",
        "",
        f"N first-negative {econ['n_first_negative']}",
        f"N temporary {econ['n_temporary']}",
        f"N persistent {econ['n_persistent']}",
        f"N unresolved {econ['n_unresolved']}",
        "",
        "TEMPORARY",
        f"wins {temp['N_wins']}",
        f"losses {temp['N_losses']}",
        f"mean subsequent PNL {_fmt(temp['mean_pnl_hold_after_t0'])}",
        f"median subsequent PNL {_fmt(temp['median_pnl_hold_after_t0'])}",
        f"T40 rate {_fmt(temp['T40_rate'])}",
        f"recover >=50 {_fmt(temp['recover_ge_50'])}",
        f"recover >=60 {_fmt(temp['recover_ge_60'])}",
        f"recover >=70 {_fmt(temp['recover_ge_70'])}",
        f"recover >=80 {_fmt(temp['recover_ge_80'])}",
        f"future MAE {_fmt(temp['mean_future_MAE'])}",
        f"future MFE {_fmt(temp['mean_future_MFE'])}",
        "",
        "PERSISTENT",
        f"wins {pers['N_wins']}",
        f"losses {pers['N_losses']}",
        f"mean subsequent PNL {_fmt(pers['mean_pnl_hold_after_t0'])}",
        f"median subsequent PNL {_fmt(pers['median_pnl_hold_after_t0'])}",
        f"T40 rate {_fmt(pers['T40_rate'])}",
        f"recover >=50 {_fmt(pers['recover_ge_50'])}",
        f"recover >=60 {_fmt(pers['recover_ge_60'])}",
        f"recover >=70 {_fmt(pers['recover_ge_70'])}",
        f"recover >=80 {_fmt(pers['recover_ge_80'])}",
        f"future MAE {_fmt(pers['mean_future_MAE'])}",
        f"future MFE {_fmt(pers['mean_future_MFE'])}",
        "",
        "PERSISTENT - TEMPORARY",
        f"Δ PNL {_ci(delta['pnl'])}",
        f"Δ loss rate {_ci(delta['loss_rate'])}",
        f"Δ T40 {_ci(delta['t40'])}",
        f"Δ MAE {_ci(delta['mae'])}",
        f"Δ MFE {_ci(delta['mfe'])}",
        "",
    ]


def _pit_lines(letter: str, rows: list[dict[str, Any]]) -> list[str]:
    lines = [f"### {letter} PIT DIFFERENCES AT FIRST NEGATIVE", ""]
    for row in rows:
        lines.append(
            f"{row['feature']}: temp {_fmt(row['temporary_mean'])}/{_fmt(row['temporary_median'])} "
            f"pers {_fmt(row['persistent_mean'])}/{_fmt(row['persistent_median'])} "
            f"Δ {_fmt(row['difference'])} CI={row.get('ci')} d={_fmt(row.get('effect_size'))} {row.get('classification')}"
        )
    lines.append("")
    return lines


def _landmark_lines(letter: str, rows: list[dict[str, Any]]) -> list[str]:
    lines = [f"### {letter} PERSISTENCE LANDMARKS", "", "Nested descriptive groups. No best row.", ""]
    for row in rows:
        lines.append(
            f"{row['landmark']}: N={row['N_trades']} loss_rate={_fmt(row['loss_rate'])} "
            f"mean PNL={_fmt(row['mean_pnl_hold_after_t0'])} T40={_fmt(row['T40_rate'])} "
            f"MAE={_fmt(row['mean_future_MAE'])} MFE={_fmt(row['mean_future_MFE'])}"
        )
    lines.append("")
    return lines


def interpret_persistence(stats_a: dict[str, Any], stats_b: dict[str, Any]) -> dict[str, Any]:
    a_pnl = stats_a["economics"]["persistent_minus_temporary"]["pnl"]
    b_pnl = stats_b["economics"]["persistent_minus_temporary"]["pnl"]
    a_warn = ((stats_a.get("warning_preserved") or {}).get("warning_before_damage_recall_among_losses") or {})
    b_warn = ((stats_b.get("warning_preserved") or {}).get("warning_before_damage_recall_among_losses") or {})
    extra = "MIXED"
    if a_pnl.get("classification") == "SUPPORTED" or b_pnl.get("classification") == "SUPPORTED":
        extra = "SUPPORTED"
    if a_pnl.get("classification") == "INSUFFICIENT_SAMPLE" and b_pnl.get("classification") == "INSUFFICIENT_SAMPLE":
        extra = "INSUFFICIENT_SAMPLE"
    before = "NOT_SUPPORTED"
    if (a_warn.get("n") or 0) > 0 or (b_warn.get("n") or 0) > 0:
        before = "MIXED"
    justify = False
    if extra == "SUPPORTED" and before in {"SUPPORTED", "MIXED"}:
        justify = False
    return {
        "persistence_contains_additional_information": extra,
        "information_appears_before_material_damage": before,
        "justifies_new_preregistered_v2_policy_experiment": justify,
        "future_hypothesis": (
            "If later work preregisters a delay-based persistence rule, it must be a new experiment. "
            "This audit does not create POLICY_G or freeze POLICY_A–F."
        ),
    }


def render_report(payload: dict[str, Any]) -> str:
    a = payload["A"]
    b = payload["B"]
    interp = payload["interpretation"]
    align = payload.get("alignment_verdict") or {}
    lines = [
        "AUSTIN",
        "PERSISTENCE MECHANISM AUDIT V1",
        "",
        "DISCOVERY ONLY",
        "",
        "MODEL FROZEN",
        "POLICY UNFROZEN",
        "CONFIRMATION UNTOUCHED",
        "EXECUTION DISABLED",
        "",
        "# 1. EXECUTIVE RESEARCH SUMMARY",
        "",
        "Austin can mark a worse state. This audit asks whether persistence of a negative",
        "Austin EV contains additional information about subsequent hold economics, and",
        "whether that distinction is visible before material damage.",
        "",
        f"Persistence additional information: {interp['persistence_contains_additional_information']}",
        f"Visible before material damage: {interp['information_appears_before_material_damage']}",
        f"Justifies new pre-registered V2 policy experiment: {interp['justifies_new_preregistered_v2_policy_experiment']}",
        "",
        "This is not Austin accuracy. Temporary/persistent labels are descriptive outcomes.",
        "",
        "# 2. AUDIT IDENTITY / LOCKS",
        "",
        f"audit_id {payload['manifest']['audit_id']}",
        f"model_manifest_hash {payload['manifest']['model_manifest_hash']}",
        f"A discovery hash {payload['manifest']['A_discovery_cohort_hash']}",
        f"A confirmation hash {payload['manifest']['A_confirmation_cohort_hash']}",
        f"B discovery hash {payload['manifest']['B_discovery_cohort_hash']}",
        f"B confirmation hash {payload['manifest']['B_confirmation_cohort_hash']}",
        f"git_commit {payload['manifest']['git_commit']} reason={payload['manifest']['git_commit_reason']}",
        f"confirmation_accessed {payload['manifest']['confirmation_accessed']}",
        f"policy_status {payload['manifest']['policy_status']}",
        f"policy_selected {payload['manifest']['policy_selected']}",
        "",
        "# 3. WHY THIS AUDIT EXISTS",
        "",
        "Discovery showed first-negative EV often recovers. Persistence of Austin EV is",
        "not automatically persistence of economic decline. The audit measures that gap.",
        "",
        "# 4. FIRST-NEGATIVE POPULATION",
        "",
        *_member_table("A · H1_2", a)[:9],
        *_member_table("B · H2_1", b)[:9],
        "# 5. TEMPORARY VS PERSISTENT NEGATIVE EV",
        "",
        "TEMPORARY_NEGATIVE_EV = later valid PRIMARY EV >= 0 exists.",
        "PERSISTENT_NEGATIVE_EV = later valid PRIMARY EV exists and all stay < 0.",
        "UNRESOLVED_NO_LATER_VALID_EV = no later valid PRIMARY EV.",
        "Missing later observations never imply persistent.",
        "Later is PRIMARY_GRID clock order, not wall timestamp. Discovery interpretation",
        "used timestamp order, so class counts can differ without changing Discovery files.",
        "",
        "# 6. ECONOMIC SEPARATION",
        "",
        *_member_table("A · H1_2", a),
        *_member_table("B · H2_1", b),
        "# 7. PIT STATE AT FIRST NEGATIVE EV",
        "",
        *_pit_lines("A", a["pit_comparison"]),
        *_pit_lines("B", b["pit_comparison"]),
        "# 8. TRAJECTORY AFTER FIRST NEGATIVE",
        "",
        "t1/t2/t3 are next valid PRIMARY states only. No interpolation.",
        "",
        "# 9. t1 / t2 PERSISTENCE LANDMARKS",
        "",
        *_landmark_lines("A", a["landmarks"]),
        *_landmark_lines("B", b["landmarks"]),
        "# 10. RECOVERY BEHAVIOR",
        "",
        "Recover >=50/60/70/80 is future price after t0. Outcome only.",
        "",
        "# 11. FUTURE MAE / MFE",
        "",
        "MAE/MFE are subsequent price extremes after t0. They are not PIT features.",
        "",
        "# 12. T40 RELATIONSHIP",
        "",
        f"A T40 temporary {_fmt(a['economics']['temporary']['T40_rate'])} persistent {_fmt(a['economics']['persistent']['T40_rate'])}",
        f"B T40 temporary {_fmt(b['economics']['temporary']['T40_rate'])} persistent {_fmt(b['economics']['persistent']['T40_rate'])}",
        "",
        "# 13. WARNING-TIME INTERPRETATION",
        "",
        "Discovery warning definition is preserved. It is not redefined to look better.",
        f"A AVAILABLE={a['warning_preserved']['n_WARNING_AVAILABLE']} TOO_LATE={a['warning_preserved']['n_WARNING_TOO_LATE']} NONE={a['warning_preserved']['n_NO_WARNING']}",
        f"B AVAILABLE={b['warning_preserved']['n_WARNING_AVAILABLE']} TOO_LATE={b['warning_preserved']['n_WARNING_TOO_LATE']} NONE={b['warning_preserved']['n_NO_WARNING']}",
        f"A warning-before-damage among losses {a['warning_preserved']['warning_before_damage_recall_among_losses']}",
        f"B warning-before-damage among losses {b['warning_preserved']['warning_before_damage_recall_among_losses']}",
        "New timing rows in warning_persistence_timing.csv are descriptive only.",
        "",
        "# 14. H2_1 ALIGNMENT AUDIT",
        "",
        f"status={align.get('status')}",
        f"potential_data_alignment_defect={align.get('potential_data_alignment_defect')}",
        f"n_clock_wall_mismatch={align.get('n_clock_wall_mismatch')} n_aligned={align.get('n_aligned')}",
        f"median_pbp_minus_entry_seconds={_fmt(align.get('median_pbp_minus_entry_seconds'))}",
        f"median_wall_minus_entry_seconds={_fmt(align.get('median_wall_minus_entry_seconds'))}",
        str(align.get("note") or ""),
        "",
        "# 15. SUPPORT / DISTANCE / MISSINGNESS",
        "",
        f"A unresolved {a['economics']['n_unresolved']} B unresolved {b['economics']['n_unresolved']}",
        "UNRESOLVED is not persistent. B remains thin on valid later states.",
        "",
        "# 16. STATISTICAL UNCERTAINTY",
        "",
        "cluster=internal_game_id seed=80 B=1000. A and B never pooled as the headline.",
        "Appendix A+B is labeled POOLED DESCRIPTIVE — NOT CONFIRMATION.",
        "",
        "# 17. LEAKAGE / INTEGRITY",
        "",
        f"model hash {payload['audits']['model']['status']}",
        f"leakage {payload['audits']['leakage']['status']}",
        f"confirmation protection {payload['audits']['confirmation']['status']}",
        "",
        "# 18. WHAT THE DATA SHOWS",
        "",
        f"A Δ PNL {_ci(a['economics']['persistent_minus_temporary']['pnl'])}",
        f"B Δ PNL {_ci(b['economics']['persistent_minus_temporary']['pnl'])}",
        "",
        "# 19. WHAT AUSTIN MAY BE MEASURING",
        "",
        "A first negative EV is a distress mark. Persistence of that mark is a later",
        "Austin-state description. It is not automatically terminal economic decline.",
        "",
        "# 20. WHAT HAS NOT BEEN PROVEN",
        "",
        "No live rule. No fill. No executable exit. No POLICY_* winner. No confirmation.",
        "No Austin accuracy percentage.",
        "",
        "# 21. WHETHER A NEW PRE-REGISTERED POLICY EXPERIMENT IS JUSTIFIED",
        "",
        f"{interp['justifies_new_preregistered_v2_policy_experiment']}",
        interp["future_hypothesis"],
        "",
        "FUTURE HYPOTHESIS only. No POLICY_G. No freeze. No confirmation.",
        "",
        "## Appendix · POOLED DESCRIPTIVE — NOT CONFIRMATION",
        "",
        f"pooled first-negative N={payload['pooled']['n_first_negative']}",
        "Not a headline. Not confirmation.",
        "",
        "POLICY STATUS = UNFROZEN",
        "CONFIRMATION A = NOT RUN",
        "CONFIRMATION B = NOT RUN",
        "",
    ]
    return "\n".join(lines)
