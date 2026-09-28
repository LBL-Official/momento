"""As-of feature families. No future labels. No h* / target_delta."""

from __future__ import annotations

from . import config as C

FORBIDDEN = (
    "future_min",
    "future_max",
    "future_det",
    "future_mae",
    "y_settle",
    "y_rec",
    "y_det",
    "y_min",
    "y_jump",
    "actual_remaining",
    "path_class",
    "dd_",
    "ue_",
    "dP_",
    "target_delta",
    "h_N",
    "h_E",
)

FEATURE_NOTES = {
    "current_price": "as-of YES bid cents",
    "market_age_seconds": "candle staleness",
    "unique_market_obs": "unique observed candles since entry",
    "stale_market": "market_age_seconds >= 60",
    "game_seconds_remaining": "game clock remaining (not used as a clock-horizon constructor)",
    "elapsed_game_seconds": "monotonic game-time clock",
    "period": "period as-of",
    "score_differential_from_A1": "score from A1",
    "possessions_since_entry": "possession clock",
    "est_remaining_r1": "PADE estimated remaining possessions (as-of)",
    "is_A1_team_offense": "possession team",
    "deterioration_cents": "entry 80 minus current",
    "max_dd_since_entry": "max deterioration since entry",
    "recovery_from_trough": "max_dd minus current det (as-of)",
    "v_3": "3-possession velocity if valid",
    "a_short": "short acceleration if valid",
    "market_volatility": "as-of rolling candle-path volatility",
}
