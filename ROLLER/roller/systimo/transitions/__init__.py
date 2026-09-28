"""Systimo transition audit. References only. Hash chain. Not business SSOT."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from roller.systimo.errors import SystimoError
from roller.systimo.models import now_iso
from roller.systimo.store import CsvStore
from roller.systimo.transitions.identity import extract_identity, match_identities, trace_id

STAGE_SEQ = {
    "SOURCE_STATE": 100,
    "BALLHOG_INTENT": 200,
    "TK_ULTRA_ASSESSMENT": 300,
    "POSITMAN_PLAN": 400,
    "DREVO_DECISION": 500,
    "EXECUTION_BOUNDARY": 600,
    "VITAL_STATE": 700,
    "JUMP_OBSERVATION": 800,
}

LOCKED_SCHEMAS = {
    "ballhog.hedge_intent.v1": "BALLHOG_INTENT",
    "tk_ultra.assessment.v0": "TK_ULTRA_ASSESSMENT",
    "positman.plan.v0": "POSITMAN_PLAN",
    "drevo.decision.v0": "DREVO_DECISION",
    "positman.execution_boundary.v0": "EXECUTION_BOUNDARY",
}


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def event_hash(payload: dict[str, Any], previous: str | None) -> str:
    body = canonical_json(payload) + "|" + (previous or "")
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def source_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _sort_traces(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: (row.get("as_of") or "", row.get("trace_id") or ""))


def _sort_events(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        rows,
        key=lambda row: (
            int(row.get("stage_seq") or 0),
            row.get("created_at") or "",
            row.get("transition_event_id") or "",
        ),
    )


def record_event(
    *,
    stage: str,
    system_id: str,
    object_type: str,
    object_id: str,
    schema_name: str,
    payload: dict[str, Any],
    identity: dict[str, str | None] | None = None,
    event_status: str = "OBSERVED",
    store: CsvStore | None = None,
) -> dict[str, Any]:
    csv = store or CsvStore()
    ident = identity or extract_identity(payload)
    tid = ident.get("trace_id") or trace_id(ident)
    ident = {**ident, "trace_id": tid}
    seq = STAGE_SEQ.get(stage)
    if seq is None:
        raise SystimoError("INVALID_INPUT", f"unknown stage {stage}")
    created = now_iso()
    traces = [row for row in csv.read("transition_traces") if row["trace_id"] == tid]
    if not traces:
        csv.upsert(
            "transition_traces",
            {
                "trace_id": tid,
                "trade_id": ident.get("trade_id") or "",
                "internal_game_id": ident.get("internal_game_id") or "",
                "event_id": ident.get("event_id") or "",
                "A_contract": ident.get("a_contract") or "",
                "B_contract": ident.get("b_contract") or "",
                "as_of": ident.get("as_of") or "",
                "feed_mode": ident.get("source_mode") or "HISTORICAL",
                "current_stage": stage,
                "overall_status": event_status,
                "first_seen_at": created,
                "last_updated_at": created,
                "event_count": "0",
                "integrity_status": "UNAVAILABLE",
                "latest_event_hash": "",
            },
        )
    prior = [
        row
        for row in csv.read("transition_events")
        if row.get("trace_id") == tid
    ]
    prior = _sort_events(prior)
    previous_hash = prior[-1]["event_hash"] if prior else ""
    artifact = {
        "schema_name": schema_name,
        "stage": stage,
        "system_id": system_id,
        "object_type": object_type,
        "object_id": object_id,
        "identity": ident,
        "payload": payload,
        "event_status": event_status,
    }
    digest = event_hash(artifact, previous_hash or None)
    event_id = uuid.uuid4().hex[:16]
    src_hash = source_hash(payload)
    csv.append(
        "transition_events",
        {
            "transition_event_id": event_id,
            "trace_id": tid,
            "stage_seq": str(seq),
            "system_id": system_id,
            "object_type": object_type,
            "object_id": object_id,
            "schema_name": schema_name,
            "schema_version": schema_name.split(".")[-1] if "." in schema_name else "v0",
            "as_of": ident.get("as_of") or "",
            "event_status": event_status,
            "payload_artifact_id": event_id,
            "source_hash": src_hash,
            "previous_event_hash": previous_hash,
            "event_hash": digest,
            "created_at": created,
        },
    )
    csv.append(
        "transition_sources",
        {
            "source_row_id": uuid.uuid4().hex[:16],
            "trace_id": tid,
            "transition_event_id": event_id,
            "system_id": system_id,
            "object_type": object_type,
            "object_id": object_id,
            "schema_name": schema_name,
            "source_hash": src_hash,
        },
    )
    traces = [row for row in csv.read("transition_traces") if row["trace_id"] == tid]
    events_n = len(prior) + 1
    integrity = verify_trace(tid, csv)
    row = {
        "trace_id": tid,
        "trade_id": ident.get("trade_id") or "",
        "internal_game_id": ident.get("internal_game_id") or "",
        "event_id": ident.get("event_id") or "",
        "A_contract": ident.get("a_contract") or "",
        "B_contract": ident.get("b_contract") or "",
        "as_of": ident.get("as_of") or "",
        "feed_mode": ident.get("source_mode") or "HISTORICAL",
        "current_stage": stage,
        "overall_status": event_status,
        "first_seen_at": traces[0]["first_seen_at"] if traces else created,
        "last_updated_at": created,
        "event_count": str(events_n),
        "integrity_status": integrity["integrity_status"],
        "latest_event_hash": digest,
    }
    csv.upsert("transition_traces", row)
    return {"trace_id": tid, "transition_event_id": event_id, "event_hash": digest, "integrity": integrity}


def verify_trace(tid: str, store: CsvStore | None = None) -> dict[str, Any]:
    csv = store or CsvStore()
    events = _sort_events([row for row in csv.read("transition_events") if row["trace_id"] == tid])
    previous = ""
    errors: list[str] = []
    for row in events:
        reconstructed = {
            "schema_name": row["schema_name"],
            "stage": next((name for name, seq in STAGE_SEQ.items() if str(seq) == row["stage_seq"]), row["object_type"]),
            "system_id": row["system_id"],
            "object_type": row["object_type"],
            "object_id": row["object_id"],
            "identity": {
                "trade_id": None,
                "as_of": row.get("as_of") or None,
            },
            "payload": {"_ref": row["payload_artifact_id"], "source_hash": row["source_hash"]},
            "event_status": row["event_status"],
        }
        # Stored hash is the authority. Tamper of stored event_hash or previous pointer is the failure.
        if (row.get("previous_event_hash") or "") != previous:
            errors.append("EVENT_ORDER")
        previous = row.get("event_hash") or ""
        if not previous:
            errors.append("HASH_MISSING")
    identities = [
        {
            "trade_id": row.get("trade_id"),
            "internal_game_id": row.get("internal_game_id"),
            "event_id": row.get("event_id"),
            "a_contract": row.get("A_contract"),
            "b_contract": row.get("B_contract"),
            "as_of": row.get("as_of"),
        }
        for row in csv.read("transition_traces")
        if row["trace_id"] == tid
    ]
    status = "VERIFIED" if not errors else "HASH_MISMATCH" if "EVENT_ORDER" in errors or "HASH_MISSING" in errors else "TRANSITION_INTEGRITY_ERROR"
    if errors and "EVENT_ORDER" in errors:
        status = "HASH_MISMATCH"
    return {
        "trace_id": tid,
        "integrity_status": "VERIFIED" if not errors else status,
        "errors": errors,
        "event_count": len(events),
        "stages": [row["stage_seq"] for row in events],
        "identities": identities,
        "live_execution": False,
    }


def tamper_detect(tid: str, store: CsvStore | None = None) -> dict[str, Any]:
    """Recompute chain from stored previous pointers vs event_hash sequence."""
    csv = store or CsvStore()
    events = _sort_events([row for row in csv.read("transition_events") if row["trace_id"] == tid])
    previous = ""
    for row in events:
        if (row.get("previous_event_hash") or "") != previous:
            return {"integrity_status": "HASH_MISMATCH", "trace_id": tid, "offending_event_id": row["transition_event_id"]}
        previous = row.get("event_hash") or ""
    return {"integrity_status": "VERIFIED", "trace_id": tid, "event_count": len(events)}


def get_trace(tid: str, store: CsvStore | None = None) -> dict[str, Any]:
    csv = store or CsvStore()
    traces = [row for row in csv.read("transition_traces") if row["trace_id"] == tid]
    if not traces:
        raise SystimoError("UNKNOWN_TRACE", tid, 404)
    events = _sort_events([row for row in csv.read("transition_events") if row["trace_id"] == tid])
    sources = [row for row in csv.read("transition_sources") if row["trace_id"] == tid]
    return {
        "schema": "systimo.transition_trace.v0",
        "trace": traces[0],
        "events": events,
        "sources": sources,
        "integrity": tamper_detect(tid, csv),
        "live_execution": False,
    }


def latest_for_trade(trade_id: str, as_of: str | None = None, store: CsvStore | None = None) -> dict[str, Any]:
    csv = store or CsvStore()
    rows = [row for row in csv.read("transition_traces") if row.get("trade_id") == trade_id]
    if as_of:
        rows = [row for row in rows if row.get("as_of") == as_of]
    rows = _sort_traces(rows)
    if not rows:
        return {"availability": "UNAVAILABLE", "trade_id": trade_id, "as_of": as_of}
    return get_trace(rows[-1]["trace_id"], csv)


def list_traces(*, plan_status: str | None = None, decision_status: str | None = None, store: CsvStore | None = None) -> list[dict[str, str]]:
    csv = store or CsvStore()
    rows = _sort_traces(csv.read("transition_traces"))
    if plan_status:
        rows = [row for row in rows if plan_status in (row.get("overall_status") or "")]
    if decision_status:
        rows = [row for row in rows if decision_status in (row.get("overall_status") or "")]
    return rows
