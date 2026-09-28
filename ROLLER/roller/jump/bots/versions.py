"""Jump B — Bot Creation version tokens. Control plane only."""

BOTS_VERSION = "jump_b_bots_v1.0.0"
FACTORY_ID = "mlb_factory_v1"
FACTORY_VERSION = "mlb_factory_v1.0.0"
BOT_ONE_ID = "mlb-bot-one"
LIVE_CONFIRMATION = "ENABLE_LIVE_TRADING"
ENGINE_POINTER = "apps/trading-engine"
STRATEGY_POINTER = "strategies/mlb"
SERVICE_NAME = "momento-live.service"
BINARY_NAME = "momento-trading-engine"

HONESTY = {
    "browser_is_not_engine": True,
    "candle_path_not_fill": True,
    "iti_is_not_live_signal": True,
    "bot_one": "grandfathered",
    "new_bots_start": "DEMO",
    "live_execution": False,
    "confirmation_2pct": "OPERATION_REQUIRED",
    "pyramiding": "OPERATION_REQUIRED",
}

CAVEATS = (
    "BROWSER IS NOT THE ENGINE",
    "CANDLE PATH ≠ ACTUAL FILL",
    "JUMP-AE = EXISTING ENGINE + RISK",
    "ITI LINEAGE ≠ LIVE SIGNAL",
    "BOT ONE IS THE PRODUCTION FOUNDATION",
    "NEW BOTS START DEMO",
    "PRODUCTION REQUIRES TRIPLE LIVE GATE",
    "JUMP C = DASHBOARD",
    "UNMATCHED KALSHI FILL = UNATTRIBUTED",
)
