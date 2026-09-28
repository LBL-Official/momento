"""Locked Austin constants. Not a live trading rule."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AustinConfig:
    seed: int = 80
    model_version: str = "austin_v2"
    dataset_version: str = "choosin_nba_2q3q_604"
    feature_schema_version: str = "austin_features_v1"
    pca_version: str = "austin_pca_v1"
    knn_config: str = "euclidean_pca_k25"
    fee_model_version: str = "UNAVAILABLE"
    starting_bankroll_cents: int = 2_000_000
    entry_cents: int = 80
    stop_cents: int = 40
    gain_cents: int = 20
    hold_loss_cents: int = 80
    trigger_cents: int = 80
    hedge_price_cents: int = 40
    hedge_triggers: tuple[int, ...] = (42, 41)
    k_default: int = 25
    k_grid: tuple[int, ...] = (5, 10, 20, 25, 50, 100)
    pca_k: int = 5
    pca_compare: tuple[int, ...] = (2, 3, 5, 10)
    lookback_bars: tuple[int, ...] = (1, 2, 3, 5, 10)
    lookback_seconds: tuple[int, ...] = (30, 60, 120, 300)
    min_knn_coverage: float = 0.80
    distance_epsilon: float = 1e-6
    snapshot_stride: int = 1
    bands: tuple[int, ...] = (3, 4, 5)
    allocation_pct: tuple[int, ...] = (3, 4, 5)
    live_feed: str = "UNAVAILABLE"
    live_execution: bool = False
    data_mode: str = "HISTORICAL_QUERY"
    fill_status: str = "FILL_UNAVAILABLE"
    fee_status: str = "UNAVAILABLE"
    l2_status: str = "SOURCE_UNAVAILABLE"
    pbp_status: str = "PBP_SEQUENCE_NOT_PIT"
    reference_hedge_n: int = 1230
    default_knn: tuple[str, ...] = field(
        default_factory=lambda: (
            "entry_price_cents",
            "current_price_cents",
            "price_travel",
            "distance_from_80",
            "score_differential",
            "score_differential_travel",
            "score_travel",
            "time_since_entry",
            "seconds_remaining",
            "quarter",
            "quarter_progress",
            "price_x_score_diff",
            "score_diff_x_time",
            "entry_price_x_score_diff",
        )
    )


DEFAULT = AustinConfig()


def band_dollars(pct: int, *, bankroll_cents: int = DEFAULT.starting_bankroll_cents) -> int:
    return int(bankroll_cents) * int(pct) // 100 // 100


def band_contracts(pct: int, *, entry_cents: int = DEFAULT.entry_cents) -> int:
    dollars = band_dollars(pct)
    return int(dollars * 100) // int(entry_cents)


def hedge_capital_cents(contracts: int, *, hedge_cents: int = DEFAULT.hedge_price_cents) -> int:
    return int(contracts) * int(hedge_cents)
