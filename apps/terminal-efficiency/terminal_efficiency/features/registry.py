"""Every feature must declare a point-in-time availability rule."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class FeatureMetadata:
    name: str
    source: str
    availability_rule: str
    family: str
    max_information_timestamp_field: str
    allowed_in_xib: bool = True


FEATURE_REGISTRY: dict[str, FeatureMetadata] = {}


def register(meta: FeatureMetadata) -> FeatureMetadata:
    FEATURE_REGISTRY[meta.name] = meta
    return meta


# --- in-game (event time <= prediction) ---
for _name, _src in (
    ("period", "pbp.period"),
    ("seconds_remaining_period", "pbp.clock"),
    ("seconds_remaining_game", "pbp.clock+period"),
    ("home_score", "pbp.scoreHome"),
    ("away_score", "pbp.scoreAway"),
    ("score_difference", "pbp.home-away"),
    ("possession_home", "possession.offensive_team"),
    ("current_run_home", "pbp.recent scores"),
    ("recent_possession_points", "possession.points"),
):
    register(
        FeatureMetadata(
            name=_name,
            source=_src,
            availability_rule="source_event_time <= prediction_timestamp",
            family="in_game",
            max_information_timestamp_field="game_event_timestamp",
        )
    )

# --- pregame (prior game end < target start) ---
for _name in (
    "home_games_played_pre",
    "away_games_played_pre",
    "home_win_pct_pre",
    "away_win_pct_pre",
    "home_wins_last5_pre",
    "away_wins_last5_pre",
    "home_wins_last10_pre",
    "away_wins_last10_pre",
    "home_ortg_pre",
    "away_ortg_pre",
    "home_drtg_pre",
    "away_drtg_pre",
    "home_net_rating_pre",
    "away_net_rating_pre",
    "home_pace_pre",
    "away_pace_pre",
    "home_efg_pre",
    "away_efg_pre",
    "home_tov_rate_pre",
    "away_tov_rate_pre",
    "home_orb_rate_pre",
    "away_orb_rate_pre",
    "home_ft_rate_pre",
    "away_ft_rate_pre",
    "home_sos_pre",
    "away_sos_pre",
    "home_rest_days",
    "away_rest_days",
    "est_possessions_remaining",
):
    register(
        FeatureMetadata(
            name=_name,
            source="prior completed games only",
            availability_rule="source_game_end_time < target_game_start_time",
            family="pregame",
            max_information_timestamp_field="feature_as_of_timestamp",
        )
    )

register(
    FeatureMetadata(
        name="player_availability",
        source="none",
        availability_rule="UNAVAILABLE — no verified PIT injury feed",
        family="player",
        max_information_timestamp_field="feature_as_of_timestamp",
        allowed_in_xib=False,
    )
)

# Kalshi prices are registered as FORBIDDEN for XIB/MCD
for _name in ("kalshi_yes_price_e4", "kalshi_no_price_e4", "yes_bid_close_e4"):
    register(
        FeatureMetadata(
            name=_name,
            source="kalshi candles_1m",
            availability_rule="alignment grid only — NEVER an XIB/MCD feature",
            family="market",
            max_information_timestamp_field="market_timestamp",
            allowed_in_xib=False,
        )
    )


def registry_records() -> list[dict]:
    return [asdict(m) for m in FEATURE_REGISTRY.values()]
