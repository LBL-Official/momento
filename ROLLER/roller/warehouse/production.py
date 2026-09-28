"""Production ROLLER capability surface.

NBA-only. Does not change Phase 11 compile_research semantics.
Does not call Confirm & Run. Does not invent L2, tick, or fills.
"""

from __future__ import annotations

from typing import Any

from roller.config import RollerConfig
from roller.research_query.models import ResearchQuestion
from roller.warehouse.coverage import (
    CATALOG_VERSION,
    OBS_BASIS,
    OBS_RESOLUTION,
    PIT_FIELD,
    get_catalog,
)
from roller.warehouse.desk import DESK_SPORTS, desk_sport
from roller.warehouse.frontend_contract import PRICE_OPS
from roller.warehouse.identity import IDENTITY_RULE_VERSION
from roller.warehouse.research_compiler import COMPILER_VERSION

PRODUCTION_SPORT = "NBA"
PRODUCTION_SPORTS = ("NBA", "MLB", "NCAAB", "ATP", "WTA")
UNAVAILABLE_SPORTS = ("WNBA",)
UNAVAILABLE_TOKENS = frozenset(
    {
        "WNBA",
        "NFL",
        "NHL",
    }
)
ENTRY_OPERATIONS = (
    "CROSS",
    "TOUCH",
    "FIRST_TOUCH",
    "BREAK",
    "REVERSION",
    "BOUNCE",
    "RECOVERY",
    "ABOVE",
    "BELOW",
    "MAXIMUM_TOUCH",
    "MINIMUM_TOUCH",
    "SECOND_TOUCH",
    "THIRD_TOUCH",
    "FOURTH_TOUCH",
    "NTH_TOUCH",
)
EXIT_OPERATIONS = (
    "HOLD",
    "REACH",
    "DROP",
    "RISE",
    "RECOVER",
    "BOUNCE",
    "REVERT",
    "MAXIMUM_MOVE",
    "MINIMUM_MOVE",
    "NEVER_REACH",
    "CLOCK",
)
TERMINAL_MODES = ("YES", "NO", "BOTH", "HOLD_TO_SETTLEMENT")
PERIODS = (
    "Q1",
    "Q2",
    "Q3",
    "Q4",
    "OT",
    "H1",
    "H2",
    "S1",
    "S2",
    "S3",
    "S4",
    "S5",
    "G1-3",
    "G4-6",
    "G7-9",
    "G10+",
)
UNSUPPORTED = ("HISTORICAL_L2", "HISTORICAL_TICK", "PBP_MARKET_PIT_ALIGNMENT")


def unavailable_production_sport(question: ResearchQuestion) -> str | None:
    """Return an unavailable-sport token, or None when the universe is a desk sport."""
    sports = {str(s).upper() for s in question.universe.sports}
    leagues = {str(s).upper() for s in question.universe.leagues}
    tokens = sports | leagues
    blocked = tokens & UNAVAILABLE_TOKENS
    if blocked:
        return sorted(blocked)[0]
    sport = desk_sport(question)
    if sport in DESK_SPORTS:
        return None
    if not (tokens & {"NBA", "MLB", "NCAAB", "BASEBALL", "ATP", "WTA"}):
        return "UNIVERSE"
    extra = tokens - {"NBA", "BASKETBALL", "MLB", "BASEBALL", "NCAAB", "ATP", "WTA", "TENNIS"}
    if extra:
        return sorted(extra)[0]
    return "UNIVERSE"


def production_capabilities(cfg: RollerConfig | None = None) -> dict[str, Any]:
    cfg = cfg or RollerConfig()
    warehouse_version = ""
    identity_version = IDENTITY_RULE_VERSION
    catalog_version = CATALOG_VERSION
    matrix: dict[str, str] = {}
    try:
        catalog = get_catalog(cfg)
        warehouse_version = str(catalog.warehouse_version)
        identity_version = str(catalog.identity_version)
        catalog_version = str(catalog.catalog_version)
        matrix = catalog.capability_matrix()
    except (OSError, ValueError, FileNotFoundError):
        matrix = {
            "HISTORICAL_L2": "DATA_REQUIRED",
            "HISTORICAL_TICK": "DATA_REQUIRED",
            "PBP_MARKET_PIT_ALIGNMENT": "OPERATION_REQUIRED",
        }
    return {
        "available_sports": list(PRODUCTION_SPORTS),
        "unavailable_sports": [
            {"sport": name, "status": "NOT_AVAILABLE"} for name in UNAVAILABLE_SPORTS
        ],
        "available_observation_bases": [OBS_BASIS, "LAST_TRADE_PRINT"],
        "available_resolutions": [OBS_RESOLUTION],
        "available_PIT_fields": [PIT_FIELD],
        "available_entry_operations": list(ENTRY_OPERATIONS),
        "available_exit_operations": list(EXIT_OPERATIONS),
        "available_terminal_modes": list(TERMINAL_MODES),
        "supported_periods": list(PERIODS),
        "supported_clock_operations": ["remaining_from_s", "remaining_to_s"],
        "unsupported_capabilities": list(UNSUPPORTED),
        "capability_matrix": matrix,
        "warehouse_version": warehouse_version,
        "identity_version": identity_version,
        "catalog_version": catalog_version,
        "compiler_version": COMPILER_VERSION,
        "price_operations": sorted(PRICE_OPS),
        "source": "warehouse_research",
    }


def sport_lock_payload(question: ResearchQuestion, errors: list[str], blocked: str) -> dict[str, Any]:
    return {
        "status": "DATA_REQUIRED",
        "syntactic_errors": errors,
        "question": question.to_dict(),
        "plan": None,
        "plan_hash": None,
        "capability": {
            "status": "DATA_REQUIRED",
            "required": ["UNIVERSE"],
            "satisfied": [],
            "missing_data": ["UNIVERSE"],
            "missing_operations": [],
            "unavailable_sport": blocked,
            "matrix": {},
        },
        "observation_basis": OBS_BASIS,
        "resolution": OBS_RESOLUTION,
        "pit_field": PIT_FIELD,
        "compiler_version": COMPILER_VERSION,
        "warehouse_version": "",
        "catalog_version": CATALOG_VERSION,
        "identity_version": IDENTITY_RULE_VERSION,
        "source": "warehouse_research",
    }
