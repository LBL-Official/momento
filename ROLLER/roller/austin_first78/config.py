"""FIRST78→67 Austin constants. Parallel to the locked 80/40 config."""

from __future__ import annotations

from roller.austin.config import AustinConfig

KNN_NAMES = (
    "entry_price_cents",
    "current_price_cents",
    "price_travel",
    "distance_from_78",
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

CFG = AustinConfig(
    seed=78,
    model_version="austin_first78_v1",
    dataset_version="choosin_nba_2q3q_first78_67",
    feature_schema_version="austin_first78_features_v1",
    pca_version="austin_first78_pca_v1",
    knn_config="euclidean_pca_k25_distance_from_78",
    entry_cents=78,
    stop_cents=67,
    gain_cents=22,
    hold_loss_cents=78,
    trigger_cents=78,
    hedge_price_cents=67,
    hedge_triggers=(69, 68),
    default_knn=KNN_NAMES,
)

ENTRY_CENTS = 78
STOP_CENTS = 67
GAIN_CENTS = 22
HOLD_LOSS_CENTS = 78
EV_DEFINITION = "first78_67_candle_path"
EV_FORMULA = "22 if YES and no 67 stop; else 67−78; else −78"


def distance_from_78(entry_price_cents: float | None) -> float | None:
    if entry_price_cents is None:
        return None
    return float(entry_price_cents) - float(ENTRY_CENTS)
