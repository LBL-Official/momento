"""Phase 7 arm: freeze machinery, write empty append-only stores. No backfill."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from roller.austin.errors import AustinError
from roller.austin.experiments.downfall.schema import schema_hash, state_schema
from roller.austin.experiments.hazard.schema import hazard_schema, schema_hash as hazard_schema_hash
from roller.austin.experiments.ids import PHASE6_ID, PHASE7_ID, PHASE7_PHASE
from roller.austin.experiments.manifest import LOCKED_HASHES, LOCKED_MANIFEST_HASH, sha256_file, verify_model_manifest
from roller.austin.experiments.persistence.ids import LOCKED_CONFIRMATION_HASH
from roller.austin.experiments.persistence.load import confirmation_files_absent
from roller.austin.experiments.policy_v2.frozen import freeze_object_hash
from roller.austin.experiments.policy_v2.ids import HAZARD_SCHEMA_HASH, STATE_SCHEMA_HASH, EXPERIMENT_A, EXPERIMENT_B
from roller.austin.paths import confirmation_gate_dir, policy_phase5_dir, prospective_phase7_dir, repo_root
from roller.austin.store import load_json, write_json
from roller.choosin_texas.book import BOOK_ID, LIBRARY_RELATIVE

EVENT_COLUMNS = [
    "experiment_id",
    "trade_id",
    "internal_game_id",
    "event_id",
    "ticker",
    "observed_at",
    "period",
    "game_clock",
    "FIRST80_entry_timestamp",
    "entry_price",
    "Austin_EV",
    "CI_lower",
    "CI_upper",
    "support_state",
    "ESS",
    "distance",
    "core_downfall_state",
    "p_terminal_loss",
    "p_recovery_t1",
    "p_recovery_t2",
    "p_recovery_t3",
    "hazard_support_N",
    "current_yes_bid",
    "current_yes_ask",
    "price_travel",
    "score",
    "score_diff",
    "data_availability_status",
    "prediction_payload_hash",
]
OUTCOME_COLUMNS = [
    "trade_id",
    "internal_game_id",
    "settlement",
    "won",
    "terminal_pnl",
    "t40",
    "time_to_t40",
    "future_minimum_price",
    "future_maximum_price",
    "MAE",
    "MFE",
    "outcome_available_at",
]


def _empty_parquet(path, columns: list[str]) -> None:
    pd.DataFrame(columns=columns).to_parquet(path, index=False)


def stage_prospective() -> dict[str, Any]:
    phase5 = policy_phase5_dir()
    gate = confirmation_gate_dir()
    if (phase5 / "POLICY_FREEZE.json").is_file():
        raise AustinError("LOCK_MISMATCH", "Phase 7 refuses an executable policy freeze")
    finalized = load_json(phase5 / "PHASE5_FINALIZED.json")
    if finalized.get("human_selected_policy") != "NONE" or finalized.get("policy_frozen") is not False:
        raise AustinError("LOCK_MISMATCH", "Phase 7 requires Phase 5 NONE closeout")
    gate_manifest = load_json(gate / "MANIFEST.json")
    if gate_manifest.get("status") != "BLOCKED_NO_FROZEN_POLICY":
        raise AustinError("LOCK_MISMATCH", "Phase 6 gate is not BLOCKED_NO_FROZEN_POLICY")
    if confirmation_files_absent().get("status") != "PASS":
        raise AustinError("LOCK_MISMATCH", "confirmation result artifacts present")
    model = verify_model_manifest()
    if model.get("model_manifest_hash") != LOCKED_MANIFEST_HASH:
        raise AustinError("LOCK_MISMATCH", "Austin model hash drifted")
    if schema_hash(state_schema()) != STATE_SCHEMA_HASH:
        raise AustinError("LOCK_MISMATCH", "state schema drifted")
    if hazard_schema_hash(hazard_schema()) != HAZARD_SCHEMA_HASH:
        raise AustinError("LOCK_MISMATCH", "hazard schema drifted")
    book_path = repo_root() / LIBRARY_RELATIVE
    if not book_path.is_file():
        raise AustinError("DATA_REQUIRED", "registered 2026-27 book.json missing")
    book = load_json(book_path)
    if book.get("book_id") != BOOK_ID:
        raise AustinError("LOCK_MISMATCH", "Page 3 book_id drifted")
    if (book.get("registered") or {}).get("status") != "RESEARCH_REGISTERED":
        raise AustinError("LOCK_MISMATCH", "book is not RESEARCH_REGISTERED")
    if (book.get("registered") or {}).get("filters"):
        raise AustinError("LOCK_MISMATCH", "Page 3 book gained filters")
    book_hash = sha256_file(book_path)
    root = prospective_phase7_dir()
    root.mkdir(parents=True, exist_ok=True)
    if (root / "PROSPECTIVE_LOCK.json").is_file():
        current = load_json(root / "PROSPECTIVE_LOCK.json")
        if current.get("prospective_lock_hash") != freeze_object_hash(current):
            raise AustinError("LOCK_MISMATCH", "prospective lock hash drifted")
        return {
            "experiment_id": PHASE7_ID,
            "status": "ARMED_WAITING_FOR_DATA",
            "prospective_lock_hash": current["prospective_lock_hash"],
            "eligible_n": 0,
            "completed_n": 0,
            "policy_status": "NO_POLICY_FROZEN",
            "execution": "DISABLED",
            "lock_already_present": True,
        }
    lock_ts = datetime.now(timezone.utc).isoformat()
    lock = {
        "phase": "PHASE_7",
        "phase_id": PHASE7_PHASE,
        "experiment_id": PHASE7_ID,
        "prospective_lock_timestamp": lock_ts,
        "Austin_model": "austin_v2",
        "austin_manifest_hash": LOCKED_MANIFEST_HASH,
        "training_n_trades": 604,
        "training_n_snapshots": 48752,
        "K": 25,
        "state_schema_version": "downfall_state_v1",
        "state_schema_hash": STATE_SCHEMA_HASH,
        "hazard_schema_version": "loss_hazard_recovery_v1",
        "hazard_schema_hash": HAZARD_SCHEMA_HASH,
        "page3_strategy_id": BOOK_ID,
        "page3_book_hash": book_hash,
        "page3_status": "RESEARCH_REGISTERED",
        "observation_schedule": "EVERY_2_GAME_CLOCK_MINUTES",
        "reporting_checkpoints": [25, 50, 100, "season-end"],
        "scoring_definitions": {
            "ev": ["MAE", "RMSE", "sign_agreement", "spearman_ev_vs_hold_pnl"],
            "hazard": ["brier", "log_loss", "calibration", "roc_auc_if_both_classes", "pr_auc_if_defined"],
            "recovery": ["eligible_N", "recovery_N", "unavailable_N", "brier", "log_loss", "calibration"],
        },
        "no_ingest_at_arm": True,
        "no_historical_backfill": True,
        "austin_never_filters_entry": True,
        "policy_status": "NO_POLICY_FROZEN",
        "execution_enabled": False,
        "submits": False,
    }
    lock_hash = freeze_object_hash(lock)
    lock["prospective_lock_hash"] = lock_hash
    write_json(root / "PROSPECTIVE_LOCK.json", lock)
    reread = load_json(root / "PROSPECTIVE_LOCK.json")
    if freeze_object_hash(reread) != lock_hash:
        raise AustinError("LOCK_MISMATCH", "prospective lock read-back hash mismatch")
    manifest = {
        "phase": "PHASE_7",
        "experiment_id": PHASE7_ID,
        "prospective_lock_timestamp": lock_ts,
        "prospective_lock_hash": lock_hash,
        "Austin_model_hash": LOCKED_MANIFEST_HASH,
        "state_schema_hash": STATE_SCHEMA_HASH,
        "hazard_schema_hash": HAZARD_SCHEMA_HASH,
        "Page_3_strategy_identifier": BOOK_ID,
        "page3_book_hash": book_hash,
        "observation_schedule": "EVERY_2_GAME_CLOCK_MINUTES",
        "policy_status": "NO_POLICY_FROZEN",
        "confirmation_A_status": "SEALED_UNSPENT",
        "confirmation_B_status": "SEALED_UNSPENT",
        "source_phase6": PHASE6_ID,
        "execution_enabled": False,
        "submits": False,
        "collection_status": "ARMED_WAITING_FOR_DATA",
        "eligible_n": 0,
        "completed_n": 0,
    }
    write_json(root / "MANIFEST.json", manifest)
    _empty_parquet(root / "prospective_events.parquet", EVENT_COLUMNS)
    _empty_parquet(root / "prospective_outcomes.parquet", OUTCOME_COLUMNS)
    (root / "revision_log.jsonl").write_text("", encoding="utf-8")
    write_json(
        root / "collection_status.json",
        {
            "status": "ARMED_WAITING_FOR_DATA",
            "eligible_n": 0,
            "completed_n": 0,
            "note": "No eligible 2026-27 FIRST80 trades after the lock. No ingest. No backfill.",
        },
    )
    write_json(
        root / "model_lock_audit.json",
        {"status": "PASS", "austin_manifest_hash": LOCKED_MANIFEST_HASH, "hashes": LOCKED_HASHES, "ncaab_query_only": True},
    )
    write_json(root / "state_schema_audit.json", {"status": "PASS", "state_schema_hash": STATE_SCHEMA_HASH})
    write_json(root / "hazard_schema_audit.json", {"status": "PASS", "hazard_schema_hash": HAZARD_SCHEMA_HASH})
    write_json(
        root / "confirmation_preservation_audit.json",
        {
            "status": "PASS",
            "A": "SEALED_UNSPENT",
            "B": "SEALED_UNSPENT",
            "A_hash": LOCKED_CONFIRMATION_HASH[EXPERIMENT_A],
            "B_hash": LOCKED_CONFIRMATION_HASH[EXPERIMENT_B],
            "outcomes_accessed": False,
        },
    )
    write_json(
        root / "integrity_audit.json",
        {
            "status": "PASS",
            "append_only_events": True,
            "outcomes_separate": True,
            "no_backfill": True,
            "austin_never_filters_entry": True,
            "eligible_n": 0,
        },
    )
    write_json(
        root / "runtime_rules.json",
        {
            "events_before_lock": "INELIGIBLE_FOR_PHASE7",
            "austin_never_filters_first80_entry": True,
            "actions_forbidden": ["INTERVENE", "EXIT", "SELL", "HEDGE"],
            "predictions_hashed": True,
            "outcomes_live_in_separate_table": True,
            "revisions_require_explicit_record": True,
            "no_retrain": True,
            "no_threshold_shopping": True,
            "no_historical_backfill": True,
            "execution_enabled": False,
            "submits": False,
        },
    )
    (root / "REPORT.md").write_text(
        "\n".join(
            [
                "AUSTIN DRE",
                "PHASE 7 — PROSPECTIVE NBA 2026–27 VALIDATION",
                "",
                "PROSPECTIVE ONLY",
                "",
                "NO HISTORICAL BACKFILL",
                "",
                "MODEL FROZEN",
                "STATE MODEL FROZEN",
                "HAZARD MODEL FROZEN",
                "",
                "NO POLICY FROZEN",
                "",
                "CONFIRMATION SEALED",
                "",
                "EXECUTION DISABLED",
                "",
                "# 1. EXPERIMENT IDENTITY",
                "",
                f"{PHASE7_ID} / {PHASE7_PHASE}",
                "",
                "# 2. PROSPECTIVE LOCK",
                "",
                f"Timestamp {lock_ts}. Hash `{lock_hash}`.",
                "",
                "# 3. STRATEGY UNIVERSE",
                "",
                f"Page 3 `{BOOK_ID}` RESEARCH_REGISTERED 80/40 Q2 FIRST80 1 contract. No Austin entry filters.",
                "",
                "# 4. COLLECTION STATUS",
                "",
                "ARMED_WAITING_FOR_DATA",
                "",
                "# 5. ELIGIBLE TRADES",
                "",
                "0. No ingest at arm. Events before the lock are INELIGIBLE_FOR_PHASE7.",
                "",
                "# 6. PIT PREDICTIONS",
                "",
                "Empty append-only prospective_events.parquet.",
                "",
                "# 7. MODEL AVAILABILITY",
                "",
                "Austin v2 / downfall_state_v1 / loss_hazard_recovery_v1 frozen.",
                "",
                "# 8. STATE DISTRIBUTION",
                "",
                "No scoring yet. Prospective collection only.",
                "",
                "# 9. HAZARD DISTRIBUTION",
                "",
                "No scoring yet. Prospective collection only.",
                "",
                "# 10. COMPLETED OUTCOMES",
                "",
                "0. prospective_outcomes.parquet is empty and separate.",
                "",
                "# 11. AUSTIN EV SCORING",
                "",
                "No scoring yet. Prospective collection only.",
                "",
                "# 12. STATE ECONOMICS",
                "",
                "No scoring yet. Prospective collection only.",
                "",
                "# 13. TERMINAL LOSS CALIBRATION",
                "",
                "No scoring yet. Prospective collection only.",
                "",
                "# 14. RECOVERY CALIBRATION",
                "",
                "No scoring yet. Prospective collection only.",
                "",
                "# 15. WARNING / TIMING",
                "",
                "No scoring yet. Prospective collection only.",
                "",
                "# 16. MISSINGNESS",
                "",
                "Unavailable recovery is never coerced to false.",
                "",
                "# 17. INTEGRITY",
                "",
                "Append-only events. Explicit revision_log.jsonl. Confirmation remains SEALED_UNSPENT.",
                "",
                "# 18. WHAT THE DATA SHOWS",
                "",
                "The harness is armed. No prospective FIRST80 has occurred after the lock.",
                "",
                "# 19. WHAT HAS NOT BEEN PROVEN",
                "",
                "No prospective EV, state, hazard, recovery, or timing result exists.",
                "",
                "# 20. WHETHER PHASE 8 IS JUSTIFIED",
                "",
                "PHASE 8 NOT YET JUSTIFIED BY OUTCOMES.",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if sha256_file(book_path) != book_hash:
        raise AustinError("LOCK_MISMATCH", "book.json changed during Phase 7 arm")
    return {
        "experiment_id": PHASE7_ID,
        "status": "ARMED_WAITING_FOR_DATA",
        "prospective_lock_hash": lock_hash,
        "eligible_n": 0,
        "completed_n": 0,
        "policy_status": "NO_POLICY_FROZEN",
        "execution": "DISABLED",
        "page3_book_hash": book_hash,
    }
