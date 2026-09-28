"""Generic vs frozen provenance. Never impersonate warehouse_frozen_v1."""

from __future__ import annotations

from typing import Any

from roller.research_query.models import (
    BASIS_LAST_TRADE,
    OBSERVABILITY,
    OBSERVABILITY_LAST_TRADE,
    OPERATION_SEMANTICS_VERSION,
    PRICE_RULE,
    PRICE_RULE_LAST_TRADE,
    CompileResult,
    EntryOp,
    ExecutionPath,
    PriceField,
    ResearchQuestion,
)


GENERIC_CAVEATS = (
    "MEASUREMENT ≠ EDGE",
    "CANDLE PATH ≠ FILL",
    "1-MINUTE OBSERVATION ≠ INTRA-MINUTE ORDER",
    "CANDLE-LEVEL OBSERVED — not tick-level",
    "GENERIC ≠ FIRST80 LOCK",
)

KALSHI_LAST_TRADE_CAVEATS = (
    "MEASUREMENT ≠ EDGE",
    "CANDLE/PRINT PATH ≠ FILL",
    "LAST TRADE ≠ YES BID",
    "LAST TRADE ≠ TRADABLE QUOTE — no bid/ask exists on this series",
    "PRINT CROSSING ≠ FILL — this price was not offered to you",
    "1-MINUTE OBSERVATION ≠ INTRA-MINUTE ORDER",
    "MINUTES WITHOUT A PRINT ARE ABSENT, NOT UNCHANGED",
    "NO P&L / EV REPORTED ON A LAST-TRADE BASIS",
    "SPORT RESULT ≠ MARKET SETTLEMENT",
    "GENERIC ≠ FIRST80 LOCK",
)

LAST_TRADE_CAVEATS = (
    "MEASUREMENT ≠ EDGE",
    "LAST TRADE ≠ TRADABLE QUOTE — no bid/ask exists on this series",
    "PRINT CROSSING ≠ FILL — this price was not offered to you",
    "1-MINUTE OBSERVATION ≠ INTRA-MINUTE ORDER",
    "MINUTES WITHOUT A PRINT ARE ABSENT, NOT UNCHANGED",
    "NO P&L / EV REPORTED ON A LAST-TRADE BASIS",
    "POLYMARKET ≠ KALSHI — neither venue is substituted for the other",
    "GENERIC ≠ FIRST80 LOCK",
)


def _market_layer(question: ResearchQuestion) -> tuple[str, str]:
    """Venue-native series name. LAST TRADE ≠ YES BID. Kalshi ≠ Polymarket."""
    last_trade = question.basis() == BASIS_LAST_TRADE
    markets = {str(m) for m in question.universe.markets}
    if last_trade and "polymarket" in markets:
        return "polymarket_1m_last_trade", "PRICE_HISTORY_LAST"
    if last_trade:
        return "kalshi_1m_last_trade", "LAST_TRADE_PRINT"
    return "kalshi_1m_candles", "TRADABLE_CANDLE"


def generic_provenance(
    question: ResearchQuestion,
    compiled: CompileResult,
    *,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entry = question.entry_conditions[0] if question.entry_conditions else None
    op = entry.resolved_operation() if entry else None
    last_trade = question.basis() == BASIS_LAST_TRADE
    market_data, market_data_type = _market_layer(question)
    if last_trade:
        if op in (EntryOp.ABOVE, EntryOp.BELOW):
            price_rule = "last_trade_close_state"
        elif op in (EntryOp.MAXIMUM_TOUCH, EntryOp.MINIMUM_TOUCH):
            price_rule = "last_trade_close_extremum"
        else:
            price_rule = PRICE_RULE_LAST_TRADE
    elif op in (EntryOp.ABOVE, EntryOp.BELOW):
        price_rule = "tradable_yes_bid_close_state"
    elif op in (EntryOp.MAXIMUM_TOUCH, EntryOp.MINIMUM_TOUCH):
        price_rule = "tradable_yes_bid_close_extremum"
    else:
        price_rule = PRICE_RULE
    return {
        "path": "generic_query",
        "execution_path": "generic_query",
        "observability": OBSERVABILITY_LAST_TRADE if last_trade else OBSERVABILITY,
        "price_rule": price_rule,
        "price_basis": question.basis(),
        "price_field": (
            PriceField.LAST_TRADE_CLOSE.value if last_trade else PriceField.YES_BID_CLOSE.value
        ),
        "market_data": market_data,
        "market_data_type": market_data_type,
        "entry_definition": (
            f"{op.value}_{entry.price_e4}" if entry and op else None
        ),
        "operation_semantics_version": OPERATION_SEMANTICS_VERSION,
        "terminal_source": (
            ((diagnostics or {}).get("official_settlement") or {}).get("terminal_source")
            or "kalshi_settlement"
        ),
        "settlement": (diagnostics or {}).get("official_settlement"),
        "period_alignment": "pbp_snap_at_entry_timestamp",
        "omitted_dimensions": list(compiled.omitted_dimensions),
        "diagnostics": diagnostics or {},
        "definition_versions": {
            "GENERIC_QUERY": "research_query_v1",
        },
        "league_producer": (
            "combined_league_union" if len(question.universe.leagues) > 1 else "single_league"
        ),
    }


def assert_not_frozen(prov: dict[str, Any]) -> None:
    defs = prov.get("definition_versions") or {}
    if prov.get("path") == "warehouse_frozen_v1":
        raise AssertionError("generic provenance must not claim warehouse_frozen_v1")
    if defs.get("FIRST80") == "warehouse_frozen_v1" and prov.get("path") == "generic_query":
        raise AssertionError("generic query cannot claim FIRST80 warehouse_frozen_v1")


def frozen_ok(execution_path: ExecutionPath) -> bool:
    return execution_path is ExecutionPath.FROZEN_REFERENCE
