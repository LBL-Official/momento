"""Canonical warehouse contract. Does not change Confirm & Run loaders.

admin.load_dataset still reads monthly CSV. This package defines the
Parquet-first contract, validation, CSV catalog, gap audit, Phase 1–2
entities/identity, Phase 3–7 NBA projections under warehouse_v0, the
Phase 8 physical warehouse tree, Phase 9 coverage catalog, Phase 10
ResearchContext loader, Phase 11 isolated research compiler,
Phases 12–14 conditional backtest (reference ≡ optimized + edges),
Phase 15 performance, Phase 16 parquet-only warehouse-backed execution,
Phase 17 source-driven warehouse ingest, Phase 18 Auto Roller verify,
Phase 19 frontend ResearchQuestion contract, and Phase 20 NBA desk
acceptance. Detectors stay in research_query.operations.

Phase 1–20 types are unused by execute / compile_draft / load_dataset.
Historical L2/tick are DATA_REQUIRED. PBP is sequence-only.
Candle-path results are not fills. Do not start Phase 21 from this package.
"""

from __future__ import annotations

from roller.warehouse.entities import ENTITY_MODEL_VERSION
from roller.warehouse.identity import IDENTITY_RULE_VERSION
from roller.warehouse.layout_v0 import LINK_RULE_VERSION

CONTRACT_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"

__all__ = [
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "ENTITY_MODEL_VERSION",
    "IDENTITY_RULE_VERSION",
    "LINK_RULE_VERSION",
]
