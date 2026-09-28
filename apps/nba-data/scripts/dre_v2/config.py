"""DRE V2 constants and paths. Research only. Does not write to PADE."""

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

PROGRAM = "MOMENTO_DYNAMIC_RISK_ENGINE_V2"
SHORT_NAME = "DRE_V2"
SCHEMA_VERSION = "1.0.0"
RESEARCH_DATE = "2026-09-03"
LIVE_EXECUTION_CHANGED = False
RANDOM_SEED = 42

REPO = Path("/Users/user/Desktop/Momento")
NBA_SCRIPTS = REPO / "apps" / "nba-data" / "scripts"
NCAAB_SCRIPTS = REPO / "apps" / "ncaab-data" / "scripts"
WAREHOUSE = REPO / "Backtesting Suite" / "Data" / "NBA" / "2025-2026" / "warehouse"
PADE_OUT = WAREHOUSE / "derived" / "nba" / "possession_adjusted_deterioration_engine_v1"
OUT = WAREHOUSE / "derived" / "nba" / "dynamic_risk_engine_v2"
DASH_PUBLIC = REPO / "frontend" / "dre-v2" / "public" / "data"
DOCS = REPO / "docs" / "research"

GATES_F80 = {"n": 1230, "survivors": 910, "stops": 320, "leaks": 0, "surv_pct": 73.9837}
SPLIT_TRAIN_END = "2025-12-31"
SPLIT_VAL_END = "2026-03-15"
ENTRY_CENTS = 80
ENTRY_E4 = 8000
SETTLEMENT_YES_CENTS = 100
SETTLEMENT_NO_CENTS = 0

# PADE V1 files that must exist and must not be written by DRE.
PADE_REQUIRED = (
    "01_game_timeline.parquet",
    "02_pbp_events.parquet",
    "03_possessions.parquet",
    "04_market_game_alignment.parquet",
    "05_trade_possession_panel.parquet",
    "06_state_features.parquet",
    "07_forward_labels.parquet",
    "08_model_predictions.parquet",
    "09_model_metrics.parquet",
    "10_alignment_diagnostics.parquet",
    "11_remaining_possessions_diagnostics.parquet",
    "12_data_leakage_audit.parquet",
    "13_config.yaml",
    "14_manifest.json",
    "summary.json",
)

# Snapshot hashes recorded 2026-09-03 before DRE V2 (integrity, not a rewrite).
PADE_SHA256_PREFIX = {
    "05_trade_possession_panel.parquet": "90358b686356cec9",
    "06_state_features.parquet": "3faea9b4bb24b5a5",
    "07_forward_labels.parquet": "4074b3dace253866",
    "12_data_leakage_audit.parquet": "0d0d6f92b355542e",
    "14_manifest.json": "4cfa0845821f5e66",
}

DOWN_THRESHOLDS = (70, 60, 50, 40, 30)
RECOVERY_THRESHOLDS_CENTS = (5, 10, 20)
HORIZONS = (1, 3, 5, 10, "end")
H_GRID = tuple(round(i / 10, 2) for i in range(11))

# Frozen a priori. Not tuned on OOS.
LOGIT_C = 1.0
LOGIT_MAX_ITER = 400
LAMBDA_D_GRID = (0.0, 2.0, 5.0, 10.0, 20.0)
LAMBDA_R_GRID = (0.0, 2.0, 5.0, 10.0)
GAMMA_GRID = (0.0, 1.0, 2.0, 5.0)

USABLE_ALIGNMENT = frozenset({"HIGH", "MEDIUM"})

BANNER = (
    "RESEARCH ONLY — CANDLE PATH ≠ ACTUAL FILL — "
    "THEORETICAL TARGET DELTA ≠ EXECUTED DELTA — "
    "THEORETICAL EXPOSURE ≠ ACTUAL EXECUTION — "
    "LIVE DEPLOYMENT: NOT AUTHORIZED"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_prefix(path: Path, n: int = 16) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:n]


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=_json_default) + "\n")


def _json_default(o):
    if isinstance(o, Path):
        return str(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        if math.isnan(float(o)):
            return None
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


def write_parquet(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        pq.write_table(pa.table({"_empty": pa.array([], type=pa.int8())}), path)
        return
    clean = []
    for r in rows:
        c = {}
        for k, v in r.items():
            if isinstance(v, (dict, list, tuple)):
                c[k] = json.dumps(v, default=str)
            elif isinstance(v, (np.bool_,)):
                c[k] = bool(v)
            elif isinstance(v, (np.integer,)):
                c[k] = int(v)
            elif isinstance(v, (np.floating,)):
                fv = float(v)
                c[k] = None if math.isnan(fv) else fv
            else:
                c[k] = v
        clean.append(c)
    keys = {k for r in clean for k in r}
    for k in keys:
        types = {type(r.get(k)) for r in clean if r.get(k) is not None}
        if len(types) > 1:
            for r in clean:
                if r.get(k) is not None:
                    r[k] = str(r[k])
    pq.write_table(pa.Table.from_pylist(clean), path)


def read_parquet_rows(path: Path) -> list[dict]:
    table = pq.read_table(path)
    names = table.column_names
    if names == ["_empty"]:
        return []
    cols = {c: table.column(c) for c in names}
    n = table.num_rows
    return [{c: cols[c][i].as_py() for c in names} for i in range(n)]


def cents_to_e4(cents) -> int | None:
    if cents is None:
        return None
    return int(round(float(cents) * 100.0))


def log(msg: str) -> None:
    print(f"[DRE_V2] {msg}", file=sys.stderr, flush=True)
