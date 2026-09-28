"""Full-scan semantic oracle. Not optimized. Same detectors as execute.

Never opens rq_index. Never routes FIRST80. Never reimplements Cross/Touch/PIT.
"""

from __future__ import annotations

from typing import Any, Callable

from roller.config import RollerConfig
from roller.research_query import cache as rq_cache
from roller.research_query.compiler import compile_draft, compile_question
from roller.research_query.execute import execute_compiled
from roller.research_query.models import ExecutionPath, ResearchQuestion


class ReferenceEngineError(ValueError):
    """FIRST80 / frozen objects are not executed here."""


def compile_for_reference(payload: dict[str, Any], *, cfg: RollerConfig | None = None):
    payload = dict(payload)
    payload.pop("execution_path", None)
    payload.pop("reference_match", None)
    payload.pop("status", None)
    draft = payload.get("draft") if isinstance(payload.get("draft"), dict) else payload
    if "universe" in payload and "entry_conditions" in payload:
        return compile_question(ResearchQuestion.from_dict(payload), cfg=cfg)
    if "question" in payload:
        return compile_question(
            ResearchQuestion.from_dict(payload["question"]),
            cfg=cfg,
            draft=payload.get("draft"),
        )
    return compile_draft(payload.get("draft") or payload, cfg=cfg)


def execute_reference(
    payload: dict[str, Any],
    *,
    cfg: RollerConfig | None = None,
    ticker_payloads: dict[str, list[dict[str, Any]]] | None = None,
    pbp_by_game: dict[str, list[dict[str, Any]]] | None = None,
    markets_by_ticker: dict[str, dict[str, Any]] | None = None,
    snap_fn: Callable | None = None,
    clear_cache: bool = True,
) -> dict[str, Any]:
    """CSV / injected full-scan using operations.py detectors."""
    compiled = compile_for_reference(payload, cfg=cfg)
    if compiled.execution_path is ExecutionPath.FROZEN_REFERENCE:
        raise ReferenceEngineError(
            "FIRST80 stays on execute_research_object. Reference engine does not route frozen_reference."
        )
    if clear_cache and ticker_payloads is None:
        rq_cache.clear()
    te_filters = None
    draft = payload.get("draft") if isinstance(payload.get("draft"), dict) else payload
    if isinstance(draft, dict):
        te_filters = draft.get("teFilters") or draft.get("te_filters")
    return execute_compiled(
        compiled,
        cfg=cfg,
        ticker_payloads=ticker_payloads,
        pbp_by_game=pbp_by_game,
        markets_by_ticker=markets_by_ticker,
        snap_fn=snap_fn,
        te_filters=te_filters if isinstance(te_filters, dict) else None,
        force_full_scan=ticker_payloads is None,
    )


def row_identity(row: dict[str, Any]) -> tuple:
    return (
        str(row.get("ticker") or ""),
        str(row.get("internal_game_id") or ""),
        str(row.get("entry_ts") or ""),
        str(row.get("entry_price_e4") or ""),
        str(row.get("entry_operation") or ""),
        str(row.get("entry_close") or ""),
        str(row.get("alignment") or ""),
        str(row.get("exit_ts") or ""),
        str(row.get("exit_close") or ""),
        str(row.get("path_true") or ""),
        str(row.get("terminal_yes") or ""),
        str(row.get("exit_outcome") or ""),
    )


def identities(env: dict[str, Any]) -> list[tuple]:
    trades = (env.get("population") or {}).get("trades") or []
    return sorted(row_identity(r) for r in trades if isinstance(r, dict))
