"""Human-readable experiment report. No winner. Confirmation stays NOT RUN on discovery."""

from __future__ import annotations

from typing import Any

from roller.austin.experiments.ids import (
    EXPERIMENT_A,
    EXPERIMENT_B,
    N_A,
    N_B,
    PAGE3_BOOK_CENTS,
    PAGE3_EV_CENTS,
    PAGE3_N,
    PAGE3_S,
    SUITE_ID,
)
from roller.austin.paths import experiment_dir


def _cls(value: Any) -> str:
    if value in ("SUPPORTED", "MIXED", "NOT_SUPPORTED", "INSUFFICIENT_SAMPLE"):
        return str(value)
    return "INSUFFICIENT_SAMPLE" if value in (None, "", [], {}) else "MIXED"


def render_report(
    *,
    experiment_id: str,
    cohort: str,
    stats: dict[str, Any],
    freeze: dict[str, Any] | None,
) -> str:
    slice_name = "H1_2" if experiment_id == EXPERIMENT_A else "H2_1"
    n_lock = N_A if experiment_id == EXPERIMENT_A else N_B
    policies = stats.get("policies") or {}
    base = stats.get("baseline_hold") or {}
    warn = stats.get("warning") or {}
    cov = stats.get("coverage") or {}
    sig = stats.get("signal") or {}
    cal = stats.get("calibration") or {}
    discovery = cohort == "DISCOVERY"
    lines = [
        "# AUSTIN · CONDITIONAL RISK VALIDATION",
        "",
        "CROSS-DOMAIN TRANSFER TEST",
        "",
        f"**Suite:** `{SUITE_ID}`",
        f"**Experiment:** `{experiment_id}`",
        f"**TRAINING:** NBA Choosin N=604",
        f"**TEST:** NCAAB {slice_name} N={n_lock}",
        f"**Cohort:** `{cohort}`",
        f"**Observation:** EVERY 2 GAME-CLOCK MINUTES",
        f"**LIVE FEED:** UNAVAILABLE",
        f"**EXECUTION:** DISABLED",
        f"**FILL:** FILL_UNAVAILABLE",
        f"**POLICY STATUS:** {'UNFROZEN' if discovery else (None if freeze is None else freeze.get('policy_id'))}",
        f"**CONFIRMATION RESULT:** {'NOT RUN' if discovery else 'OBSERVED'}",
        "",
        "# 1. EXECUTIVE RESEARCH SUMMARY",
        "",
        "Does frozen Austin conditional EV contain forward-looking information about",
        "remaining hold-to-settlement economics at predetermined 2-minute checkpoints?",
        "",
        f"| Measure | {cohort} |",
        f"| --- | ---: |",
        f"| Games | {stats.get('N_games')} |",
        f"| Trades | {stats.get('N_trades')} |",
        f"| State observations | {stats.get('N_state_observations')} |",
        f"| BASELINE_HOLD EV ¢ | {base.get('ev_cents')} |",
        f"| Path complete / partial / unavailable | {cov.get('N_path_complete')} / {cov.get('N_path_partial')} / {cov.get('N_path_unavailable')} |",
        f"| EV ordering vs subsequent hold | {sig.get('ordering_status')} |",
        f"| Median warning minutes | {warn.get('median_minutes')} |",
        "",
        "No overall winner. No holy grail claim.",
        "",
        "# 2. EXPERIMENT IDENTITY",
        "",
        f"Suite `{SUITE_ID}`. Member `{experiment_id}`. Slice `{slice_name}` locked N={n_lock}.",
        "H2_2 is forbidden. Page 3 N=280 is display-only.",
        "",
        "# 3. MODEL LOCK",
        "",
        "austin_v2 · choosin_nba_2q3q_604 · K=25 · hold_80_to_settlement · NCAAB did not fit.",
        "",
        "# 4. COHORT LOCK",
        "",
        f"Role `{cohort}`. Games {stats.get('N_games')}. Trades {stats.get('N_trades')}.",
        "Split is temporal floor(G/2) unique games written before inference.",
        "",
        "# 5. DATA / PATH COVERAGE",
        "",
        str(cov),
        "",
        "# 6. AUSTIN CONDITIONAL EV VS SUBSEQUENT PNL",
        "",
        f"Negative EV states n={((sig.get('negative_ev') or {}).get('n'))} mean hold={((sig.get('negative_ev') or {}).get('mean_hold'))}",
        f"Non-negative EV states n={((sig.get('nonnegative_ev') or {}).get('n'))} mean hold={((sig.get('nonnegative_ev') or {}).get('mean_hold'))}",
        f"Ordering claim: {_cls(sig.get('ordering_status'))}",
        "",
        "# 7. EV TRAJECTORY / DETERIORATION",
        "",
        f"EV_NOW − EV_entry ≤ −8¢ n={((sig.get('deterioration_le_minus_8') or {}).get('n'))} mean hold={((sig.get('deterioration_le_minus_8') or {}).get('mean_hold'))}",
        f"Otherwise n={((sig.get('deterioration_gt_minus_8') or {}).get('n'))} mean hold={((sig.get('deterioration_gt_minus_8') or {}).get('mean_hold'))}",
        "",
        "# 8. WARNING TIME",
        "",
        f"AVAILABLE={warn.get('available')} TOO_LATE={warn.get('too_late')} NONE={warn.get('no_warning')} PATH_UNAVAILABLE={warn.get('path_unavailable')}",
        f"median={warn.get('median_minutes')} P25={warn.get('p25')} P75={warn.get('p75')} losers_median={warn.get('median_minutes_losers')}",
        f"mean adverse cents remaining={warn.get('mean_adverse_remaining')}",
        "Missing warning is not converted to zero.",
        "",
        "# 9. CALIBRATION",
        "",
        f"Status: {cal.get('status')}",
        str(cal.get("table")),
        "",
        "# 10. DISCOVERY POLICY TABLE",
        "",
        "Scenario B = next 1m close. SCENARIO — NOT OBSERVED FILL. No winner is marked.",
        "",
    ]
    for pid in ("POLICY_A", "POLICY_B", "POLICY_C", "POLICY_D", "POLICY_E", "POLICY_F"):
        row = policies.get(pid)
        if not row:
            continue
        ci = (row.get("delta_ci") or {}).get("ci")
        lines.append(
            f"- `{pid}` rate={row.get('intervention_rate')} baseline={row.get('baseline_hold', {}).get('ev_cents')} "
            f"policyB={row.get('policy_hypothetical_b', {}).get('ev_cents')} Δ={row.get('delta_mean')} CI={ci} "
            f"DD={row.get('max_dd_policy')} P10={row.get('p10_policy')} worst={row.get('worst_trade')} "
            f"avoided={row.get('losses_avoided')} saved={row.get('cents_saved')} "
            f"abandoned={row.get('winners_abandoned')} sacrificed={row.get('cents_sacrificed')} "
            f"warn_med={row.get('median_warning_minutes')}"
        )
    lines += [
        "",
        "# 11. FALSE INTERVENTIONS",
        "",
        "Winners abandoned and cents sacrificed are in the policy table. Not a count-only ratio.",
        "",
        "# 12. LOSSES AVOIDED / CENTS SAVED",
        "",
        "Avoided losers report cents saved, not only a count.",
        "",
        "# 13. EXECUTION SCENARIOS",
        "",
        "HYPOTHETICAL_INTERVENTION is SCENARIO — NOT OBSERVED FILL. FILL_UNAVAILABLE. FEE_MODEL=UNAVAILABLE.",
        "",
        "# 14. EQUITY / DRAWDOWN",
        "",
        "Equity curves are chronological by entry_timestamp. Discovery is not combined with confirmation.",
        "",
        "# 15. CLUSTERED STATISTICS",
        "",
        "Cluster = internal_game_id. seed=80. B=1000. Checkpoints are not independent bets.",
        "",
        "# 16. LOW-SUPPORT / OFF-MANIFOLD ANALYSIS",
        "",
        "LOW_HISTORICAL_SUPPORT rows remain in the experiment. Distance is not confidence.",
        "",
        "# 17. LEAKAGE / SELF-NEIGHBOR / INTEGRITY",
        "",
        "See leakage_audit.json and self_neighbor_audit.json. submits=false.",
        "",
        "# 18. DISCOVERY RESULT",
        "",
        "Family POLICY_A–F evaluated. Policy remains UNFROZEN. No automatic selection.",
        "",
        "# 19. CONFIRMATION RESULT",
        "",
        "NOT RUN" if discovery else "See confirmation artifacts.",
        "",
        "# 20. LIVE APPLICABILITY",
        "",
        "RESEARCH REPLAY VALIDATED · LIVE FEED UNAVAILABLE · EXECUTION DISABLED · FILL_UNAVAILABLE",
        "",
        "# WHAT THE DATA SHOWS",
        "",
        f"Locked {slice_name} N={n_lock}. Cohort {cohort}. Hold EV {base.get('ev_cents')}. Ordering {sig.get('ordering_status')}.",
        "",
        "# WHAT AUSTIN ADDS",
        "",
        "Frozen NBA-neighbor conditional EV and EV trajectory at 2-minute game-clock checkpoints after entry.",
        "",
        "# WHAT HAS NOT BEEN PROVEN",
        "",
        "Fills, live feed, 2026–27 NBA prospective validation, NCAAB-native model, confirmation generalization.",
        "",
        "# WHETHER THE EVIDENCE JUSTIFIES THE NEXT VALIDATION STAGE",
        "",
    ]
    if discovery:
        lines.append("Discovery evidence alone cannot establish generalization. Human must select one POLICY_A…F, then freeze, then run confirmation once per member.")
    else:
        lines.append("See confirmation ΔEV CI, warning time, false-intervention cents, and leakage audits.")
    if experiment_id == EXPERIMENT_B:
        lines += ["", f"Do not combine with {EXPERIMENT_A} as a headline OOS result."]
    return "\n".join(lines) + "\n"


