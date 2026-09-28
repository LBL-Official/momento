"""Jump catalog version tokens. Observation only."""

CATALOG_VERSION = "jump_catalog_v1.0.0"
UNATTRIBUTED = "UNATTRIBUTED"
MATCH_TS_TOLERANCE_SECONDS = 5
DEMO_SECRET_ID = "momento/kalshi/demo"
PRODUCTION_SECRET_ID = "momento/kalshi/production"

HONESTY = {
    "browser_is_not_engine": True,
    "candle_path_not_fill": True,
    "jump_ae": "apps/trading-engine + Risk + mlb_factory_v1",
    "live_ev": "UNAVAILABLE",
    "unmatched": UNATTRIBUTED,
    "demo_not_added_to_live": True,
    "empty_unread_not_zero": True,
    "fill_result_sum_is_not_account_pnl": True,
}

CAVEATS = (
    "BROWSER IS NOT THE ENGINE",
    "CANDLE PATH ≠ ACTUAL FILL",
    "JUMP-AE = EXISTING ENGINE + RISK",
    "UNMATCHED KALSHI FILL = UNATTRIBUTED",
    "DEMO CENTS NOT ADDED TO LIVE",
    "MISSING BOOK = OBSERVATION_UNAVAILABLE",
    "FILL RESULT SUM ≠ ACCOUNT PNL",
    "HEADLINE PNL = CURRENT BANKROLL − $50 ORIGIN",
)
