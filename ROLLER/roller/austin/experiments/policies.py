"""Pre-registered policy family. No threshold hunting. No HOLD/SELL words."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from roller.austin.errors import AustinError
from roller.austin.experiments.ids import DETERIORATION_X_CENTS, SUITE_ID
from roller.austin.paths import experiment_dir, suite_freeze_path
from roller.austin.store import load_json

POLICY_FAMILY: dict[str, dict[str, Any]] = {
    "POLICY_A": {"policy_id": "POLICY_A", "kind": "ev_lt", "threshold_cents": 0.0, "ci": None},
    "POLICY_B": {"policy_id": "POLICY_B", "kind": "ev_lt", "threshold_cents": 2.0, "ci": None},
    "POLICY_C": {"policy_id": "POLICY_C", "kind": "ev_lt", "threshold_cents": 5.0, "ci": None},
    "POLICY_D": {
        "policy_id": "POLICY_D",
        "kind": "deterioration",
        "threshold_cents": DETERIORATION_X_CENTS,
        "ci": None,
    },
    "POLICY_E": {"policy_id": "POLICY_E", "kind": "ev_lt", "threshold_cents": 0.0, "ci": "upper_below_zero"},
    "POLICY_F": {"policy_id": "POLICY_F", "kind": "ev_lt", "threshold_cents": 0.0, "ci": "crosses_zero"},
}


def canonical_definition(policy_id: str) -> str:
    row = POLICY_FAMILY[policy_id]
    if row["kind"] == "deterioration":
        return f"EV − EV_entry ≤ −{int(row['threshold_cents'])}¢"
    base = f"EV < {row['threshold_cents']:+.0f}¢".replace("< +", "< +").replace("< +0", "< 0")
    if row["threshold_cents"] == 0:
        base = "EV < 0¢"
    elif row["threshold_cents"] == 2:
        base = "EV < +2¢"
    elif row["threshold_cents"] == 5:
        base = "EV < +5¢"
    if row["ci"] == "upper_below_zero":
        return f"{base} AND upper 95% CI < 0¢"
    if row["ci"] == "crosses_zero":
        return f"{base} AND CI crosses 0"
    return base


def policy_hash(policy_id: str) -> str:
    payload = {**POLICY_FAMILY[policy_id], "definition": canonical_definition(policy_id)}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def assert_policy_id(policy_id: str) -> str:
    text = str(policy_id or "").strip()
    if text not in POLICY_FAMILY:
        raise AustinError("QUERY_REJECTED", f"policy {text} is not pre-registered")
    return text


def decide(
    policy_id: str,
    *,
    ev: float | None,
    ci_lower: float | None,
    ci_upper: float | None,
    ev_entry: float | None,
    primary: bool,
) -> str:
    if not primary:
        return "NONE"
    if ev is None:
        return "NONE"
    spec = POLICY_FAMILY[assert_policy_id(policy_id)]
    if spec["kind"] == "deterioration":
        if ev_entry is None:
            return "NONE"
        return "INTERVENE" if float(ev) - float(ev_entry) <= -float(spec["threshold_cents"]) else "NONE"
    if float(ev) >= float(spec["threshold_cents"]):
        return "NONE"
    if spec["ci"] == "upper_below_zero":
        if ci_upper is None or float(ci_upper) >= 0:
            return "NONE"
    if spec["ci"] == "crosses_zero":
        if ci_lower is None or ci_upper is None:
            return "NONE"
        if not (float(ci_lower) < 0 < float(ci_upper)):
            return "NONE"
    return "INTERVENE"


def assign_ev_entry(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """First valid PRIMARY_GRID EV becomes immutable EV_entry."""
    by_trade: dict[str, float | None] = {}
    out = []
    for row in rows:
        tid = row["trade_id"]
        ev = row.get("conditional_ev_cents")
        primary = bool(row.get("primary"))
        available = row.get("availability_status") == "VALUE" and ev is not None
        if tid not in by_trade:
            by_trade[tid] = None
        if by_trade[tid] is None and primary and available:
            by_trade[tid] = float(ev)
        entry = by_trade[tid]
        now = float(ev) if ev is not None else None
        out.append(
            {
                **row,
                "ev_at_entry": entry,
                "ev_now": now,
                "ev_change": None if entry is None or now is None else now - entry,
            }
        )
    return out


def refuse_auto_policy(_stats: dict[str, Any] | None = None) -> None:
    """Agent / CLI must not infer a POLICY_* winner. Human freeze only."""
    raise AustinError("QUERY_REJECTED", "agent path cannot auto-pick a policy; POLICY STATUS stays UNFROZEN")


def confirmation_artifacts_exist() -> bool:
    names = (
        "confirmation_state_queries.csv",
        "confirmation_policy_ledger.csv",
        "confirmation_statistics.json",
    )
    for experiment_id in ("NCAAB_H1_2_AUSTIN_TRANSFER_V1", "NCAAB_H2_1_AUSTIN_TRANSFER_V1"):
        root = experiment_dir(experiment_id)
        if (root / "confirmation" / "state_queries.csv").is_file():
            return True
        if (root / "confirmation" / "policy_ledger.csv").is_file():
            return True
        if (root / "confirmation" / "statistics.json").is_file():
            return True
        if any((root / name).is_file() for name in names):
            return True
    return False


def load_suite_freeze() -> dict[str, Any]:
    path = suite_freeze_path()
    payload = load_json(path)
    if payload.get("suite_id") != SUITE_ID:
        raise AustinError("LOCK_MISMATCH", "POLICY_FREEZE suite_id mismatch")
    if payload.get("confirmation_read") is True:
        raise AustinError("LOCK_MISMATCH", "POLICY_FREEZE confirmation_read=true")
    return payload
