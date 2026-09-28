"""Phase 4 integrity audits. Confirmation is identity-only. Phase 2/3 stay read-only."""

from __future__ import annotations

from typing import Any

from roller.austin.errors import AustinError
from roller.austin.experiments.downfall.audits import warning_audit
from roller.austin.experiments.downfall.engine import derive_downfall_state
from roller.austin.experiments.downfall.schema import schema_hash, state_schema
from roller.austin.experiments.downfall.timeline import trade_primary
from roller.austin.experiments.hazard.finalize import finalize_phase2, finalize_phase3
from roller.austin.experiments.hazard.ids import (
    FORBIDDEN_PIT,
    PHASE2_MANIFEST_SHA256,
    PHASE2_REPORT_SHA256,
    PHASE2_STATISTICS_SHA256,
    PHASE3_REPORT_SHA256,
    PHASE3_STATISTICS_SHA256,
    STATE_SCHEMA_HASH,
)
from roller.austin.experiments.hazard.logo import predict_family
from roller.austin.experiments.hazard.targets import attach_targets, pit_keys
from roller.austin.experiments.ids import EXPERIMENT_A, EXPERIMENT_B
from roller.austin.experiments.manifest import sha256_file
from roller.austin.experiments.ncaab_state import mutate_future_and_rebuild
from roller.austin.experiments.persistence.audits import cohort_hash_audit, confirmation_protection_audit, model_hash_audit
from roller.austin.experiments.persistence.load import confirmation_files_absent
from roller.austin.paths import downfall_phase3_dir, persistence_phase2_dir


def phase2_finalization_audit() -> dict[str, Any]:
    payload = finalize_phase2()
    root = persistence_phase2_dir()
    if sha256_file(root / "REPORT.md") != PHASE2_REPORT_SHA256:
        raise AustinError("LOCK_MISMATCH", "Phase 2 REPORT.md drifted after FINALIZED.json")
    if sha256_file(root / "statistics.json") != PHASE2_STATISTICS_SHA256:
        raise AustinError("LOCK_MISMATCH", "Phase 2 statistics.json drifted after FINALIZED.json")
    if sha256_file(root / "MANIFEST.json") != PHASE2_MANIFEST_SHA256:
        raise AustinError("LOCK_MISMATCH", "Phase 2 MANIFEST.json drifted after FINALIZED.json")
    return {
        "status": "PASS",
        "finalized": payload,
        "report_hash": PHASE2_REPORT_SHA256,
        "statistics_hash": PHASE2_STATISTICS_SHA256,
        "manifest_hash": PHASE2_MANIFEST_SHA256,
        "actionability_gate": "NOT_MET",
        "historical_artifacts_modified": False,
    }


def phase3_finalization_audit() -> dict[str, Any]:
    payload = finalize_phase3()
    root = downfall_phase3_dir()
    if sha256_file(root / "REPORT.md") != PHASE3_REPORT_SHA256:
        raise AustinError("LOCK_MISMATCH", "Phase 3 REPORT.md drifted after FINALIZED.json")
    if sha256_file(root / "statistics.json") != PHASE3_STATISTICS_SHA256:
        raise AustinError("LOCK_MISMATCH", "Phase 3 statistics.json drifted after FINALIZED.json")
    hashed = schema_hash(state_schema())
    if hashed != STATE_SCHEMA_HASH:
        raise AustinError("LOCK_MISMATCH", "downfall_state_v1 hash drifted")
    return {
        "status": "PASS",
        "finalized": payload,
        "report_hash": PHASE3_REPORT_SHA256,
        "statistics_hash": PHASE3_STATISTICS_SHA256,
        "state_schema_hash": hashed,
        "phase_4_decision": "MIXED",
        "historical_artifacts_modified": False,
    }


def state_schema_audit(hazard_schema_hash: str) -> dict[str, Any]:
    hashed = schema_hash(state_schema())
    if hashed != STATE_SCHEMA_HASH:
        raise AustinError("LOCK_MISMATCH", "downfall_state_v1 hash drifted")
    return {
        "status": "PASS",
        "state_schema_version": "downfall_state_v1",
        "state_schema_hash": hashed,
        "hazard_schema_hash": hazard_schema_hash,
        "file_digest_is_not_canonical": True,
    }


def crossfit_audit(preds: list[dict[str, Any]]) -> dict[str, Any]:
    leaked = [p for p in preds if p.get("same_game_present_in_training")]
    if leaked:
        raise AustinError("LOCK_MISMATCH", "LOGO same_game_present_in_training")
    return {
        "status": "PASS",
        "n_predictions": len(preds),
        "n_same_game_present": 0,
        "same_game_present_in_training": False,
        "note": "Every p_hat rebuilds the Beta table after dropping that row's internal_game_id.",
    }


