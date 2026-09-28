"""MLB factory snapshot. Display and identity only. Not MlbStrategy."""

from __future__ import annotations

from typing import Any

from roller.jump.bots.versions import ENGINE_POINTER, FACTORY_ID, FACTORY_VERSION, STRATEGY_POINTER

# Copied from config/live.toml and strategies/mlb/src/quote.rs.
# Jump does not execute these rules.
FACTORY: dict[str, Any] = {
    "factory_id": FACTORY_ID,
    "factory_version": FACTORY_VERSION,
    "name": "MLB Production Factory",
    "execution": "MLB Factory Execution Engine",
    "editable": False,
    "bankroll_cents": 5000,
    "allocation_bps": 1250,
    "per_game_cents": 625,
    "max_open_mlb_positions": 5,
    "min_entry_cents": 80,
    "preferred_entry_cents": 80,
    "max_entry_cents": 83,
    "confirm_cents": 81,
    "lock_cents": 89,
    "signal": "80_to_81_yes_bid",
    "order_type": "maker_only_post_only",
    "risk": "Risk Decision Engine",
    "engine_pointer": ENGINE_POINTER,
    "strategy_pointer": STRATEGY_POINTER,
    "notes": (
        "Factory settings of the current MLB desk. Jump does not reimplement "
        "the strategy. Candle-path ITI is lineage only and is not the live signal."
    ),
}


def factory_snapshot() -> dict[str, Any]:
    return dict(FACTORY)