def render_stop_report(experiment_id: str, stats: dict[str, Any], audits: dict[str, Any] | None = None) -> str:
    """§55 discovery completion card. No winner."""
    slice_name = "H1_2" if experiment_id == EXPERIMENT_A else "H2_1"
    n_lock = N_A if experiment_id == EXPERIMENT_A else N_B
    base = stats.get("baseline_hold") or {}
    warn = stats.get("warning") or {}
    cov = stats.get("coverage") or {}
    sig = stats.get("signal") or {}
    audits = audits or {}
    lines = [
        f"§55 DISCOVERY COMPLETION · {experiment_id}",
        f"slice={slice_name} locked N={n_lock}",
        f"integrity leakage={((audits.get('leakage') or {}).get('status'))} self_neighbor={((audits.get('self_neighbor') or {}).get('status'))}",
        f"cohort games={stats.get('N_games')} trades={stats.get('N_trades')} states={stats.get('N_state_observations')}",
        f"coverage complete/partial/unavailable={cov.get('N_path_complete')}/{cov.get('N_path_partial')}/{cov.get('N_path_unavailable')}",
        f"EV vs hold ordering={sig.get('ordering_status')} hold EV={base.get('ev_cents')}",
        f"warning AVAILABLE={warn.get('available')} TOO_LATE={warn.get('too_late')} NONE={warn.get('no_warning')} PATH_UNAVAILABLE={warn.get('path_unavailable')} median={warn.get('median_minutes')}",
        "policy table (no winner):",
    ]
    for pid in ("POLICY_A", "POLICY_B", "POLICY_C", "POLICY_D", "POLICY_E", "POLICY_F"):
        row = (stats.get("policies") or {}).get(pid) or {}
        lines.append(
            f"  {pid} rate={row.get('intervention_rate')} Δ={row.get('delta_mean')} CI={(row.get('delta_ci') or {}).get('ci')} "
            f"avoided={row.get('losses_avoided')} abandoned={row.get('winners_abandoned')}"
        )
    lines += [
        "",
        "DISCOVERY COMPLETE",
        "POLICY STATUS = UNFROZEN",
        "CONFIRMATION A = NOT RUN",
        "CONFIRMATION B = NOT RUN",
        "NEXT REQUIRED ACTION = HUMAN SELECTS EXACTLY ONE PRE-REGISTERED POLICY",
    ]
    return "\n".join(lines) + "\n"


def persist_report(experiment_id: str, cohort: str, text: str) -> None:
    root = experiment_dir(experiment_id)
    (root / cohort.lower()).mkdir(parents=True, exist_ok=True)
    (root / cohort.lower() / "REPORT.md").write_text(text, encoding="utf-8")
    if cohort == "DISCOVERY":
        (root / "REPORT.md").write_text(text, encoding="utf-8")
    if cohort == "CONFIRMATION":
        (root / "REPORT.md").write_text(text, encoding="utf-8")
        (root / "confirmation_REPORT.md").write_text(text, encoding="utf-8")
