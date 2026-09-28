"""Jump version tokens. Research only."""

CODE_VERSION = "jump_v0.4.0"
SCHEMA_VERSION = "jump_dashboard_v1"
LIVE_EXECUTION = False
PHASES = ("A", "B", "C")
PHASE_STATUS = {
    "A": "MOVED_TO_SUPERASI",
    "B": "IMPLEMENTED",
    "C": "IMPLEMENTED",
}

CAVEATS = (
    "BROWSER IS NOT THE ENGINE",
    "CANDLE PATH ≠ ACTUAL FILL",
    "JUMP A = ITI MOVED TO SUPERASI",
    "JUMP B = BOT CREATION",
    "JUMP-AE = EXISTING ENGINE + RISK",
    "JUMP C = DASHBOARD",
    "MY BOTS = 05",
    "UNMATCHED KALSHI FILL = UNATTRIBUTED",
    "ACTUAL ≠ EXPECTED",
    "MISSING METRICS = UNAVAILABLE",
    "NEW BOTS START DEMO",
    "ITI LINEAGE ≠ LIVE SIGNAL",
    "2% CONFIRMATION = OPERATION_REQUIRED",
    "PYRAMIDING = OPERATION_REQUIRED",
)

HONESTY = {
    "risk_not": "candle_path_not_fill",
    "fees": "UNAVAILABLE",
    "slippage": "UNAVAILABLE",
    "fills": "UNAVAILABLE",
    "live_execution": False,
    "browser_is_not_engine": True,
    "desk_settings": "STAMPED_AT_RUN",
    "confirmation_2pct": "OPERATION_REQUIRED",
    "pyramiding": "OPERATION_REQUIRED",
    "bot_one": "grandfathered",
    "new_bots_start": "DEMO",
    "actual_not_expected": True,
    "jump_ae": "apps/trading-engine + Risk + mlb_factory_v1",
    "catalog_unmatched": "UNATTRIBUTED",
    "demo_not_added_to_live": True,
}
