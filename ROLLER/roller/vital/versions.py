"""Vital version tokens. Execution control plane. Not a second engine.

MLB Bot 001 identity lives in roller.vital.mlb_001.identity.
This module re-exports those tokens so existing imports stay stable.
"""

from roller.vital.mlb_001.identity import (
    BINARY_NAME,
    BOT_ALIASES,
    BOT_DISPLAY,
    BOT_ID,
    CONFIG_POINTER,
    DOCUMENTED_INSTANCE_ID,
    DOCUMENTED_REGION,
    ENGINE_POINTER,
    FACTORY,
    FACTORY_ID,
    FACTORY_VERSION,
    HOST_BINARY,
    HOST_CONFIG,
    HOST_KILL,
    HOST_RUNTIME,
    HOST_SNAPSHOT,
    HOST_STATE_DIR,
    KIND,
    SECRET_FETCH_POINTER,
    SERVICE_NAME,
    STRATEGY_POINTER,
    UNIT_POINTER,
)

CODE_VERSION = "vital_v1.2.0"
SCHEMA_VERSION = "vital_bot_v1"
LIVE_EXECUTION = False
INTEGRATION_PROOF = "LIVE_SERVICE_INTEGRATION"
INTEGRATION_PROOF_STATUS = "IMPLEMENTED"
CONTROL_CONFIRMATION = "VITAL_ENABLE_CONTROL"
LIVE_CONFIRMATION = "ENABLE_LIVE_TRADING"
DEMO_ACTIVATION_CONFIRMATION = "VITAL_ENABLE_DEMO"

LIFECYCLE = (
    "DRAFT",
    "CREATED",
    "DEPLOYING",
    "DEPLOYED",
    "STARTING",
    "RUNNING",
    "STOPPING",
    "STOPPED",
    "RESTARTING",
    "FAILED",
    "OBSERVATION_UNAVAILABLE",
    "KILLED",
)
ENVIRONMENTS = ("DEMO", "PRODUCTION")
HEALTH = ("HEALTHY", "DEGRADED", "UNHEALTHY", "UNKNOWN")
CONTROL_ACTIONS = ("deploy", "start", "stop", "restart", "kill")
COMMAND_STATUSES = (
    "ACCEPTED",
    "REJECTED",
    "DISPATCHED",
    "CONFIRMING",
    "CONFIRMED",
    "FAILED",
    "CONTROL_DISABLED",
)

PHASE_STATUS = {
    "1": "ACCEPTED",
    "2": "IMPLEMENTED",
    "3": "IMPLEMENTED",
    "4": "IMPLEMENTED",
    "5": "IMPLEMENTED",
    "6": "IMPLEMENTED",
    "7": "IMPLEMENTED",
    "S": "IMPLEMENTED",
    "8": "IMPLEMENTED",
    "9": "IMPLEMENTED",
}

CAVEATS = (
    "BROWSER IS NOT THE ENGINE",
    "HTTP 200 ≠ RUNNING",
    "DESIRED ≠ OBSERVED ≠ CONFIRMED",
    "START ≠ ENABLE_LIVE_TRADING",
    "KILL ≠ STOP",
    "KILL DOES NOT FLATTEN",
    "MISSING ≠ ZERO",
    "UNAVAILABLE ≠ INACTIVE",
    "UNOBSERVED ≠ HEALTHY",
    "LIVE EV = UNAVAILABLE",
    "SHARPE = UNAVAILABLE",
    "ITI IS NOT A LIVE SIGNAL",
    "NO SECOND ENGINE",
    "ORDER ≠ FILL ≠ TRADE",
    "UNREAD EXECUTION ≠ EMPTY HISTORY",
    "RUNNING ≠ HEALTHY ≠ EXECUTING",
    "DESIRED ≠ WRITTEN ≠ OBSERVED ≠ LOADED",
)

HONESTY = {
    "browser_is_not_engine": True,
    "http_200_not_running": True,
    "desired_observed_confirmed": True,
    "start_not_live_arm": True,
    "kill_not_stop": True,
    "kill_does_not_flatten": True,
    "missing_not_zero": True,
    "live_ev": "UNAVAILABLE",
    "sharpe": "UNAVAILABLE",
    "fees": "UNAVAILABLE",
    "slippage": "UNAVAILABLE",
    "live_execution": False,
    "secrets_in_api": False,
    "iti_is_not_live_signal": True,
    "jump_ae": "apps/trading-engine + Risk + mlb_factory_v1",
    "bot_one": "grandfathered",
    "demo_not_added_to_live": True,
    "order_not_fill": True,
    "candle_path_not_fill": True,
    "unread_execution_not_empty": True,
    "running_not_healthy": True,
    "healthy_not_executing": True,
    "desired_written_observed_loaded": True,
}
