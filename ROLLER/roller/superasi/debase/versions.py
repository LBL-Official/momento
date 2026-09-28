"""Phase B version tokens. Strategy payoff is Roller-dynamic."""

from roller.superasi.base.versions import (
    BANKROLL_FLOOR,
    DESK_PATHS,
    DESK_SEED,
    GRADE_CONFIG_VERSION,
    HONESTY,
    P_BE,
    P_DESK,
    RISK_PROFILE_WEEKS,
    TARGET_BANKROLL,
    WILSON_Z,
)

SUPERASI_DEBASE_VERSION = "superasi_bdebase_v1.1.0"

# Quartile hinge: Φ^{-1}(0.75). Wilson at this z is the IQR box [Q1, Q3].
WILSON_Z_IQR1 = 0.6744897501960817
P_WORKING_BASIS = "iqr1"
DEBASE_DESK_NOTE = "IQR 1 (Q1) as the mean. Worst-form Theoretical desk. Not DEBASE_GRADE."
DEBASE_MC_NOTE = "This Roller's R:R + IQR 1 as the mean. Worst-form Monte Carlo. Not DEBASE_GRADE."

INITIAL_BANKROLL = 20_000.0
ALLOCATION_RATE = 0.05
TRADES_PER_WEEK = 10
TARGET_WEEKLY_EV = 0.01
A_PLUS_RETURN = 0.67
A_PLUS_FLOOR = 0.055
EV_TOLERANCE = 1e-4

SENSITIVITY_P = (
    0.60,
    0.625,
    0.65,
    0.675,
    0.70,
    0.725,
    0.75,
    0.775,
    0.80,
)

PROGRAMS = ("base_decomposition", "base_degrading", "base_devalidation")
EVIDENCE_LAYERS = ("OBSERVED", "THEORETICAL", "MONTE_CARLO", "STRESS")
RECORD_TYPES = (
    "meta",
    "observed",
    "decomposition",
    "weekly",
    "weekly_observed",
    "grading",
    "degrading",
    "devalidation",
    "risk_profile",
    "comparison",
    "sensitivity",
    "stress",
    "path_bands",
)
