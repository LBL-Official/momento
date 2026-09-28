"""Analysis provenance. Reproduce the number six months later."""

from __future__ import annotations

from typing import Any

from roller.results_math.versions import (
    BOOTSTRAP_ITERATIONS,
    BOOTSTRAP_SEED,
    CODE_VERSION,
    CONFIDENCE_LEVEL,
    SCHEMA_VERSION,
    SEMANTICS_VERSION,
    WILSON_Z,
)


def analysis_provenance(
    *,
    hashes: dict[str, Any] | None,
    dataset_version: str | None,
    entry_definition: str | None,
    exit_definition: str | None,
    last_trade: bool,
    assumptions: dict[str, Any],
) -> dict[str, Any]:
    return {
        "results_math_semantics_version": SEMANTICS_VERSION,
        "results_math_schema_version": SCHEMA_VERSION,
        "results_math_code_version": CODE_VERSION,
        "dataset_version": dataset_version,
        "query_hash": (hashes or {}).get("question_hash"),
        "index_hashes": hashes or {},
        "entry_definition": entry_definition,
        "exit_definition": exit_definition,
        "price_definition": "yes_bid_close" if not last_trade else "last_trade_close",
        "settlement_definition": "kalshi_result / settlement_value_e4",
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_iterations": BOOTSTRAP_ITERATIONS,
        "ci_methods": ["wilson", "student_t", "percentile_bootstrap", "clopper_pearson"],
        "confidence_level": CONFIDENCE_LEVEL,
        "wilson_z": WILSON_Z,
        "cluster_unit": "internal_game_id",
        "last_trade": last_trade,
        "assumptions": assumptions,
        "note": "CANDLE PATH ≠ FILL. MEASUREMENT ≠ EDGE. LAST TRADE ≠ EXECUTABLE PRICE.",
    }
