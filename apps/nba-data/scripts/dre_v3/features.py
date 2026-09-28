"""As-of feature list. No future labels."""

from __future__ import annotations

from .config import FEATURE_COLS

FEATURE_NOTES = {
    "current_price": "PADE/DRE V2 as-of yes-bid cents",
    "deterioration_cents": "entry 80 minus current, as-of",
    "market_age_seconds": "staleness of the as-of candle",
    "period": "game period at possession n",
    "game_seconds_remaining": "game clock remaining, as-of",
    "score_differential_from_A1": "score from A1 perspective, as-of",
    "is_A1_team_offense": "possession team flag, as-of",
    "possessions_since_entry": "possession clock since FIRST-80 entry",
}

FORBIDDEN_FEATURES = (
    "future_min",
    "future_max",
    "y_settle",
    "y_rec",
    "y_det",
    "y_jump",
    "actual_remaining",
    "path_bin",
    "dd_",
    "uu_",
    "target_delta",
)
