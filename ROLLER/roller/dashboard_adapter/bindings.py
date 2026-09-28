"""Paths to frozen warehouse artifacts. Read-only references — no math."""

from __future__ import annotations

from pathlib import Path

# Relative to Momento repo root (ROLLER/ is one level down).
_REPO = Path(__file__).resolve().parents[3]

WAREHOUSE_NBA_FIRST80_CANDIDATES = (
    _REPO
    / "Backtesting Suite"
    / "Data"
    / "NBA"
    / "2025-2026"
    / "warehouse"
    / "derived"
    / "nba"
    / "first80_execution_audit"
    / "candidates.json"
)

WAREHOUSE_NBA_BARRIER_TRADES = (
    _REPO
    / "Backtesting Suite"
    / "Data"
    / "NBA"
    / "2025-2026"
    / "warehouse"
    / "derived"
    / "nba"
    / "first80_quarter_barrier_survival"
    / "trades.parquet"
)

WAREHOUSE_NCAAB_FIRST80_P5_TRADES = (
    _REPO
    / "Backtesting Suite"
    / "Data"
    / "NCAAB"
    / "2025-2026"
    / "warehouse"
    / "derived"
    / "ncaab"
    / "first80_p5_half_barrier_survival"
    / "trades.parquet"
)

BINDING_WAREHOUSE_FROZEN_V1 = "warehouse_frozen_v1"
BINDING_ROLLER_FIRST80 = "roller_4.1.0-R"
BINDING_BARRIER_SURVIVAL_V1 = "barrier_survival_v1"
BINDING_NCAAB_FIRST80_P5 = "p5_half_barrier_survival_v1"

# Expected locked population size for NBA warehouse FIRST80 settled book.
NBA_FIRST80_EXPECTED_N = 1230

# Expected locked population size for NCAAB P5∩P5 FIRST80 frozen parquet.
NCAAB_FIRST80_P5_EXPECTED_N = 721

# Phase 4 adapter binding: schema entry_slice ↔ barrier artifact column.
ENTRY_SLICE_ARTIFACT_FIELD = "entry_quarter_bucket"

# Phase 6: NCAAB half structural axis on the frozen P5 artifact.
ENTRY_HALF_ARTIFACT_FIELD = "entry_half_bucket"

POPULATION_ROWS_SERIALIZE_CAP = 200

NCAAB_FIRST80_P5_ARTIFACT_LABEL = "first80_p5_half_barrier_survival/trades.parquet"


def warehouse_first80_candidates_path() -> Path:
    return WAREHOUSE_NBA_FIRST80_CANDIDATES


def warehouse_first80_available() -> bool:
    return WAREHOUSE_NBA_FIRST80_CANDIDATES.is_file()


def warehouse_barrier_trades_path() -> Path:
    return WAREHOUSE_NBA_BARRIER_TRADES


def warehouse_barrier_trades_available() -> bool:
    return WAREHOUSE_NBA_BARRIER_TRADES.is_file()


def warehouse_ncaab_first80_p5_trades_path() -> Path:
    return WAREHOUSE_NCAAB_FIRST80_P5_TRADES


def warehouse_ncaab_first80_p5_available() -> bool:
    return WAREHOUSE_NCAAB_FIRST80_P5_TRADES.is_file()
