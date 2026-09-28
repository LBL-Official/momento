"""DRE V4 constants. Research only. Never writes to PADE / DRE V2 / DRE V3."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

PROGRAM = "MOMENTO_DYNAMIC_RISK_ENGINE_V4"
SCHEMA_VERSION = "1.0.0"
RESEARCH_DATE = "2026-09-03"
LIVE_EXECUTION_CHANGED = False
RANDOM_SEED = 42

REPO = Path("/Users/user/Desktop/Momento")
NBA_SCRIPTS = REPO / "apps" / "nba-data" / "scripts"
NCAAB_SCRIPTS = REPO / "apps" / "ncaab-data" / "scripts"
WAREHOUSE = REPO / "Backtesting Suite" / "Data" / "NBA" / "2025-2026" / "warehouse"
PADE_OUT = WAREHOUSE / "derived" / "nba" / "possession_adjusted_deterioration_engine_v1"
V2_OUT = WAREHOUSE / "derived" / "nba" / "dynamic_risk_engine_v2"
V3_OUT = WAREHOUSE / "derived" / "nba" / "dynamic_risk_engine_v3"
OUT = WAREHOUSE / "derived" / "nba" / "dynamic_risk_engine_v4"
DASH_PUBLIC = REPO / "frontend" / "dre-v4" / "public" / "data"
DOCS = REPO / "docs" / "research"

GATES_F80 = {"n": 1230, "survivors": 910, "stops": 320, "leaks": 0, "surv_pct": 73.9837}
UNIVERSE_N = 1230
PANEL_TRADES_EXPECTED = 1221
PANEL_ROWS_EXPECTED = 139966
UNRESOLVED_EXPECTED = 9

PADE_REQUIRED = (
    "05_trade_possession_panel.parquet",
    "06_state_features.parquet",
    "07_forward_labels.parquet",
    "12_data_leakage_audit.parquet",
    "14_manifest.json",
)
PADE_SHA256_PREFIX = {
    "05_trade_possession_panel.parquet": "90358b686356cec9",
    "06_state_features.parquet": "3faea9b4bb24b5a5",
    "07_forward_labels.parquet": "4074b3dace253866",
    "12_data_leakage_audit.parquet": "0d0d6f92b355542e",
    "14_manifest.json": "4cfa0845821f5e66",
}
V2_REQUIRED = (
    "09_predictions/state_predictions.parquet",
    "run_manifest.json",
    "02_frozen_universe/gate_a.json",
    "14_diagnostics/unresolved.json",
)
V2_SHA256_PREFIX = {
    "09_predictions/state_predictions.parquet": "90423de3c8f60d51",
    "run_manifest.json": "0dfcb4f13a64dbf6",
}
V3_REQUIRED = (
    "04_state_panel.parquet",
    "19_oos_results.json",
    "20_run_manifest.json",
    "13_interior_solution_analysis.json",
)
V3_SHA256_PREFIX = {
    "04_state_panel.parquet": "cba09b9410f3ab12",
    "19_oos_results.json": "ccdb87f081e0a38a",
    "20_run_manifest.json": "b4423b41f720f1ef",
}

# Pre-registered matched-price spec. Not tuned on OOS.
PRIMARY = {
    "price_bin_cents": 5,
    "price_lo": 60,
    "horizon": "5",
    "slice_a": "early",
    "slice_b": "late",
    "min_rows": 50,
    "min_trades": 15,
    "min_abs_rate_delta": 0.08,
    "min_abs_median_dd": 3.0,
    "min_wasserstein_dd": 3.0,
}
ROBUST_BINS = (2, 5, 10)
NN_TOLERANCE = 1.0
BOOTSTRAP_GAMES = 200
PATH_CLASSES = (
    "SEVERE_DETERIORATION",
    "MODERATE_DETERIORATION",
    "STABLE_RANGE",
    "MODERATE_RECOVERY",
    "STRONG_RECOVERY_FIRST",
    "AMBIGUOUS_CANDLE_ORDER",
    "INSUFFICIENT_FORWARD_OBSERVATION",
)
POSS_HORIZONS = ("1", "3", "5", "10", "end")
CLOCK_HORIZONS = (60, 180, 300)

FEATURE_B0 = ["current_price"]
FEATURE_B1 = FEATURE_B0 + ["market_age_seconds", "unique_market_obs", "stale_market"]
FEATURE_B2 = FEATURE_B1 + ["game_seconds_remaining", "period", "score_differential_from_A1"]
FEATURE_M3 = FEATURE_B2 + ["possessions_since_entry", "est_remaining_r1", "is_A1_team_offense"]
FEATURE_M4 = FEATURE_M3 + ["deterioration_cents", "max_dd_since_entry", "recovery_from_trough"]
FEATURE_M5 = FEATURE_M4 + ["v_3", "a_short", "market_volatility"]
FAMILIES = {
    "B0": FEATURE_B0,
    "B1": FEATURE_B1,
    "B2": FEATURE_B2,
    "M3": FEATURE_M3,
    "M4": FEATURE_M4,
    "M5": FEATURE_M5,
}

BANNER = (
    "RESEARCH ONLY — CANDLE PATH ≠ ACTUAL FILL — "
    "FORWARD DISTRIBUTION ≠ TRADABLE EDGE — "
    "PREDICTIVE STATE ≠ EXECUTION SIGNAL — "
    "LIVE DEPLOYMENT: NOT AUTHORIZED"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_prefix(path: Path, n: int = 16) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:n]


def log(msg: str) -> None:
    print(f"[DRE_V4] {msg}", file=sys.stderr, flush=True)


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_clean(obj), indent=2, default=_json_default, allow_nan=False) + "\n")


def _json_clean(o):
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    if isinstance(o, dict):
        return {k: _json_clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json_clean(v) for v in o]
    return o


def _json_default(o):
    if isinstance(o, Path):
        return str(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        if math.isnan(float(o)) or math.isinf(float(o)):
            return None
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


def write_parquet_df(path: Path, df) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), path)
