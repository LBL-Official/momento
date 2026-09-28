"""DRE V7 specification locks. Research only. No V5/V6 writes. No M0/M1 fit."""

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

PROGRAM = "MOMENTO_DYNAMIC_RISK_ENGINE_V7"
SCHEMA_VERSION = "1.0.0"
RESEARCH_DATE = "2026-09-03"
LIVE_EXECUTION_CHANGED = False
RANDOM_SEED = 42

REPO = Path("/Users/user/Desktop/Momento")
NBA_SCRIPTS = REPO / "apps" / "nba-data" / "scripts"
WAREHOUSE = REPO / "Backtesting Suite" / "Data" / "NBA" / "2025-2026" / "warehouse"
V5_OUT = WAREHOUSE / "derived" / "nba" / "dynamic_risk_engine_v5"
V6_OUT = WAREHOUSE / "derived" / "nba" / "dynamic_risk_engine_v6"
PADE_OUT = WAREHOUSE / "derived" / "nba" / "possession_adjusted_deterioration_engine_v1"
OUT = WAREHOUSE / "derived" / "nba" / "dynamic_risk_engine_v7"
DASH_PUBLIC = REPO / "frontend" / "dre-v7" / "public" / "data"
DOCS = REPO / "docs" / "research"

UNITS = "cents_per_contract"
PRIMARY_PAYOFF = "pi_terminal"
SURFACE_WEIGHTING_PRIMARY = "TRADE_BALANCED"
OCCUPANCY_LABEL = "STATE_OCCUPANCY_WEIGHTED DIAGNOSTIC"
CELL_LABEL = "CELL_GEOMETRY_DIAGNOSTIC"
STABILITY_LABEL = "TEMPORAL_STABILITY_DIAGNOSTIC"

BOOTSTRAP_GAMES = 200
MIN_SIDE_TRADES = 15

MAGNITUDE_CUTS_CENTS = (1.0, 2.0, 5.0, 10.0)
EXTREME_KS = (5.0, 10.0)
BASELINE_ABS_CENTS = 1.0
SPARSE_UNIQUE_TRADES = 4
STABILITY_MIN_TRADES = 10

SUPPORT_STRATA = (
    ("0", 0, 0),
    ("1", 1, 1),
    ("2-4", 2, 4),
    ("5-9", 5, 9),
    ("10-19", 10, 19),
    ("20-49", 20, 49),
    ("50+", 50, 10**9),
)

SPLITS = ("TRAIN", "VALIDATION", "OOS")
PANEL_TRADES_EXPECTED = 1221
PANEL_ROWS_EXPECTED = 139966
SPLIT_GAMES_EXPECTED = {"TRAIN": 503, "VALIDATION": 481, "OOS": 237}

V5_PUBLISHED = {
    "headline": "B",
    "mae_m0_oos": 20.55697546313149,
    "mae_m1_oos": 20.12797948988682,
    "delta_mae_oos": 0.4289959732446711,
    "n_m0_cells": 20,
    "n_m1_cells": 584,
}
V6_STATUS = "UNCLASSIFIED_PRE_REGISTERED_OUTCOME"

PROMINENT = (
    "An observed state is not necessarily a well-supported state; "
    "a well-populated state is not necessarily independently supported; "
    "and an exactly scored state is not necessarily supported by a robust empirical distribution."
)

SUPPORT_NOT_INDEPENDENCE = (
    "UNIQUE_TRADE_SUPPORT ≠ STATISTICAL_INDEPENDENCE. "
    "N_EFF_TRADE = OCCUPANCY CONCENTRATION MEASURE ≠ INDEPENDENT SAMPLE SIZE."
)

R_BAR_FORMULA = (
    "r_bar_i = Pi_i - mean_t alpha_M0_it, "
    "where mean_t alpha_M0_it = (1/T_i) sum_t alpha_M0_it. "
    "One residual per trade. Repeated possessions are not independent terminals."
)

BANNER = (
    "RESEARCH ONLY — Δα_state ≠ EDGE — "
    "CONDITIONAL INFORMATION ≠ EXECUTION — "
    "REPEATED POSSESSIONS ≠ INDEPENDENT OUTCOMES — "
    "LIVE DEPLOYMENT: NOT AUTHORIZED"
)

