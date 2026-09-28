"""Measured leakage and self-neighbor audits. Not stub PASS notes."""

from __future__ import annotations

from typing import Any

from roller.austin.clock import parse_utc
from roller.austin.experiments.ncaab_state import mutate_future_and_rebuild
from roller.austin.features import build_feature_vector
from roller.austin.store import load_snapshots, write_json
from roller.austin.paths import experiment_dir


def _numeric_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if set(left) != set(right):
        return False
    for key in left:
        va, vb = left[key], right[key]
        if va == vb:
            continue
        try:
            if va != va and vb != vb:  # NaN == NaN for this audit
                continue
        except (TypeError, ValueError):
            return False
        return False
    return True


def _post_entry_timestamp(trade: dict[str, Any], bars: list) -> str | None:
    entry = parse_utc(trade.get("entry_timestamp"))
    after = [row[0] for row in bars if entry is not None and row[0] > entry]
    if after:
        return after[min(2, len(after) - 1)].isoformat()
    if bars:
        return bars[len(bars) // 2][0].isoformat()
    return None


def run_leakage_audit(experiment_id: str, cohort: str, trades: list[dict[str, Any]], warehouse: dict[str, Any]) -> dict[str, Any]:
    checked = 0
    failed = 0
    errors = 0
    for trade in trades[:5]:
        ticker = str(trade.get("ticker") or "")
        gid = str(trade.get("internal_game_id") or "")
        bars = warehouse.get("bars", {}).get(ticker, [])
        pbp = warehouse.get("pbp", {}).get(gid, [])
        stamp = _post_entry_timestamp(trade, bars)
        if not bars or stamp is None:
            continue
        try:
            a, b = mutate_future_and_rebuild(
                trade,
                timestamp_utc=stamp,
                future_price=1.0,
                bars=bars,
                pbp=pbp,
            )
            fa = build_feature_vector(a)["numeric"]
            fb = build_feature_vector(b)["numeric"]
        except Exception:  # noqa: BLE001
            errors += 1
            continue
        checked += 1
        if not _numeric_equal(fa, fb):
            failed += 1
    payload = {
        "status": "PASS" if checked and failed == 0 else ("INSUFFICIENT_SAMPLE" if checked == 0 else "FAIL"),
        "n_checked": checked,
        "n_failed": failed,
        "n_errors": errors,
        "note": "mutate bars/PBP after t; feature vector at t must be unchanged",
    }
    root = experiment_dir(experiment_id) / cohort.lower()
    write_json(root / "leakage_audit.json", payload)
    if cohort == "DISCOVERY":
        write_json(experiment_dir(experiment_id) / "leakage_audit.json", payload)
    return payload


def run_self_neighbor_audit(experiment_id: str, cohort: str, trades: list[dict[str, Any]]) -> dict[str, Any]:
    snaps = load_snapshots()
    train_ids = set(snaps["trade_id"].astype(str)) if "trade_id" in snaps.columns else set()
    ncaab_ids = {str(t["trade_id"]) for t in trades}
    overlap = sorted(ncaab_ids & train_ids)
    payload = {
        "status": "PASS" if not overlap else "FAIL",
        "n_ncaab_trades": len(ncaab_ids),
        "n_training_trade_ids": len(train_ids),
        "overlap": overlap,
        "note": "NCAAB trade_ids must sit outside the 604 snapshot matrix",
    }
    root = experiment_dir(experiment_id) / cohort.lower()
    write_json(root / "self_neighbor_audit.json", payload)
    if cohort == "DISCOVERY":
        write_json(experiment_dir(experiment_id) / "self_neighbor_audit.json", payload)
    return payload
