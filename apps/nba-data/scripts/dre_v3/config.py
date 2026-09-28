"""DRE V3 constants. Research only. Never writes to PADE or DRE V2."""

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

PROGRAM = "MOMENTO_DYNAMIC_RISK_ENGINE_V3"
SHORT_NAME = "DRE_V3"
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
OUT = WAREHOUSE / "derived" / "nba" / "dynamic_risk_engine_v3"
DASH_PUBLIC = REPO / "frontend" / "dre-v3" / "public" / "data"
DOCS = REPO / "docs" / "research"

GATES_F80 = {"n": 1230, "survivors": 910, "stops": 320, "leaks": 0, "surv_pct": 73.9837}
SPLIT_TRAIN_END = "2025-12-31"
SPLIT_VAL_END = "2026-03-15"
ENTRY_CENTS = 80.0
SETTLE_YES = 100.0
SETTLE_NO = 0.0
X_YES = SETTLE_YES - ENTRY_CENTS  # +20 from entry
X_NO = SETTLE_NO - ENTRY_CENTS  # -80 from entry
# Experimental $50 bankroll in cents. Not a live bankroll instruction.
W0_CENTS = 5000.0

H_GRID = tuple(round(i * 0.05, 2) for i in range(21))
NEAR_OPT_ABS = 1e-8
NEAR_OPT_REL = 1e-6
FLAT_ABS = 1e-9
TIE_ABS = 1e-12

PATH_BINS = (
    "EXTREME_DOWN",
    "SEVERE_DOWN",
    "MODERATE_DOWN",
    "STABLE",
    "MODERATE_REC",
    "STRONG_REC",
    "EXTREME_REC",
)
HORIZONS = ("5", "10", "end")
# Representative candle-path excursions (cents) for each exclusive bin.
BIN_DD = {
    "EXTREME_DOWN": 35.0,
    "SEVERE_DOWN": 25.0,
    "MODERATE_DOWN": 15.0,
    "STABLE": 0.0,
    "MODERATE_REC": 0.0,
    "STRONG_REC": 0.0,
    "EXTREME_REC": 0.0,
}
BIN_UU = {
    "EXTREME_DOWN": 0.0,
    "SEVERE_DOWN": 0.0,
    "MODERATE_DOWN": 0.0,
    "STABLE": 0.0,
    "MODERATE_REC": 15.0,
    "STRONG_REC": 25.0,
    "EXTREME_REC": 35.0,
}

# Frozen a priori grids. Selected on VALIDATION only.
CRRA_GAMMA = (0.5, 1.0, 2.0, 3.0, 5.0, 10.0)
CARA_ALPHA_PER_DOLLAR = (0.005, 0.01, 0.02, 0.05)
CVAR_Q = (0.05, 0.10, 0.20)
LAMBDA_TAIL = (0.0, 0.25, 0.5, 1.0, 2.0)
LAMBDA_R = (0.0, 0.25, 0.5, 1.0)
LAMBDA_D = (0.0, 0.25, 0.5, 1.0)
N4_P = (2.0, 3.0)
N4_A = (0.01, 0.05, 0.20)
N4_B = (0.0, 0.05)

FEATURE_COLS = [
    "current_price",
    "deterioration_cents",
    "market_age_seconds",
    "period",
    "game_seconds_remaining",
    "score_differential_from_A1",
    "is_A1_team_offense",
    "possessions_since_entry",
]

PADE_REQUIRED = (
    "05_trade_possession_panel.parquet",
    "06_state_features.parquet",
    "07_forward_labels.parquet",
    "12_data_leakage_audit.parquet",
    "14_manifest.json",
    "summary.json",
)
PADE_SHA256_PREFIX = {
    "05_trade_possession_panel.parquet": "90358b686356cec9",
    "06_state_features.parquet": "3faea9b4bb24b5a5",
    "07_forward_labels.parquet": "4074b3dace253866",
    "12_data_leakage_audit.parquet": "0d0d6f92b355542e",
    "14_manifest.json": "4cfa0845821f5e66",
}
V2_REQUIRED = (
    "03_state_panel/dre_state_panel.parquet",
    "09_predictions/state_predictions.parquet",
    "08_models/model_metrics.parquet",
    "run_manifest.json",
    "11_exposure_surfaces/oos_policy_score.json",
    "02_frozen_universe/gate_a.json",
)
V2_SHA256_PREFIX = {
    "03_state_panel/dre_state_panel.parquet": "de42b6593ac6dbb0",
    "09_predictions/state_predictions.parquet": "90423de3c8f60d51",
    "08_models/model_metrics.parquet": "395360a2cf53a91f",
    "run_manifest.json": "0dfcb4f13a64dbf6",
    "11_exposure_surfaces/oos_policy_score.json": "d872ef25c61aa149",
}

BANNER = (
    "RESEARCH ONLY — CANDLE PATH ≠ ACTUAL FILL — "
    "THEORETICAL EXPOSURE ≠ EXECUTED EXPOSURE — "
    "MODELED STATE VALUE ≠ TRADABLE EDGE — "
    "LIVE DEPLOYMENT: NOT AUTHORIZED"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_prefix(path: Path, n: int = 16) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:n]


def log(msg: str) -> None:
    print(f"[DRE_V3] {msg}", file=sys.stderr, flush=True)


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
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, path)