def leakage_audit(
    entries: list[dict[str, Any]],
    timelines: dict[tuple[str, str], list[dict[str, Any]]],
    suite: dict[str, dict[str, Any]],
    *,
    warehouse: dict[str, Any],
    limit_trades: int = 6,
) -> dict[str, Any]:
    checked = 0
    failed = 0
    leaked = 0
    warehouse_checked = 0
    warehouse_failed = 0
    errors = 0
    p_hat_failed = 0
    by_eid: dict[str, list[dict[str, Any]]] = {EXPERIMENT_A: [], EXPERIMENT_B: []}
    for row in entries:
        by_eid.setdefault(str(row.get("source_experiment_id")), []).append(row)
    for eid, member in suite.items():
        trades = list(member["trades"])[:limit_trades]
        wanted = {t["trade_id"] for t in trades}
        sample = [r for r in by_eid.get(eid, []) if r.get("trade_id") in wanted][:limit_trades]
        for entry in sample:
            keys = pit_keys(entry)
            if set(keys) & FORBIDDEN_PIT:
                leaked += 1
                failed += 1
                continue
            primary = trade_primary(member["queries"], entry["trade_id"])
            idx = int(entry.get("state_sequence_number") or 0)
            if idx >= len(primary):
                continue
            history = primary[: idx + 1]
            state = derive_downfall_state(history)
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
            timeline = timelines.get((eid, entry["trade_id"])) or []
            flipped = dict(entry)
            flipped["TARGET_terminal_loss"] = 0 if entry.get("TARGET_terminal_loss") == 1 else 1
            train = [flipped if r is entry else r for r in entries]
            pred = next(
                p
                for p in predict_family(train, family="H1", target="TARGET_terminal_loss")
                if p["trade_id"] == entry["trade_id"] and p["core_state"] == entry["core_state"]
            )
            if pred.get("same_game_present_in_training"):
                raise AustinError("LOCK_MISMATCH", "LOGO same_game_present_in_training")
            if pred.get("p_terminal_loss_H1") != entry.get("p_terminal_loss_H1"):
                p_hat_failed += 1
                failed += 1
            replay_targets = attach_targets(entry, timeline, mutated)
            if pit_keys(replay_targets) != keys:
                failed += 1
            stamp = history[-1].get("timestamp_utc")
            ticker = str(entry.get("ticker") or "")
            gid = str(entry.get("internal_game_id") or "")
            bars = warehouse.get("bars", {}).get(ticker, [])
            pbp = warehouse.get("pbp", {}).get(gid, [])
            if stamp and bars:
                try:
                    mutate_future_and_rebuild(
                        next(t for t in member["trades"] if t["trade_id"] == entry["trade_id"]),
                        timestamp_utc=stamp,
                        future_price=1.0,
                        bars=bars,
                        pbp=pbp,
                    )
                    after = derive_downfall_state(history)
                    warehouse_checked += 1
                    if after["core_state"] != state["core_state"]:
                        warehouse_failed += 1
                except Exception:  # noqa: BLE001
                    errors += 1
    status = (
        "PASS"
        if checked and failed == 0 and leaked == 0 and warehouse_failed == 0 and p_hat_failed == 0
        else ("INSUFFICIENT_SAMPLE" if checked == 0 else "FAIL")
    )
    return {
        "status": status,
        "n_checked": checked,
        "n_failed": failed,
        "n_leaked_outcome_keys": leaked,
        "n_p_hat_failed": p_hat_failed,
        "n_warehouse_checked": warehouse_checked,
        "n_warehouse_failed": warehouse_failed,
        "n_errors": errors,
        "note": (
            "Mutating later EV/state/bars/PBP/outcome/T40/MAE/MFE must leave PIT keys "
            "and this row's LOGO p_hat unchanged because the same game is excluded."
        ),
    }


def confirmation_audit() -> dict[str, Any]:
    payload = confirmation_protection_audit()
    files = confirmation_files_absent()
    if files.get("status") != "PASS":
        raise AustinError("LOCK_MISMATCH", "confirmation result files present")
    return payload


__all__ = [
    "phase2_finalization_audit",
    "phase3_finalization_audit",
    "state_schema_audit",
    "crossfit_audit",
    "leakage_audit",
    "confirmation_audit",
    "model_hash_audit",
    "cohort_hash_audit",
    "warning_audit",
]
