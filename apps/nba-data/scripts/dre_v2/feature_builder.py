"""Nested feature families. Complete-case exclusions are documented, not silent."""

from __future__ import annotations

FAMILIES = {
    "B0": [
        "current_price",
        "entry_price",
        "deterioration_absolute",
    ],
    "B1": [
        "current_price",
        "entry_price",
        "deterioration_absolute",
        "market_age_seconds",
        "position_age_wall_s",
    ],
    "B2": [
        "current_price",
        "entry_price",
        "deterioration_absolute",
        "market_age_seconds",
        "position_age_wall_s",
        "period",
        "game_seconds_remaining",
        "score_differential_from_A1",
        "is_A1_team_offense",
    ],
    "M3": [
        "current_price",
        "entry_price",
        "deterioration_absolute",
        "market_age_seconds",
        "position_age_wall_s",
        "period",
        "game_seconds_remaining",
        "score_differential_from_A1",
        "is_A1_team_offense",
        "possession_index",
        "possessions_since_entry",
        "estimated_possessions_remaining_r2",
    ],
    "M3_NO_REM": [
        "current_price",
        "entry_price",
        "deterioration_absolute",
        "market_age_seconds",
        "position_age_wall_s",
        "period",
        "game_seconds_remaining",
        "score_differential_from_A1",
        "is_A1_team_offense",
        "possession_index",
        "possessions_since_entry",
    ],
    "M4": [
        "current_price",
        "entry_price",
        "deterioration_absolute",
        "market_age_seconds",
        "position_age_wall_s",
        "period",
        "game_seconds_remaining",
        "score_differential_from_A1",
        "is_A1_team_offense",
        "possession_index",
        "possessions_since_entry",
        "estimated_possessions_remaining_r2",
        "max_deterioration_since_entry",
        "recovery_from_max_drawdown",
        "distance_from_entry",
        "distance_from_prior_peak",
    ],
    "M5": [
        "current_price",
        "entry_price",
        "deterioration_absolute",
        "market_age_seconds",
        "position_age_wall_s",
        "period",
        "game_seconds_remaining",
        "score_differential_from_A1",
        "is_A1_team_offense",
        "possession_index",
        "possessions_since_entry",
        "estimated_possessions_remaining_r2",
        "max_deterioration_since_entry",
        "recovery_from_max_drawdown",
        "distance_from_entry",
        "distance_from_prior_peak",
        "v_3",
        "v_5",
        "a_short",
        "unique_market_observations_since_entry",
        "market_price_change_1_observation",
    ],
}

FAMILY_LAYER = {
    "B0": "MARKET_PRICE_ONLY",
    "B1": "MARKET_PLUS_WALL_AGE",
    "B2": "MARKET_PLUS_GAME_STATE",
    "M3": "MULTI_CLOCK_STATE",
    "M3_NO_REM": "MULTI_CLOCK_WITHOUT_REMAINING_ESTIMATE",
    "M4": "PATH_STATE",
    "M5": "DYNAMIC_STATE",
}

# Primary scientific targets. Saturated 5-poss 40-cross is a CONTROL only.
PRIMARY_TARGETS = [
    ("y_settle_yes", "P(Settle YES | X_n) — primary terminal"),
    ("y_rec_ge_10_k5", "P(recovery >=10c within 5 poss)"),
    ("y_rec_ge_10_end", "P(recovery >=10c to game end)"),
    ("y_rec_ge_5_k5", "P(recovery >=5c within 5 poss)"),
    ("y_rec_ge_20_k5", "P(recovery >=20c within 5 poss)"),
    ("y_det_ge_10_k5", "P(deterioration >=10c within 5 poss)"),
    ("y_det_ge_10_end", "P(deterioration >=10c to game end)"),
    ("y_min_le_50_k5", "P(future min <=50 within 5 poss) — non-trivial"),
    ("y_min_le_60_end", "P(future min <=60 to game end)"),
    ("y_jump_40", "P(observed jump-through-40 candle proxy) — NOT a fill"),
]

CONTROL_TARGETS = [
    ("y_min_le_40_k5", "CONTROL / SATURATED: P(min<=40 within 5 poss)"),
]

ALL_TARGETS = PRIMARY_TARGETS + CONTROL_TARGETS

FORBIDDEN_AS_FEATURES = frozenset(
    {
        "actual_remaining_possessions",
        "actual_remaining_possessions_eval_only",
        "terminal_pnl_hold",
        "expiration_result_yes",
    }
)


def feature_dictionary() -> list[dict]:
    rows = []
    seen = set()
    for fam, cols in FAMILIES.items():
        for c in cols:
            if c in seen:
                continue
            seen.add(c)
            rows.append(
                {
                    "feature_name": c,
                    "families": [f for f, cs in FAMILIES.items() if c in cs],
                    "layer": FAMILY_LAYER.get(fam),
                    "as_of": True,
                    "lookahead_forbidden": c in FORBIDDEN_AS_FEATURES or c.startswith("y_") or c.startswith("future_"),
                }
            )
    return rows
