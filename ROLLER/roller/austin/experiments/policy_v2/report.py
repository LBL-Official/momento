"""Phase 5A REPORT.md. Preregistration only. No freeze. No live-ready language."""

from __future__ import annotations

from typing import Any

from roller.austin.experiments.persistence.report import _fmt


def _md_table(headers: list[str], rows: list[list[object]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_fmt(c) for c in row) + " |")
    return lines


def _class_econ(row: dict[str, Any]) -> str:
    n = int(row.get("intervention_n") or 0)
    if n < 5:
        return "INSUFFICIENT_SAMPLE"
    lo = row.get("delta_vs_hold_ci_lo")
    hi = row.get("delta_vs_hold_ci_hi")
    delta = row.get("delta_vs_hold")
    if delta is None or lo is None or hi is None:
        return "INSUFFICIENT_SAMPLE"
    if lo > 0:
        return "SUPPORTED"
    if hi < 0:
        return "NOT_SUPPORTED"
    return "MIXED"


def interpret(
    econ_a: list[dict[str, Any]],
    econ_b: list[dict[str, Any]],
    *,
    leakage: dict[str, Any],
    phase4: dict[str, Any],
) -> dict[str, Any]:
    by_id = {r["candidate_id"]: {"A": r} for r in econ_a}
    for row in econ_b:
        by_id.setdefault(row["candidate_id"], {})["B"] = row
    classes = {}
    for cid, pair in by_id.items():
        classes[cid] = {
            "A": _class_econ(pair.get("A") or {}),
            "B": _class_econ(pair.get("B") or {}),
        }
    proposed = "NONE"
    # Do not pick the max-EV candidate. Phase 4 MIXED / NOT JUSTIFIED is the prior.
    # A candidate is proposable only if A is SUPPORTED, B is not NOT_SUPPORTED,
    # winner sacrifice does not exceed cents saved, and median adverse remaining > 0.
    for cid, pair in by_id.items():
        a = pair.get("A") or {}
        if classes[cid]["A"] != "SUPPORTED":
            continue
        if classes[cid]["B"] == "NOT_SUPPORTED":
            continue
        if (a.get("winner_cents_sacrificed") or 0) > (a.get("cents_saved") or 0):
            continue
        if (a.get("median_adverse_cents_remaining") or 0) <= 0:
            continue
        proposed = cid
        break
    freeze = "NOT_SUPPORTED"
    if proposed != "NONE":
        if classes[proposed]["B"] == "INSUFFICIENT_SAMPLE" or phase4.get("mixed_caveat"):
            freeze = "MIXED"
        else:
            freeze = "SUPPORTED"
    gate_a = "PASS" if leakage.get("status") == "PASS" else "FAIL"
    gate_b = "SUPPORTED"
    gate_c = "NOT_SUPPORTED" if proposed == "NONE" else "MIXED"
    gate_d = "MIXED"
    if proposed != "NONE":
        a = by_id[proposed]["A"]
        if (a.get("winners_intervened") or 0) == 0:
            gate_d = "SUPPORTED"
        elif (a.get("winner_cents_sacrificed") or 0) > 2 * (a.get("cents_saved") or 0):
            gate_d = "NOT_SUPPORTED"
    gate_e = "MIXED"
    if proposed != "NONE" and (by_id[proposed]["A"].get("median_adverse_cents_remaining") or 0) > 0:
        gate_e = "SUPPORTED"
    if proposed == "NONE":
        gate_e = "NOT_SUPPORTED" if all((r.get("median_adverse_cents_remaining") or 0) <= 0 or (r.get("intervention_n") or 0) == 0 for r in econ_b) else "MIXED"
    gate_f = "MIXED"
    return {
        "gate_a_determinism": gate_a,
        "gate_b_mechanism_consistency": gate_b,
        "gate_c_discovery_economics": gate_c,
        "gate_d_winner_preservation": gate_d,
        "gate_e_timing": gate_e,
        "gate_f_transfer_support": gate_f,
        "candidate_classes": classes,
        "proposed_policy": proposed,
        "human_freeze_justified": freeze,
        "policy_status": "UNFROZEN",
        "phase_4_caveat": phase4.get("phase_5_decision"),
        "note": (
            "Phase 4 classification is MIXED and its decision text is PHASE 5 NOT JUSTIFIED. "
            "This exercise is preregistration only. POLICY_A–F are historical."
        ),
    }


