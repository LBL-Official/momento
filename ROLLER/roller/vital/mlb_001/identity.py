"""MLB Bot 001 isolated identity. Not a shared mlb/ dump. Not a second engine."""

BOT_ID = "mlb-001"
BOT_ALIASES = ("mlb-bot-one",)
BOT_DISPLAY = "MLB Bot 001"
KIND = "grandfathered"
SPORT = "mlb"
ORDINAL = 1
PACKAGE = "roller.vital.mlb_001"
FOLDER = "research/vital/bots/mlb-001"

FACTORY_ID = "mlb_factory_v1"
FACTORY_VERSION = "mlb_factory_v1.0.0"
ENGINE_POINTER = "apps/trading-engine"
STRATEGY_POINTER = "strategies/mlb"
CONFIG_POINTER = "config/live.toml"
UNIT_POINTER = "deploy/momento-live.service"
SECRET_FETCH_POINTER = "deploy/m10-fetch-secret.sh"
FRONTEND_POINTER = "frontend/vital-terminal"
API_ROUTE_PREFIX = "/vital/bots/mlb-001"
SERVICE_NAME = "momento-live.service"
BINARY_NAME = "momento-trading-engine"
HOST_BINARY = "/usr/local/bin/momento-trading-engine"
HOST_CONFIG = "/var/lib/momento/config/live.toml"
HOST_STATE_DIR = "/var/lib/momento/state"
HOST_RUNTIME = "/var/lib/momento/state/live-runtime.json"
HOST_SNAPSHOT = "/var/lib/momento/state/weekly-snapshot.json"
HOST_KILL = "/var/lib/momento/state/KILL"
DOCUMENTED_INSTANCE_ID = "i-0f0849d5829476c31"
DOCUMENTED_REGION = "us-east-1"

FACTORY = {
    "factory_id": FACTORY_ID,
    "factory_version": FACTORY_VERSION,
    "name": "MLB Production Factory",
    "editable": False,
    "bankroll_cents": 5000,
    "allocation_bps": 1250,
    "per_game_cents": 625,
    "max_open_mlb_positions": 5,
    "min_entry_cents": 80,
    "preferred_entry_cents": 80,
    "max_entry_cents": 83,
    "confirm_cents": 81,
    "lock_cents": 89,
    "signal": "80_to_81_yes_bid",
    "order_type": "maker_only_post_only",
    "risk": "Risk Decision Engine",
    "engine_pointer": ENGINE_POINTER,
    "strategy_pointer": STRATEGY_POINTER,
    "notes": (
        "Stamped MLB desk facts. Vital does not reimplement the strategy. "
        "ITI is research lineage only and is not the live signal."
    ),
}
