"""Condition scopes. v1 executes ticker entry/path/terminal only."""

from __future__ import annotations

from enum import Enum


class ConditionScope(str, Enum):
    UNIVERSE = "UNIVERSE"
    MARKET_TICKER = "MARKET_TICKER"
    ENTRY_EVENT = "ENTRY_EVENT"
    POST_ENTRY_PATH = "POST_ENTRY_PATH"
    TERMINAL = "TERMINAL"
    # Reserved — compiler must not execute.
    GAME = "GAME"
    GAME_PREGAME = "GAME_PREGAME"
    TEAM_GAME = "TEAM_GAME"
    PLAYER_GAME = "PLAYER_GAME"
    POSSESSION = "POSSESSION"
    STATE = "STATE"
    MARKET_CANDLE = "MARKET_CANDLE"


IMPLEMENTED_SCOPES = frozenset(
    {
        ConditionScope.UNIVERSE,
        ConditionScope.MARKET_TICKER,
        ConditionScope.ENTRY_EVENT,
        ConditionScope.POST_ENTRY_PATH,
        ConditionScope.TERMINAL,
    }
)

RESERVED_SCOPES = frozenset(
    {
        ConditionScope.GAME,
        ConditionScope.GAME_PREGAME,
        ConditionScope.TEAM_GAME,
        ConditionScope.PLAYER_GAME,
        ConditionScope.POSSESSION,
        ConditionScope.STATE,
        ConditionScope.MARKET_CANDLE,
    }
)

RESERVED_FAMILIES = frozenset(
    {
        "xib",
        "mcd",
        "team_win_pct",
        "win_pct",
        "home",
        "away",
        "pregame",
        "player",
        "possession",
        "state",
        "game",
        "team_game",
        "expected_margin",
        "disagreement",
    }
)
