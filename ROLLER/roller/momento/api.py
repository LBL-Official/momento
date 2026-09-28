"""Momento systems HTTP handlers. Façade only."""

from __future__ import annotations

from typing import Any

from roller.momento.adapters import logic_payload, probe_health, system_payload
from roller.momento.bracket import BRACKET_EDGES, INFRA_EDGES
from roller.momento.contracts import CONTRACT_TYPES
from roller.momento.health import aggregate_health, connection_view, ingestion_view
from roller.momento.lifecycle import run_offline_first80
from roller.momento.registry import LIVE_EXECUTION, SYSTEM_COUNT, load_registry


class MomentoApiError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 404) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _row(system_id: str):
    row = load_registry().by_id().get(system_id)
    if row is None:
        raise MomentoApiError("UNKNOWN_SYSTEM", f"unknown system {system_id}")
    return row


def handle_season_strategy() -> dict[str, Any]:
    from roller.momento.season_strategy import SeasonStrategyError, resolve_season_strategy

    try:
        return resolve_season_strategy()
    except SeasonStrategyError as exc:
        raise MomentoApiError(exc.code, exc.message, status_code=409) from exc


def handle_systems() -> dict[str, Any]:
    registry = load_registry()
    return {
        "schema_version": registry.schema_version,
        "code_version": registry.code_version,
        "live_execution": LIVE_EXECUTION,
        "count": SYSTEM_COUNT,
        "systems": [system_payload(row) for row in registry.systems],
    }


def handle_system(system_id: str) -> dict[str, Any]:
    return system_payload(_row(system_id))


def handle_logic(system_id: str) -> dict[str, Any]:
    return logic_payload(_row(system_id))


def handle_system_health(system_id: str) -> dict[str, Any]:
    _row(system_id)
    return probe_health(system_id)


def handle_schema(system_id: str) -> dict[str, Any]:
    row = _row(system_id)
    names = list(row.input_contracts) + list(row.output_contracts)
    schemas = {}
    for name in names:
        cls = CONTRACT_TYPES.get(name)
        if cls is not None:
            schemas[name] = cls.model_json_schema()
    return {
        "system_id": row.id,
        "input_contracts": list(row.input_contracts),
        "output_contracts": list(row.output_contracts),
        "schemas": schemas,
        "live_execution": False,
    }


def handle_dataflow() -> dict[str, Any]:
    return {
        "live_execution": False,
        "bracket_edges": [list(edge) for edge in BRACKET_EDGES],
        "infra_edges": [list(edge) for edge in INFRA_EDGES],
        "lifecycle": "GET /momento/lifecycle",
    }


def handle_health() -> dict[str, Any]:
    return aggregate_health()


def handle_connection() -> dict[str, Any]:
    return connection_view()


def handle_ingestion() -> dict[str, Any]:
    return ingestion_view()


def handle_reconciliation() -> dict[str, Any]:
    from roller.momento.health import reconciliation_view

    return reconciliation_view()


def handle_lifecycle() -> dict[str, Any]:
    return run_offline_first80()


def handle_bdr_catalog() -> dict[str, Any]:
    from roller.momento.bdr import BdrError, handle_catalog

    try:
        return handle_catalog()
    except BdrError as exc:
        raise MomentoApiError(exc.code, exc.message) from exc


def handle_bdr_document(slug: str) -> dict[str, Any]:
    from roller.momento.bdr import BdrError, handle_document

    try:
        return handle_document(slug)
    except BdrError as exc:
        raise MomentoApiError(exc.code, exc.message) from exc


def handle_tk_ultra() -> dict[str, Any]:
    from roller.momento.tk_ultra import TkUltraError, handle_desk

    try:
        return handle_desk()
    except TkUltraError as exc:
        raise MomentoApiError(exc.code, exc.message, exc.status_code) from exc


def handle_tk_ultra_assess(
    *,
    wing_price: str | None = None,
    base_price: str | None = None,
    beta: str | None = None,
    wing_anchor: str | None = None,
    base_anchor: str | None = None,
    ticks_per_handle: str | None = None,
    pair: str | None = None,
    corridor_cents: str | None = None,
) -> dict[str, Any]:
    from roller.momento.tk_ultra import TkUltraError, handle_assess

    try:
        return handle_assess(
            wing_price=wing_price,
            base_price=base_price,
            beta=beta,
            wing_anchor=wing_anchor,
            base_anchor=base_anchor,
            ticks_per_handle=ticks_per_handle,
            pair=pair,
            corridor_cents=corridor_cents,
        )
    except TkUltraError as exc:
        raise MomentoApiError(exc.code, exc.message, exc.status_code) from exc


def handle_tk_ultra_health() -> dict[str, Any]:
    from roller.tk_ultra.api import handle_health

    return handle_health()


def handle_tk_ultra_sources() -> dict[str, Any]:
    from roller.tk_ultra.api import handle_sources

    return handle_sources()


def handle_tk_ultra_positions() -> dict[str, Any]:
    from roller.tk_ultra.api import handle_positions

    return handle_positions()


def handle_tk_ultra_state(
    trade_id: str,
    as_of: str | None = None,
    include_sibling: bool = False,
) -> dict[str, Any]:
    from roller.tk_ultra.api import handle_state
    from roller.tk_ultra.errors import TkUltraV0Error

    try:
        return handle_state(trade_id, as_of=as_of, include_sibling=include_sibling)
    except TkUltraV0Error as exc:
        raise MomentoApiError(exc.code, exc.message, exc.status_code) from exc


def handle_tk_ultra_assess_v0(body: dict[str, Any] | None) -> dict[str, Any]:
    from roller.tk_ultra.api import handle_assess_v0
    from roller.tk_ultra.errors import TkUltraV0Error

    try:
        return handle_assess_v0(body)
    except TkUltraV0Error as exc:
        raise MomentoApiError(exc.code, exc.message, exc.status_code) from exc


def handle_tk_ultra_ballhog_context(trade_id: str, as_of: str | None = None) -> dict[str, Any]:
    from roller.tk_ultra.api import handle_ballhog_context

    return handle_ballhog_context(trade_id, as_of=as_of)