def render_report(payload: dict[str, Any]) -> str:
    a = payload["econ_a"]
    b = payload["econ_b"]
    interp = payload["interpretation"]
    registry = payload["registry"]
    lines = [
        "AUSTIN DRE",
        "PHASE 5A — PRE-REGISTERED DRE POLICY V2",
        "",
        "DISCOVERY ONLY",
        "",
        "PHASE 2 FINALIZED",
        "PHASE 3 COMPLETE",
        "PHASE 4 COMPLETE",
        "",
        "AUSTIN FROZEN",
        "STATE MODEL FROZEN",
        "HAZARD MODEL FROZEN",
        "",
        "POLICY UNFROZEN",
        "CONFIRMATION UNTOUCHED",
        "",
        "EXECUTION DISABLED",
        "",
        "# 1. EXECUTIVE RESEARCH SUMMARY",
        "",
        f"Phase 4 handoff: {interp['phase_4_caveat']}. Classification MIXED. This is a preregistration exercise, not a freeze.",
        f"PROPOSED_POLICY {interp['proposed_policy']}. HUMAN_FREEZE_JUSTIFIED {interp['human_freeze_justified']}.",
        "POLICY_A…F remain historical discovery objects and were not selected.",
        interp["note"],
        "",
        "# 2. WATERFALL STATUS",
        "",
        "Phase 2 FINALIZED / actionability NOT MET. Phase 3 COMPLETE / MIXED. Phase 4 COMPLETE. Phase 6 not started.",
        "",
        "# 3. PHASE 4 HANDOFF",
        "",
        f"Hazard schema `{payload['hazard_schema_hash']}`. Gates A–F from Phase 4 remain MIXED except validity PASS.",
        "",
        "# 4. POLICY DESIGN PRINCIPLES",
        "",
        "Distress states only. H1 only. Frozen 0.2 calibration-bin edge. Support N>=10. Missing hazard → NONE.",
        "T40 already: allow trigger and classify TOO_LATE. First-fire only. No EV / price / clock cuts. No PNL sweep.",
        "",
        "# 5. CANDIDATE REGISTRY",
        "",
        f"Registry hash `{payload['candidate_registry_hash']}`. Written before economics. Immutable after.",
        "",
    ]
    for cand in registry["candidates"]:
        lines.append(f"- `{cand['candidate_id']}` states={cand['required_core_states']} {cand['rationale']}")
    lines.extend(["", "# 6. CANDIDATE PIT DEFINITIONS", "", "See POLICY_CANDIDATES.json. INTERVENE or NONE only.", ""])
    lines.extend(["# 7. CANDIDATE SUPPORT", "", "support_n >= 10 on every required probability. LOW_HISTORICAL_SUPPORT → NONE.", ""])
    for title, rows in (("8. DISCOVERY A ECONOMICS", a), ("9. DISCOVERY B ECONOMICS", b)):
        lines.extend([f"# {title}", ""])
        lines.extend(
            _md_table(
                ["Candidate", "Trigger N", "Rate", "Losses intervened", "Winners intervened", "Scenario-B EV", "Δ vs hold", "95% CI"],
                [
                    [
                        r["candidate_id"],
                        r["intervention_n"],
                        r["intervention_rate"],
                        r["losses_intervened"],
                        r["winners_intervened"],
                        r["scenario_b_ev"],
                        r["delta_vs_hold"],
                        f"[{r['delta_vs_hold_ci_lo']}, {r['delta_vs_hold_ci_hi']}]",
                    ]
                    for r in rows
                ],
            )
        )
        lines.append("")
    lines.extend(["# 10. LOSS AVOIDANCE", ""])
    lines.extend(
        _md_table(
            ["member", "candidate", "losses avoided", "cents saved"],
            [["A", r["candidate_id"], r["losses_avoided"], r["cents_saved"]] for r in a]
            + [["B", r["candidate_id"], r["losses_avoided"], r["cents_saved"]] for r in b],
        )
    )
    lines.extend(["", "# 11. WINNER SACRIFICE", ""])
    lines.extend(
        _md_table(
            ["member", "candidate", "winners abandoned", "winner cents sacrificed"],
            [["A", r["candidate_id"], r["winners_abandoned"], r["winner_cents_sacrificed"]] for r in a]
            + [["B", r["candidate_id"], r["winners_abandoned"], r["winner_cents_sacrificed"]] for r in b],
        )
    )
    lines.extend(["", "# 12. DRE VALUE ADDED", "", "losses_saved − winner_upside_sacrificed − declared_zero_execution_cost. Hypothetical only.", ""])
    lines.extend(
        _md_table(
            ["member", "candidate", "DRE value added"],
            [["A", r["candidate_id"], r["dre_value_added"]] for r in a] + [["B", r["candidate_id"], r["dre_value_added"]] for r in b],
        )
    )
    lines.extend(["", "# 13. TIMING / BEFORE-DAMAGE ANALYSIS", ""])
    lines.extend(
        _md_table(
            ["member", "candidate", "median price", "median adverse ¢", "median minutes to worst", "TOO_LATE N"],
            [["A", r["candidate_id"], r["median_trigger_price"], r["median_adverse_cents_remaining"], r["median_minutes_to_worst"], r["n_too_late"]] for r in a]
            + [["B", r["candidate_id"], r["median_trigger_price"], r["median_adverse_cents_remaining"], r["median_minutes_to_worst"], r["n_too_late"]] for r in b],
        )
    )
    lines.extend(
        [
            "",
            "# 14. SCENARIO A",
            "",
            "Observed yes_bid / current price at the first-fire checkpoint. SCENARIO — NOT OBSERVED FILL.",
            "",
            "# 15. SCENARIO B",
            "",
            "Next available 1-minute close from discovery PRIMARY. Primary comparison. SCENARIO — NOT OBSERVED FILL.",
            "",
            "# 16. STATISTICAL UNCERTAINTY",
            "",
            "Game-clustered bootstrap. cluster=internal_game_id. seed=80. B=1000.",
            "",
            "# 17. CROSS-MEMBER CONSISTENCY",
            "",
            "A and B are never pooled. B recovery / P2 / P3PLUS cells remain thin. That counts against freeze.",
            "",
            "# 18. LEAKAGE / INTEGRITY",
            "",
            f"Leakage {payload['audits']['leakage']['status']}. Confirmation accessed=false. POLICY_FREEZE.json not written.",
            "",
            "# 19. WHAT THE DATA SHOWS",
            "",
            f"Candidate classes: {interp['candidate_classes']}.",
            "",
            "# 20. WHAT THE POLICY WOULD DO",
            "",
            "INTERVENE is a hypothetical defensive-action branch on the later validation ledger. It is not a fill.",
            "",
            "# 21. WHAT HAS NOT BEEN PROVEN",
            "",
            "No confirmation. No freeze. No live EV. No execution. Candle path is not a fill. POLICY_A–F were not revived.",
            "",
            "# 22. PROPOSED POLICY OR NONE",
            "",
            f"PROPOSED_POLICY {interp['proposed_policy']}",
            "POLICY_STATUS AWAITING_HUMAN_FREEZE",
            "",
            "# 23. WHETHER HUMAN FREEZE IS JUSTIFIED",
            "",
            f"HUMAN_FREEZE_JUSTIFIED {interp['human_freeze_justified']}",
            "",
            "PHASE 6 — NOT STARTED",
            "",
        ]
    )
    return "\n".join(lines)
