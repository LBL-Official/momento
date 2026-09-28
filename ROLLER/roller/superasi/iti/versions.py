"""Ian Taleb Index version tokens. SuperASI owns ITI after Final Results."""

ITI_VERSION = "jump_a_iti_v1.0.0"
ITI_HOME = "superasi"
SLOT_COUNT = 25
STEP_RATE = 0.05
MAX_STEPS = 3
MIN_CENTS = 1
MAX_CENTS = 99
ORCHESTRATOR_BASELINE = "baseline"
ORCHESTRATOR_OPTIMIZED = "optimized"
DEFAULT_ORCHESTRATOR = ORCHESTRATOR_OPTIMIZED

HONESTY = {
    "risk_not": "candle_path_not_fill",
    "fees": "UNAVAILABLE",
    "slippage": "UNAVAILABLE",
    "fills": "UNAVAILABLE",
    "confirmation_2pct": "OPERATION_REQUIRED",
    "pyramiding": "OPERATION_REQUIRED",
    "live_execution": False,
}

CAVEATS = (
    "LIVE EXECUTION = FALSE",
    "CANDLE PATH ≠ ACTUAL FILL",
    "2% CONFIRMATION = OPERATION_REQUIRED",
    "PYRAMIDING = OPERATION_REQUIRED",
    "RECOMMENDED GRADE ≠ FILL",
)
