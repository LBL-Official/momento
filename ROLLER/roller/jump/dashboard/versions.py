"""Jump C — operating dashboard version tokens. Control surface only."""

DASHBOARD_VERSION = "jump_c_dashboard_v1.4.0"

HONESTY = {
    "browser_is_not_engine": True,
    "candle_path_not_fill": True,
    "iti_is_not_live_signal": True,
    "actual_not_expected": True,
    "live_execution": False,
    "execution_truth": "vital",
    "pnl": "VITAL_KALSHI_SPORTS_SHARD_MINUS_FACTORY_ORIGIN",
    "fill_result_sum_is_not_account_pnl": True,
    "kalshi": "VITAL_READ_ONLY_BOOK",
    "sharpe": "UNAVAILABLE",
    "ev": "UNAVAILABLE",
    "live_ev": "UNAVAILABLE",
    "fills": "CATALOG_HAS_FILLS_ONLY",
    "jump_ae": "apps/trading-engine + Risk + mlb_factory_v1",
    "demo_not_added_to_live": True,
    "demo_top_level_is_not_sports_collateral": True,
    "probe_is_not_desk_truth": True,
    "fees": "UNAVAILABLE",
}

CAVEATS = (
    "BROWSER IS NOT THE ENGINE",
    "CANDLE PATH ≠ ACTUAL FILL",
    "ACTUAL ≠ EXPECTED",
    "MISSING METRICS = UNAVAILABLE",
    "NEVER INVENT $0",
    "ITI LINEAGE ≠ LIVE SIGNAL",
    "JUMP C READS VITAL",
    "LIVE EV = UNAVAILABLE",
    "FILL RESULT SUM ≠ ACCOUNT PNL",
    "DEMO TOP-LEVEL ≠ SPORTS SHARD 3",
    "JUMP DOES NOT START momento-live.service",
    "DEMO CENTS NOT ADDED TO LIVE",
)
