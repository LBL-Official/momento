"""Simple warehouse pull: compile chips, scan matching rows, return N.

This is the generic Confirm & Run measurement. Frozen FIRST80 is not this path.
CANDLE ≠ FILL. LAST TRADE ≠ YES BID.
"""

from __future__ import annotations

from typing import Any

from roller.research_query.compiler import compile_draft
from roller.research_query.execute import apply_te_population_scope, evaluate_ticker
from roller.research_query.models import (
    ExecutionPath,
    ResearchStatus,
    TerminalOutcome,
)
from roller.research_query.season_mapping import sport_from_league


def measured_n(envelope: dict[str, Any]) -> int | None:
    """Reported population N, or None when compile/execute refused a number."""
    status = str(envelope.get("execution_status") or "")
    if status in {"OPERATION_REQUIRED", "DATA_REQUIRED", "READY_WITH_LIMITATIONS"}:
        return None
    if status == "FROZEN_REFERENCE":
        return None
    summary = envelope.get("summary") or {}
    if summary.get("population_n") is not None:
        return int(summary["population_n"])
    trades = (envelope.get("population") or {}).get("trades")
    if trades is None:
        return None
    return len(trades)


def pull(
    draft: dict[str, Any],
    *,
    ticker_payloads: dict[str, list[dict[str, Any]]],
    pbp_by_game: dict[str, list[dict[str, Any]]] | None = None,
    markets_by_ticker: dict[str, dict[str, Any]] | None = None,
    games: list[dict[str, Any]] | None = None,
    te_filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile the draft, then count warehouse tickers that match the chips.

    Injected rows are the warehouse. No index. No frozen lock. No invented fill.
    """
    compiled = compile_draft(draft)
    if compiled.status is ResearchStatus.OPERATION_REQUIRED:
        return {
            "execution_status": "OPERATION_REQUIRED",
            "n": None,
            "trades": None,
            "compile": compiled.to_dict(),
        }
    if compiled.status is ResearchStatus.DATA_REQUIRED:
        return {
            "execution_status": "DATA_REQUIRED",
            "n": None,
            "trades": None,
            "compile": compiled.to_dict(),
        }
    if compiled.status is ResearchStatus.READY_WITH_LIMITATIONS and not compiled.question.accept_limitations:
        return {
            "execution_status": "READY_WITH_LIMITATIONS",
            "n": None,
            "trades": None,
            "compile": compiled.to_dict(),
        }
    if compiled.execution_path is ExecutionPath.FROZEN_REFERENCE:
        return {
            "execution_status": "FROZEN_REFERENCE",
            "n": None,
            "trades": None,
            "compile": compiled.to_dict(),
        }

    question = compiled.question
    leagues = list(question.universe.leagues)
    fallback = leagues[0] if leagues else "NBA"
    try:
        fallback_sport = sport_from_league(fallback)
    except ValueError:
        fallback_sport = fallback
    games_by_id = {str(g.get("internal_game_id") or ""): g for g in (games or [])}
    rows = []
    for ticker, candles in ticker_payloads.items():
        if not ticker or not candles:
            continue
        gid = str((candles[0] or {}).get("internal_game_id") or "")
        sport = str(
            (candles[0] or {}).get("_research_sport")
            or (candles[0] or {}).get("sport")
            or (games_by_id.get(gid) or {}).get("_research_sport")
            or (games_by_id.get(gid) or {}).get("sport")
            or fallback_sport
        )
        row, _diag = evaluate_ticker(
            candles,
            question,
            sport=sport,
            pbp_events=(pbp_by_game or {}).get(gid),
            market=(markets_by_ticker or {}).get(ticker),
        )
        if row is None:
            continue
        rows.append(row)

    te = te_filters
    if te is None and isinstance(draft, dict):
        raw_te = draft.get("teFilters") or draft.get("te_filters")
        te = raw_te if isinstance(raw_te, dict) else None
    rows, _scope = apply_te_population_scope(rows, te)
    if not question.tagged_exits():
        term = question.terminal
        if term is TerminalOutcome.YES:
            rows = [r for r in rows if r.get("terminal_yes") is True]
        elif term is TerminalOutcome.NO:
            rows = [r for r in rows if r.get("terminal_yes") is False]
    return {
        "execution_status": "COMPLETE",
        "n": len(rows),
        "trades": rows,
        "compile": compiled.to_dict(),
    }
