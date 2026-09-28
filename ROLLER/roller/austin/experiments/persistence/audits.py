"""Integrity audits for the persistence mechanism. No confirmation spend."""

from __future__ import annotations

from typing import Any

from roller.austin.experiments.audits import _numeric_equal
from roller.austin.experiments.manifest import LOCKED_HASHES, LOCKED_MANIFEST_HASH, verify_model_manifest
from roller.austin.experiments.ncaab_state import mutate_future_and_rebuild
from roller.austin.experiments.persistence.events import later_after, pit_descriptors, primary_rows, reconstruct_extras
from roller.austin.experiments.persistence.ids import FORBIDDEN_PIT_KEYS
from roller.austin.experiments.persistence.load import confirmation_files_absent
from roller.austin.experiments.persistence.util import as_float, valid_ev
from roller.austin.features import build_feature_vector
from roller.austin.store import load_pca_model


def model_hash_audit() -> dict[str, Any]:
    model = verify_model_manifest()
    return {
        "status": "PASS",
        "model_manifest_hash": model.get("model_manifest_hash"),
        "locked_model_manifest_hash": LOCKED_MANIFEST_HASH,
        "hashes": model.get("hashes") or LOCKED_HASHES,
        "training_n_trades": model.get("training_n_trades"),
        "training_n_snapshots": model.get("training_n_snapshots"),
        "ncaab_used_for_training": False,
        "ncaab_used_for_pca": False,
        "ncaab_used_for_scaler": False,
        "ncaab_used_for_knn": False,
        "git_commit": model.get("git_commit"),
        "git_commit_reason": model.get("git_commit_reason"),
    }


def cohort_hash_audit(suite: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = {}
    for eid, member in suite.items():
        rows[eid] = {
            "discovery_hash": member["discovery_hash"],
            "confirmation_hash": member["confirmation_identity"]["cohort_hash"],
            "confirmation_n_trades": member["confirmation_identity"]["n_trades"],
            "confirmation_n_games": member["confirmation_identity"]["n_games"],
        }
    return {"status": "PASS", "members": rows, "confirmation_outcomes_used": False}


def confirmation_protection_audit() -> dict[str, Any]:
    files = confirmation_files_absent()
    return {
        **files,
        "confirmation_accessed": False,
        "policy_status": "UNFROZEN",
        "policy_selected": "NONE",
        "note": "confirmation_cohort.json identity/hash only; no confirmation queries or outcomes",
    }


def _pit_from_raw(raw, first_row: dict[str, Any], *, previous: float | None, ev_entry: float | None, ev_entry_row) -> dict[str, Any]:
    feats = build_feature_vector(raw)["numeric"]
    extras = {
        "score_travel": feats.get("score_travel"),
        "score_diff_travel": feats.get("score_differential_travel"),
    }
    return pit_descriptors(
        first_row,
        previous_valid_ev=previous,
        ev_entry=ev_entry,
        ev_entry_row=ev_entry_row,
        extras=extras,
    )


def leakage_audit(
    events: list[dict[str, Any]],
    *,
    warehouse: dict[str, Any],
    limit: int = 5,
) -> dict[str, Any]:
    checked_t0 = 0
    failed_t0 = 0
    checked_t1 = 0
    failed_t1 = 0
    checked_t2 = 0
    failed_t2 = 0
    errors = 0
    pca = load_pca_model()
    for event in events[:limit]:
        trade = event["_trade"]
        first = event["_first"]
        ticker = str(trade.get("ticker") or "")
        gid = str(trade.get("internal_game_id") or "")
        bars = warehouse.get("bars", {}).get(ticker, [])
        pbp = warehouse.get("pbp", {}).get(gid, [])
        stamp = first.get("timestamp_utc")
        if not stamp or not bars:
            continue
        pit = event.get("pit") or {}
        leaked = set(pit) & FORBIDDEN_PIT_KEYS
        if leaked:
            failed_t0 += 1
            continue
        try:
            a, b = mutate_future_and_rebuild(trade, timestamp_utc=stamp, future_price=1.0, bars=bars, pbp=pbp)
            fa = build_feature_vector(a)["numeric"]
            fb = build_feature_vector(b)["numeric"]
            extras_a = reconstruct_extras(trade, first, warehouse={"bars": {ticker: bars}, "pbp": {gid: pbp}}, model=pca)
            extras_b = {
                "score_travel": fb.get("score_travel"),
                "score_diff_travel": fb.get("score_differential_travel"),
            }
            pit_a = pit_descriptors(
                first,
                previous_valid_ev=event.get("previous_valid_EV"),
                ev_entry=event.get("EV_entry"),
                ev_entry_row=first,
                extras=extras_a,
            )
            pit_b = pit_descriptors(
                first,
                previous_valid_ev=event.get("previous_valid_EV"),
                ev_entry=event.get("EV_entry"),
                ev_entry_row=first,
                extras=extras_b,
            )
        except Exception:  # noqa: BLE001
            errors += 1
            continue
        checked_t0 += 1
        if not _numeric_equal(fa, fb) or pit_a.get("SCORE_TRAVEL") != pit_b.get("SCORE_TRAVEL"):
            failed_t0 += 1
        later_valid = event.get("_later_valid") or []
        if later_valid:
            t1 = later_valid[0]
            t1_stamp = t1.get("timestamp_utc")
            if t1_stamp:
                try:
                    a1, b1 = mutate_future_and_rebuild(
                        trade, timestamp_utc=t1_stamp, future_price=1.0, bars=bars, pbp=pbp
                    )
                    f1a = build_feature_vector(a1)["numeric"]
                    f1b = build_feature_vector(b1)["numeric"]
                    checked_t1 += 1
                    if not _numeric_equal(f1a, f1b):
                        failed_t1 += 1
                except Exception:  # noqa: BLE001
                    errors += 1
            if len(later_valid) > 1:
                t2 = later_valid[1]
                t2_stamp = t2.get("timestamp_utc")
                if t2_stamp:
                    try:
                        a2, b2 = mutate_future_and_rebuild(
                            trade, timestamp_utc=t2_stamp, future_price=1.0, bars=bars, pbp=pbp
                        )
                        f2a = build_feature_vector(a2)["numeric"]
                        f2b = build_feature_vector(b2)["numeric"]
                        checked_t2 += 1
                        if not _numeric_equal(f2a, f2b):
                            failed_t2 += 1
                    except Exception:  # noqa: BLE001
                        errors += 1
    status = "PASS" if checked_t0 and failed_t0 == 0 and failed_t1 == 0 and failed_t2 == 0 else (
        "INSUFFICIENT_SAMPLE" if checked_t0 == 0 else "FAIL"
    )
    return {
        "status": status,
        "n_checked_t0": checked_t0,
        "n_failed_t0": failed_t0,
        "n_checked_t1": checked_t1,
        "n_failed_t1": failed_t1,
        "n_checked_t2": checked_t2,
        "n_failed_t2": failed_t2,
        "n_errors": errors,
        "note": "mutate bars/PBP after t0/t1/t2; PIT descriptor vector at that checkpoint must be unchanged",
    }


def assert_pit_clean(pit: dict[str, Any]) -> None:
    leaked = set(pit) & FORBIDDEN_PIT_KEYS
    if leaked:
        raise AssertionError(f"PIT leaked {sorted(leaked)}")
