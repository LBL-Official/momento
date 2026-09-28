"""Transition query handlers. References only. Missing is UNAVAILABLE."""

from __future__ import annotations

from typing import Any

from roller.systimo.models import UNAVAILABLE
from roller.systimo.store import CsvStore
from roller.systimo.transitions import STAGE_SEQ, get_trace, latest_for_trade, list_traces, tamper_detect


def run_transition_query(
    query_type: str, payload: dict[str, Any], csv: CsvStore
) -> tuple[Any, list[dict[str, str]], list[str]]:
    src = [{"system_id": "systimo", "interface_id": "transitions", "provenance": "research/systimo/transitions"}]
    trade_id = str(payload.get("trade_id") or payload.get("system") or "").strip()
    as_of = payload.get("as_of")
    trace_id = str(payload.get("trace_id") or "").strip()
    if query_type == "TRANSITION_TRACE":
        if trace_id:
            return get_trace(trace_id, csv), src, []
        if trade_id:
            return latest_for_trade(trade_id, as_of, csv), src, []
        return {"traces": list_traces(store=csv)}, src, []
    if query_type == "CURRENT_POSITION_CHAIN":
        body = latest_for_trade(trade_id, as_of, csv) if trade_id else {"availability": UNAVAILABLE}
        return body, src, []
    if query_type == "POSITMAN_PLAN":
        return _invoke_plan(trade_id, as_of), src, []
    if query_type == "DREVO_DECISION":
        return _invoke_decision(trade_id, as_of), src, []
    if query_type == "TRANSITION_INTEGRITY":
        if not trace_id and trade_id:
            latest = latest_for_trade(trade_id, as_of, csv)
            trace_id = str((latest.get("trace") or {}).get("trace_id") or latest.get("trace_id") or "")
        if not trace_id:
            return {"availability": UNAVAILABLE, "integrity_status": UNAVAILABLE}, src, []
        return tamper_detect(trace_id, csv), src, []
    if query_type == "TRANSITION_SOURCES":
        wanted = trace_id
        if not wanted and trade_id:
            latest = latest_for_trade(trade_id, as_of, csv)
            wanted = str((latest.get("trace") or {}).get("trace_id") or "")
        rows = [row for row in csv.read("transition_sources") if not wanted or row["trace_id"] == wanted]
        return {"sources": rows, "n": len(rows)}, src, []
    if query_type == "UNRESOLVED_TRANSITIONS":
        rows = [
            row
            for row in list_traces(store=csv)
            if "UNRESOLVED" in (row.get("overall_status") or "")
            or row.get("overall_status") in {"SOURCE_UNAVAILABLE", "PLAN_UNRESOLVED", "POLICY_UNRESOLVED"}
        ]
        return {"traces": rows, "n": len(rows)}, src, []
    if query_type == "REJECTED_TRANSITIONS":
        rows = [row for row in list_traces(store=csv) if row.get("overall_status") == "REJECT"]
        return {"traces": rows, "n": len(rows)}, src, []
    if query_type == "SOURCE_TO_DECISION_LINEAGE":
        body = latest_for_trade(trade_id, as_of, csv) if trade_id else {"availability": UNAVAILABLE}
        events = body.get("events") if isinstance(body, dict) else []
        stages = [row.get("stage_seq") for row in events] if isinstance(events, list) else []
        return {"lineage": body, "stage_seq": stages, "stage_names": STAGE_SEQ}, src, []
    if query_type == "LATEST_STAGE":
        body = latest_for_trade(trade_id, as_of, csv) if trade_id else {"availability": UNAVAILABLE}
        trace = body.get("trace") if isinstance(body, dict) else {}
        return {"latest_stage": (trace or {}).get("current_stage"), "trace": trace}, src, []
    if query_type == "ORCHESTRA_CONTEXT":
        from roller.systimo.orchestra import handle_orchestra_context

        return handle_orchestra_context(trade_id, as_of), src, []
    return {"availability": UNAVAILABLE}, src, [f"unhandled {query_type}"]


def _invoke_plan(trade_id: str, as_of: str | None) -> dict[str, Any]:
    if not trade_id:
        return {"availability": UNAVAILABLE, "detail": "trade_id required"}
    from roller.positman.service import plan

    return plan(trade_id, as_of, record=False)


def _invoke_decision(trade_id: str, as_of: str | None) -> dict[str, Any]:
    if not trade_id:
        return {"availability": UNAVAILABLE, "detail": "trade_id required"}
    from roller.dre.decision import decide_for_trade

    return decide_for_trade(trade_id, as_of, record=False)