CENTRAL_QUESTION = (
    "Does the V6 disagreement structure survive when viewed through "
    "unique-trade support rather than possession occupancy?"
)

SPECIFICATION_LOCKS = {
    "program": PROGRAM,
    "schema_version": SCHEMA_VERSION,
    "frozen": True,
    "units": UNITS,
    "prominent": PROMINENT,
    "support_not_independence": SUPPORT_NOT_INDEPENDENCE,
    "r_bar_formula": R_BAR_FORMULA,
    "weighting": {
        "TRADE_BALANCED": SURFACE_WEIGHTING_PRIMARY,
        "occupancy": OCCUPANCY_LABEL,
        "cell": CELL_LABEL,
        "stability": STABILITY_LABEL,
    },
    "maps": {
        "source": "V6 02_train_frozen_m0_m1.json",
        "n_m0": 20,
        "n_m1": 584,
        "no_refit": True,
        "m0_m1_calls": 0,
    },
    "support_strata": [{"id": a, "lo": b, "hi": c} for a, b, c in SUPPORT_STRATA],
    "sparse_unique_trades": SPARSE_UNIQUE_TRADES,
    "stability_min_trades": STABILITY_MIN_TRADES,
    "magnitude_cents": list(MAGNITUDE_CUTS_CENTS),
    "extreme_ks": list(EXTREME_KS),
    "baseline_abs_cents": BASELINE_ABS_CENTS,
    "scoring_path": ["M1_EXACT", "M0_FALLBACK", "GLOBAL_FALLBACK"],
    "four_fields": ["EXACT_CELL_EXISTS", "TRAIN_UNIQUE_TRADE_SUPPORT", "N_EFF_TRADE", "SCORING_PATH"],
    "bootstrap": {
        "n": BOOTSTRAP_GAMES,
        "seed": RANDOM_SEED,
        "cluster": "event_id",
        "interval": "p05_p95",
        "meaning": "Variation under resampling of observed game-level clusters. Not a population causal CI.",
    },
    "min_side_trades": MIN_SIDE_TRADES,
    "shift_metric": "total_variation = 0.5 * sum |p-q|",
    "synthesis_tokens": [
        "SUPPORT_SPARSE_PATTERN",
        "SUPPORT_STABLE_PATTERN",
        "DISTRIBUTION_SHIFT_PATTERN",
        "MIXED_EVIDENCE",
        "UNRESOLVED",
    ],
    "no_v7_letters": True,
    "note": "Frozen before VAL/OOS outcome tables. Do not edit after this write.",
}

OOS_REPLICATION_PROTOCOL = {
    "program": PROGRAM,
    "frozen": True,
    "written_before_oos_outcome_tables": True,
    "primary_question": CENTRAL_QUESTION,
    "r_bar_formula": R_BAR_FORMULA,
    "gate_j": (
        "Apply V6 decile edges to mean_da_i only if source=TRAIN mean_SIR_i, "
        "unit=trade, transform=qcut, CLIP_TO_TRAIN_EXTREMA. Else NOT_APPLICABLE."
    ),
    "coverage": {"min_side_trades": MIN_SIDE_TRADES, "thin": "INCONCLUSIVE"},
    "bootstrap": SPECIFICATION_LOCKS["bootstrap"],
    "no_threshold_search": True,
    "no_refit": True,
    "synthesis_not_verdict_letters": True,
}

NO_OOS_TUNING_AUDIT = {
    "gate": "F",
    "status": "PASS",
    "oos_used": False,
    "selected_hyperparameters": (
        "none — strata 0/1/2-4/5-9/10-19/20-49/50+, sparse<=4, stability>=10, "
        "1/2/5/10¢, TV, bootstrap 200/42/event_id pre-registered"
    ),
    "protocol_written_before_oos_outcome_tables": True,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_prefix(path: Path, n: int = 16) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:n]


def sha256_full(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def log(msg: str) -> None:
    print(f"[DRE_V7] {msg}", file=sys.stderr, flush=True)


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


def stratum_id(n_unique: int | None) -> str:
    if n_unique is None or int(n_unique) < 0:
        return "0"
    x = int(n_unique)
    for sid, lo, hi in SUPPORT_STRATA:
        if lo <= x <= hi:
            return sid
    return "50+"
