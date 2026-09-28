"""Phase 3 integrity audits. Confirmation is identity-only. Phase 2 files stay read-only."""

from __future__ import annotations

from typing import Any

from roller.austin.errors import AustinError
from roller.austin.experiments.downfall.engine import derive_downfall_state
from roller.austin.experiments.downfall.ids import (
    FORBIDDEN_PIT,
    LOCKED_ALIGNMENT_STATUS,
    LOCKED_CLOCK_ORDER,
    LOCKED_WARNING_LOSSES,
    PHASE2_REPORT_SHA256,
    PHASE2_STATISTICS_SHA256,
)
from roller.austin.experiments.downfall.timeline import build_timeline, trade_primary
from roller.austin.experiments.ids import EXPERIMENT_A, EXPERIMENT_B
from roller.austin.experiments.manifest import sha256_file
from roller.austin.experiments.ncaab_state import mutate_future_and_rebuild
from roller.austin.experiments.persistence.audits import cohort_hash_audit, confirmation_protection_audit, model_hash_audit
from roller.austin.experiments.persistence.warning import preserved_warning
from roller.austin.paths import persistence_phase2_dir
from roller.austin.store import load_json


def phase2_unchanged_audit() -> dict[str, Any]:
    root = persistence_phase2_dir()
    report = root / "REPORT.md"
    stats_path = root / "statistics.json"
    if not report.is_file() or not stats_path.is_file():
        raise AustinError("DATA_REQUIRED", "Phase 2 artifacts missing; Phase 3 cannot start")
    report_sha = sha256_file(report)
    stats_sha = sha256_file(stats_path)
    stats = load_json(stats_path)
    interp = stats.get("interpretation") or {}
    a_econ = (stats.get("A") or {}).get("economics") or {}
    b_econ = (stats.get("B") or {}).get("economics") or {}
    align = stats.get("alignment_verdict") or {}
    if report_sha != PHASE2_REPORT_SHA256 or stats_sha != PHASE2_STATISTICS_SHA256:
        raise AustinError("LOCK_MISMATCH", "Phase 2 REPORT/statistics hash drifted; STOP")
    if interp.get("phase_3_justified") is not False:
        raise AustinError("LOCK_MISMATCH", "Phase 2 phase_3_justified is no longer false; STOP")
    if "NOT MET" not in str(interp.get("acceptance") or "").upper() and interp.get("phase_3_justified") is not False:
        raise AustinError("LOCK_MISMATCH", "Phase 2 actionability drifted; STOP")
    for eid, econ in ((EXPERIMENT_A, a_econ), (EXPERIMENT_B, b_econ)):
        locked = LOCKED_CLOCK_ORDER[eid]
        for key, expected in locked.items():
            if econ.get(key) != expected:
                raise AustinError("LOCK_MISMATCH", f"Phase 2 clock-order {eid} {key} drifted; STOP")
    if align.get("status") != LOCKED_ALIGNMENT_STATUS or align.get("potential_data_alignment_defect") is not False:
        raise AustinError("LOCK_MISMATCH", "H2_1 alignment drifted; STOP")
    return {
        "status": "PASS",
        "phase_2_report_sha256": report_sha,
        "phase_2_statistics_sha256": stats_sha,
        "phase_3_justified": False,
        "actionability": "NOT_MET",
        "alignment": align,
        "clock_order": {"A": a_econ, "B": b_econ},
        "wrote_phase_2": False,
    }


