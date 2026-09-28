"""Persistence audit identities. Not a transfer member. Not a policy."""

from __future__ import annotations

from roller.austin.experiments.ids import (
    AUDIT_ID,
    BOOTSTRAP_B,
    BOOTSTRAP_SEED,
    EV_DEFINITION,
    EXPERIMENT_A,
    EXPERIMENT_B,
    OBSERVATION_SCHEDULE,
    PHASE2_ID,
    SUITE_ID,
)

TEMPORARY_NEGATIVE_EV = "TEMPORARY_NEGATIVE_EV"
PERSISTENT_NEGATIVE_EV = "PERSISTENT_NEGATIVE_EV"
UNRESOLVED_NO_LATER_VALID_EV = "UNRESOLVED_NO_LATER_VALID_EV"

NEGATIVE_CLASSES = (
    TEMPORARY_NEGATIVE_EV,
    PERSISTENT_NEGATIVE_EV,
    UNRESOLVED_NO_LATER_VALID_EV,
)

LANDMARK_T0 = "NEGATIVE_AT_T0"
LANDMARK_T0_ONLY = "NEGATIVE_AT_T0_ONLY"
LANDMARK_T0_T1 = "NEGATIVE_AT_T0_T1"
LANDMARK_T0_T1_T2 = "NEGATIVE_AT_T0_T1_T2"
LANDMARK_T0_T1_T2_T3 = "NEGATIVE_AT_T0_T1_T2_T3"

LANDMARKS = (LANDMARK_T0, LANDMARK_T0_T1, LANDMARK_T0_T1_T2, LANDMARK_T0_T1_T2_T3)
PHASE = "PHASE_2"
PHASE_NAME = "PERSISTENCE MECHANISM"

LOCKED_DISCOVERY_HASH = {
    EXPERIMENT_A: "f7bc6280913c63a2a50cb5181b0c523c5492bbdb47da167d9639e2f867a87e36",
    EXPERIMENT_B: "699e6bb65fe4fa3dffc566b352f089c109ffadfb501b830e2c129f2e66450840",
}
LOCKED_CONFIRMATION_HASH = {
    EXPERIMENT_A: "4bc027bddba0f723b914b2d80e0ff49ae0eb0bff94711860e310737941e0f0e4",
    EXPERIMENT_B: "1ce8a0b2f3d3ee88d34cb0e4833cf3369aa776fc75bff912d7e2f3b2a4173c51",
}

UNAVAILABLE = "UNAVAILABLE"

PIT_KEYS = (
    "first_negative_EV",
    "EV_DEPTH_BELOW_ZERO",
    "EV_CHANGE_FROM_ENTRY",
    "EV_CHANGE_FROM_PREVIOUS",
    "EV_SLOPE_FROM_ENTRY",
    "CI_LOWER",
    "CI_UPPER",
    "CI_WIDTH",
    "CI_ENTIRELY_NEGATIVE",
    "CI_CROSSES_ZERO",
    "PRICE",
    "PRICE_TRAVEL",
    "SCORE_TRAVEL",
    "SCORE_DIFF_TRAVEL",
    "TIME_SINCE_ENTRY",
    "GAME_TIME_REMAINING",
    "ESS",
    "EFFECTIVE_NEIGHBORS",
    "MEAN_DISTANCE",
    "MEDIAN_DISTANCE",
    "FEATURE_COVERAGE",
)

FORBIDDEN_PIT_KEYS = frozenset(
    {
        "negative_ev_class",
        "eventual_outcome",
        "won",
        "pnl_hold_after_first_negative",
        "future_MAE",
        "future_MFE",
        "future_T40",
        "future_min_price",
        "future_max_price",
        "future_recover_ge_50",
        "future_recover_ge_60",
        "future_recover_ge_70",
        "future_recover_ge_80",
    }
)

__all__ = [
    "AUDIT_ID",
    "BOOTSTRAP_B",
    "BOOTSTRAP_SEED",
    "EV_DEFINITION",
    "EXPERIMENT_A",
    "EXPERIMENT_B",
    "OBSERVATION_SCHEDULE",
    "SUITE_ID",
    "PHASE2_ID",
    "TEMPORARY_NEGATIVE_EV",
    "PERSISTENT_NEGATIVE_EV",
    "UNRESOLVED_NO_LATER_VALID_EV",
]
