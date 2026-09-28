"""MLB Bot 001 folder boundary. Pointers only. No crate move. No second worker."""

from __future__ import annotations

from typing import Any

from roller.vital.mlb_001.identity import (
    API_ROUTE_PREFIX,
    BOT_ALIASES,
    BOT_DISPLAY,
    BOT_ID,
    CONFIG_POINTER,
    ENGINE_POINTER,
    FOLDER,
    FRONTEND_POINTER,
    KIND,
    PACKAGE,
    SECRET_FETCH_POINTER,
    SERVICE_NAME,
    SPORT,
    STRATEGY_POINTER,
    UNIT_POINTER,
)

# Sport crate / shared dump names that must never be a Vital bot_id.
FORBIDDEN_AS_BOT_ID = frozenset({"mlb", "nba", "ncaab", "nfl", "wnba", "vital", "jump"})

TREE_OWNED = (
    "metadata",
    "source",
    "config",
    "deployment",
    "runtime",
    "logs",
    "events",
    "execution",
    "docs",
    "pointers",
)

POINTERS = {
    "backend": "ROLLER/roller/vital",
    "worker": ENGINE_POINTER,
    "strategy": STRATEGY_POINTER,
    "config": CONFIG_POINTER,
    "api": API_ROUTE_PREFIX,
    "frontend": FRONTEND_POINTER,
    "deployment": UNIT_POINTER,
    "secret_fetch": SECRET_FETCH_POINTER,
    "docs": f"{FOLDER}/docs",
}


def boundary_record() -> dict[str, Any]:
    return {
        "bot_id": BOT_ID,
        "aliases": list(BOT_ALIASES),
        "name": BOT_DISPLAY,
        "kind": KIND,
        "sport": SPORT,
        "package": PACKAGE,
        "folder": FOLDER,
        "isolated": True,
        "moved": False,
        "second_engine": False,
        "live_execution": False,
        "aws_runtime_id": SERVICE_NAME,
        "tree": list(TREE_OWNED),
        "pointers": dict(POINTERS),
        "notes": (
            "MLB Bot 001 owns this folder only. Worker and strategy stay "
            "pointers. Do not copy apps/trading-engine or strategies/mlb here. "
            "Bot 002 must be research/vital/bots/mlb-002, not a child of this tree."
        ),
    }