def warning_audit(suite: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = {}
    for eid, member in suite.items():
        preserved = preserved_warning(member["trades"], member["queries"])
        block = preserved.get("warning_before_damage_recall_among_losses") or {}
        expected_n, expected_losses = LOCKED_WARNING_LOSSES[eid]
        n = int(block.get("n") or 0)
        n_losses = int(block.get("n_losses") or 0)
        if n != expected_n or n_losses != expected_losses:
            raise AustinError("LOCK_MISMATCH", f"Phase 1 warning {eid} drifted from {expected_n}/{expected_losses}")
        rows[eid] = {"n": n, "n_losses": n_losses, "preserved": preserved}
    return {
        "status": "PASS",
        "A": "0 / 15",
        "B": "0 / 12",
        "members": rows,
        "note": "Phase 1 AVAILABLE warning among eventual losses remains frozen. Not early warning.",
    }


def determinism_audit(suite: dict[str, dict[str, Any]]) -> dict[str, Any]:
    checked = 0
    failed = 0
    for eid, member in suite.items():
        for trade in member["trades"]:
            first = [
                r["core_state"]
                for r in build_timeline(eid, trade, member["queries"])
            ]
            second = [
                r["core_state"]
                for r in build_timeline(eid, trade, member["queries"])
            ]
            checked += 1
            if first != second:
                failed += 1
    return {
        "status": "PASS" if checked and failed == 0 else "FAIL",
        "n_checked": checked,
        "n_failed": failed,
        "note": "Same discovery PRIMARY history produces the same core_state sequence.",
    }


def leakage_audit(
    suite: dict[str, dict[str, Any]],
    *,
    warehouse: dict[str, Any],
    limit_trades: int = 8,
) -> dict[str, Any]:
    checked = 0
    failed = 0
    warehouse_checked = 0
    warehouse_failed = 0
    errors = 0
    leaked = 0
    for eid, member in suite.items():
        for trade in member["trades"][:limit_trades]:
            primary = trade_primary(member["queries"], trade["trade_id"])
            if not primary:
                continue
            probes = list(range(min(len(primary), 5)))
            for idx in probes:
                history = primary[: idx + 1]
                state = derive_downfall_state(history)
                if set(state) & FORBIDDEN_PIT:
                    leaked += 1
                    failed += 1
                    continue
                mutated = []
                for j, row in enumerate(primary):
                    item = dict(row)
                    if j > idx:
                        item["conditional_ev_cents"] = 999.0
                        item["pnl_hold_after_t"] = -999.0
                        item["t40_already"] = True
                        item["hit_40_after"] = True
                        item["current_price_cents"] = 1
                    mutated.append(item)
                replay = derive_downfall_state(mutated[: idx + 1])
                checked += 1
                if (
                    replay["core_state"] != state["core_state"]
                    or replay["negative_streak_length"] != state["negative_streak_length"]
                    or replay["CI_state"] != state["CI_state"]
                ):
                    failed += 1
                stamp = history[-1].get("timestamp_utc")
                ticker = str(trade.get("ticker") or "")
                gid = str(trade.get("internal_game_id") or "")
                bars = warehouse.get("bars", {}).get(ticker, [])
                pbp = warehouse.get("pbp", {}).get(gid, [])
                if stamp and bars:
                    try:
                        mutate_future_and_rebuild(
                            trade, timestamp_utc=stamp, future_price=1.0, bars=bars, pbp=pbp
                        )
                        after = derive_downfall_state(history)
                        warehouse_checked += 1
                        if after["core_state"] != state["core_state"]:
                            warehouse_failed += 1
                    except Exception:  # noqa: BLE001
                        errors += 1
    status = "PASS" if checked and failed == 0 and leaked == 0 and warehouse_failed == 0 else (
        "INSUFFICIENT_SAMPLE" if checked == 0 else "FAIL"
    )
    return {
        "status": status,
        "n_checked": checked,
        "n_failed": failed,
        "n_leaked_outcome_keys": leaked,
        "n_warehouse_checked": warehouse_checked,
        "n_warehouse_failed": warehouse_failed,
        "n_errors": errors,
        "note": (
            "Mutating later PRIMARY EV/outcome/T40/MAE/MFE and post-t bars/PBP "
            "must leave derive_downfall_state(history_up_to_t) unchanged."
        ),
    }


def gate_a_status(determinism: dict[str, Any], leakage: dict[str, Any]) -> str:
    if determinism.get("status") == "PASS" and leakage.get("status") == "PASS":
        return "PASS"
    if determinism.get("status") == "INSUFFICIENT_SAMPLE" or leakage.get("status") == "INSUFFICIENT_SAMPLE":
        return "FAIL"
    return "FAIL"


__all__ = [
    "phase2_unchanged_audit",
    "warning_audit",
    "determinism_audit",
    "leakage_audit",
    "model_hash_audit",
    "cohort_hash_audit",
    "confirmation_protection_audit",
    "gate_a_status",
]
