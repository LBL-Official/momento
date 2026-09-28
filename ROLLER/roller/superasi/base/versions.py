"""Phase A version tokens. Desk defaults are the measuring instrument."""

SUPERASI_BASE_VERSION = "superasi_abase_v1.0.0"
GRADE_CONFIG_VERSION = "grade_config_v1"

DESK_SEED = 20260913
DESK_PATHS = 100_000
RISK_PROFILE_WEEKS = 20
BANKROLL_FLOOR = 15_000.0
TARGET_BANKROLL = 30_000.0
P_DESK = 0.70
P_BE = 2.0 / 3.0
WILSON_Z = 1.96

HONESTY = {
    "risk_not": "candle_path_not_fill",
    "fees": "UNAVAILABLE",
    "slippage": "UNAVAILABLE",
    "fills": "UNAVAILABLE",
    "net_ev": "NOT_COMPUTABLE",
    "live_grade": "UNAVAILABLE",
}

EVIDENCE_LAYERS = ("OBSERVED", "THEORETICAL", "MONTE_CARLO")
RECORD_TYPES = (
    "meta",
    "observed",
    "composition",
    "weekly",
    "grading",
    "validation",
    "risk_profile",
    "comparison",
)
PROGRAMS = ("base_composition", "base_grading", "base_validation")
