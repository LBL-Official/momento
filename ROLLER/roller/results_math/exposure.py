"""Results verifier for the strategy/backtest exposure contract.

Results does not own the strategy default. It consumes
`roller.exposure_contract` and verifies the retained population.

Results never rewrites N. If N=1661 tickers and unique games=1500 under
EXPOSURE_UNIT=GAME, status is CARDINALITY_VIOLATION and strategy statistics
are withheld. A future research-layer change must emit a new versioned object.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from roller.exposure_contract import (
    EVENT,
    GAME,
    MULTI_ENTRY_PER_GAME,
    ONE_GAME_ONE_TRADE,
    ROW_KEYS,
    TEAM,
    TICKER,
    UNITS,
    resolve_exposure_contract,
)
from roller.results_math.models import CARDINALITY_VIOLATION, OBSERVED, UNVERIFIED

CLUSTERING_UNIT_GAME = "internal_game_id"

__all__ = [
    "EVENT",
    "GAME",
    "MULTI_ENTRY_PER_GAME",
    "ONE_GAME_ONE_TRADE",
    "TEAM",
    "TICKER",
    "declared_exposure_unit",
    "verify_exposure",
]


def _row_key(row: dict[str, Any], unit: str) -> str | None:
    for field in ROW_KEYS.get(unit, ()):
        value = row.get(field)
        if value is not None and value != "":
            return str(value)
    return None


def declared_exposure_unit(
    result: dict[str, Any] | None = None,
    question: Any = None,
) -> str:
    return str(resolve_exposure_contract(result, question)["exposure_unit"])


def verify_exposure(
    *,
    rows: list[dict[str, Any]] | None,
    n: int | None,
    declared: str | None = None,
    result: dict[str, Any] | None = None,
    question: Any = None,
) -> dict[str, Any]:
    """Verify retained-row cardinality against the exposure contract. Does not rewrite N."""
    if declared is not None:
        contract = resolve_exposure_contract({"exposure_unit": declared}, question)
    else:
        contract = resolve_exposure_contract(result, question)
    unit = str(contract["exposure_unit"])
    max_n = contract.get("max_entries_per_unit")
    unique_key = {
        GAME: "n_unique_games",
        MULTI_ENTRY_PER_GAME: "n_unique_games",
        TEAM: "n_unique_teams",
        TICKER: "n_unique_tickers",
        EVENT: "n_unique_events",
    }.get(unit, "n_unique_units")
    equals_key = {
        GAME: "n_equals_unique_games",
        MULTI_ENTRY_PER_GAME: "n_equals_unique_games",
        TEAM: "n_equals_unique_teams",
        TICKER: "n_equals_unique_tickers",
        EVENT: "n_equals_unique_events",
    }.get(unit, "n_equals_unique_units")
    base = {
        **contract,
        "declared_unit": unit,
        "clustering_unit": contract.get("clustering_field"),
        "n_population": n,
        "n_rows": len(rows) if rows is not None else None,
        "n_unique_games": None,
        "n_unique_units": None,
        unique_key: None,
        "n_missing_unit_id": None,
        "max_trades_per_game": None,
        "max_trades_per_unit": None,
        "duplicate_games": [],
        "duplicate_units": [],
        equals_key: None,
        "n_equals_unique_games": None if unique_key != "n_unique_games" else None,
        "strategy_statistics_permitted": True,
    }
    if unit not in UNITS:
        return {
            **base,
            "status": UNVERIFIED,
            "reason": f"Unknown exposure unit {unit}. Results will not invent a clustering key.",
        }
    if unit == MULTI_ENTRY_PER_GAME or max_n is None:
        extra: dict[str, Any] = {}
        if rows:
            keys = [_row_key(r, GAME) for r in rows]
            present = [k for k in keys if k is not None]
            extra = {
                "n_unique_games": len(set(present)),
                "n_missing_unit_id": sum(1 for k in keys if k is None),
                "max_trades_per_game": max(Counter(present).values()) if present else 0,
                "max_trades_per_unit": max(Counter(present).values()) if present else 0,
            }
        return {
            **base,
            **extra,
            "status": OBSERVED,
            "strategy_statistics_permitted": True,
            "reason": "Research object explicitly allows multiple entries per game.",
        }
    if not rows:
        return {
            **base,
            "status": UNVERIFIED,
            "reason": (
                f"No retained rows to verify EXPOSURE_UNIT={unit} "
                f"MAX_ENTRIES_PER_UNIT={max_n}. Do not assume N is unique {contract.get('clustering_field')}."
            ),
        }
    keys = [_row_key(r, unit) for r in rows]
    missing = sum(1 for k in keys if k is None)
    present = [k for k in keys if k is not None]
    counts = Counter(present)
    dupes = sorted(gid for gid, c in counts.items() if c > int(max_n))
    n_units = len(counts)
    max_per = max(counts.values()) if counts else 0
    n_eq = n is not None and missing == 0 and int(max_n) == 1 and n_units == int(n) and len(rows) == int(n)
    out = {
        **base,
        "n_rows": len(rows),
        "n_unique_units": n_units,
        unique_key: n_units,
        "n_missing_game_id": missing if unit in {GAME, MULTI_ENTRY_PER_GAME} else None,
        "n_missing_unit_id": missing,
        "max_trades_per_unit": max_per,
        "max_trades_per_game": max_per if unit == GAME else None,
        "duplicate_units": dupes[:20],
        "duplicate_games": dupes[:20] if unit == GAME else [],
        "n_duplicate_units": len(dupes),
        "n_duplicate_games": len(dupes) if unit == GAME else 0,
        equals_key: n_eq,
        "n_equals_unique_games": n_eq if unit == GAME else None,
    }
    if dupes:
        return {
            **out,
            "status": CARDINALITY_VIOLATION,
            "strategy_statistics_permitted": False,
            "reason": (
                f"One or more {contract.get('clustering_field')} retained more than "
                f"{max_n} trade(s). FAIL CLOSED. N is unchanged. Strategy statistics withheld."
            ),
        }
    if missing:
        return {
            **out,
            "status": UNVERIFIED,
            "reason": (
                f"{missing} retained rows lack {contract.get('clustering_field')}. "
                "Cardinality cannot be proven. Do not assume the population is compliant."
            ),
        }
    if int(max_n) == 1 and n is not None and n_units != int(n):
        return {
            **out,
            "status": CARDINALITY_VIOLATION,
            "strategy_statistics_permitted": False,
            "reason": (
                f"N={n} does not equal unique {contract.get('clustering_field')}={n_units}. "
                "FAIL CLOSED. Results does not rewrite N."
            ),
        }
    return {
        **out,
        "status": OBSERVED,
        "strategy_statistics_permitted": True,
        "reason": (
            f"Each retained row respects EXPOSURE_UNIT={unit} "
            f"MAX_ENTRIES_PER_UNIT={max_n}."
        ),
    }
