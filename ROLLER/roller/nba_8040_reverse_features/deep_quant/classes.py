"""Documented feature-class sets. Period one-hot is class-only, not ALL."""

from __future__ import annotations

from roller.nba_8040_reverse_features.catalog import matrix_specs

PRICE = [
    "entry_bid_cents",
    "entry_last_cents",
    "entry_volume",
    "jump_through_80",
    "exact_80",
    "prior_close_cents",
    "close_1m_before",
    "close_3m_before",
    "close_5m_before",
    "close_10m_before",
    "close_15m_before",
    "close_30m_before",
    "delta_1m",
    "delta_3m",
    "delta_5m",
    "delta_10m",
    "delta_15m",
    "delta_30m",
]
TIME = [
    "period_remaining_s",
    "game_seconds_remaining",
    "frac_period_remaining",
    "frac_game_elapsed",
]
SCORE = ["bought_margin", "abs_margin", "leading", "tie", "favorite_leading"]
OPEN = ["pregame_cents", "distance_from_open"]
MICRO_PATH = [
    "came_from_below",
    "jump_through_80",
    "exact_80",
    "prior_close_cents",
    "velocity_1m",
    "velocity_3m",
    "velocity_5m",
    "velocity_10m",
    "velocity_15m",
    "velocity_30m",
    "accel_5m",
    "accel_10m",
    "accel_15m",
    "accel_30m",
]
VOLATILITY = [
    "range_1m",
    "range_3m",
    "range_5m",
    "range_10m",
    "range_15m",
    "range_30m",
    "std_5m",
    "std_10m",
    "std_15m",
    "std_30m",
    "direction_changes_5m",
    "direction_changes_10m",
    "direction_changes_15m",
    "direction_changes_30m",
]
MARKET_STATE = [
    "entry_bid_cents",
    "entry_ask_cents",
    "spread_cents",
    "entry_last_cents",
    "entry_volume",
]
PERIOD = ["period_q2", "period_q3"]


def _uniq(names: list[str]) -> list[str]:
    seen: list[str] = []
    for name in names:
        if name not in seen:
            seen.append(name)
    return seen


def all_pre80_names() -> list[str]:
    return [spec.name for spec in matrix_specs()]


def class_sets() -> dict[str, list[str]]:
    return {
        "PRICE": list(PRICE),
        "TIME": list(TIME),
        "SCORE": list(SCORE),
        "OPEN": list(OPEN),
        "MICRO_PATH": list(MICRO_PATH),
        "VOLATILITY": list(VOLATILITY),
        "MARKET_STATE": list(MARKET_STATE),
        "PERIOD": list(PERIOD),
        "MARKET_PATH": _uniq(PRICE + MICRO_PATH),
        "PRICE_TIME": _uniq(PRICE + TIME),
        "PRICE_SCORE": _uniq(PRICE + SCORE),
        "TIME_SCORE": _uniq(TIME + SCORE),
        "ALL_PRE80": all_pre80_names(),
        "ALL_PRE80_EX_TIME": [name for name in all_pre80_names() if name not in TIME],
        "TIME_RAW": ["period_remaining_s", "game_seconds_remaining"],
        "TIME_FRAC": ["frac_period_remaining", "frac_game_elapsed"],
    }


LETTER_SETS = {
    "A_PRICE": "PRICE",
    "B_TIME": "TIME",
    "C_SCORE": "SCORE",
    "D_OPEN": "OPEN",
    "E_MARKET_PATH": "MARKET_PATH",
    "F_VOLATILITY": "VOLATILITY",
    "G_PERIOD": "PERIOD",
    "H_PRICE_TIME": "PRICE_TIME",
    "I_PRICE_SCORE": "PRICE_SCORE",
    "J_TIME_SCORE": "TIME_SCORE",
    "K_ALL_PRE80": "ALL_PRE80",
}


CLASS_LETTER = {
    "A": "identity",
    "B": "market_at_80",
    "C": "pre80_level_path",
    "D": "micro_path",
    "E": "post80_path",
    "F": "time",
    "G": "score",
    "H": "score_trajectory",
    "I": "possession_fouls_timeouts",
    "J": "path_velocity",
    "K": "path_volatility",
    "L": "quote_at_entry",
    "M": "opening",
    "N": "opposite_ticker",
    "O": "period_grouping",
    "P": "labels",
}
