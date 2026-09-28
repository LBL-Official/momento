"""DRE V6 specification locks. Research only.

Does not write to PADE / DRE V2–V5 / FIRST01 / Risk / live config.
Implementation may not discover its own science.
"""

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

PROGRAM = "MOMENTO_DYNAMIC_RISK_ENGINE_V6"
SCHEMA_VERSION = "1.0.0"
RESEARCH_DATE = "2026-09-03"
LIVE_EXECUTION_CHANGED = False
RANDOM_SEED = 42

REPO = Path("/Users/user/Desktop/Momento")
NBA_SCRIPTS = REPO / "apps" / "nba-data" / "scripts"
WAREHOUSE = REPO / "Backtesting Suite" / "Data" / "NBA" / "2025-2026" / "warehouse"
V5_OUT = WAREHOUSE / "derived" / "nba" / "dynamic_risk_engine_v5"
V4_OUT = WAREHOUSE / "derived" / "nba" / "dynamic_risk_engine_v4"
V3_OUT = WAREHOUSE / "derived" / "nba" / "dynamic_risk_engine_v3"
V2_OUT = WAREHOUSE / "derived" / "nba" / "dynamic_risk_engine_v2"
PADE_OUT = WAREHOUSE / "derived" / "nba" / "possession_adjusted_deterioration_engine_v1"
OUT = WAREHOUSE / "derived" / "nba" / "dynamic_risk_engine_v6"
DASH_PUBLIC = REPO / "frontend" / "dre-v6" / "public" / "data"
DOCS = REPO / "docs" / "research"

UNITS = "cents_per_contract"
CONTRACTS_RESEARCH = 100
PRIMARY_PAYOFF = "pi_terminal"
SURFACE_WEIGHTING_PRIMARY = "TRADE_BALANCED"
SURFACE_WEIGHTING_SECONDARY = "STATE_OCCUPANCY_WEIGHTED"
OCCUPANCY_LABEL = "STATE_OCCUPANCY_WEIGHTED DIAGNOSTIC"

BOOTSTRAP_GAMES = 200
MIN_SIDE_TRADES = 15
N_DECILES = 10
IDENTITY_REL_TOL = 1e-9

# Pre-registered cuts. Do not replace after OOS.
MAGNITUDE_CUTS_CENTS = (1.0, 2.0, 5.0, 10.0)
CONCENTRATION_PCTS = (0.01, 0.05, 0.10, 0.25)
CONCENTRATION_VERDICT_PCT = 0.10
CONCENTRATION_VERDICT_SHARE = 0.40
MATERIAL_CENTS = 5.0
MATERIAL_INVENTORY_CENTS = MATERIAL_CENTS * CONTRACTS_RESEARCH  # 500¢ = $5.00
PERSISTENCE_K = 5.0
PERSISTENCE_MEDIAN_MIN = 3
BASELINE_ABS_CENTS = 1.0
TAIL_KS = (2.0, 5.0, 10.0)
PATH_K = 5.0

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

PADE_SHA256_PREFIX = {
    "05_trade_possession_panel.parquet": "90358b686356cec9",
    "06_state_features.parquet": "3faea9b4bb24b5a5",
    "07_forward_labels.parquet": "4074b3dace253866",
    "12_data_leakage_audit.parquet": "0d0d6f92b355542e",
    "14_manifest.json": "4cfa0845821f5e66",
    "03_possessions.parquet": "5682d436fa2e2396",
}
V2_SHA256_PREFIX = {
    "09_predictions/state_predictions.parquet": "90423de3c8f60d51",
    "run_manifest.json": "0dfcb4f13a64dbf6",
}
V3_SHA256_PREFIX = {
    "04_state_panel.parquet": "cba09b9410f3ab12",
    "19_oos_results.json": "ccdb87f081e0a38a",
    "20_run_manifest.json": "b4423b41f720f1ef",
}
V4_SHA256_PREFIX = {
    "03_state_panel.parquet": "2e09b7219e7c9b74",
    "15_discovery_verdict.json": "54c8af4bc77acf3f",
    "01_run_manifest.json": "eb66b13f519d4606",
    "NO_OOS_TUNING_AUDIT.json": "b9f6f71ce9ac8481",
    "04_universe_accounting.json": "8cf80641d54aa958",
    "07_leakage_audit.json": "fafe5e785497568e",
    "08_split_audit.json": "5a587ef816373ea4",
}

CONCENTRATION_NOT_EVIDENCE = (
    "A concentrated distribution of model disagreement is not evidence of "
    "predictive information unless the concentrated states also exhibit "
    "reproducible OOS separation in terminal payoff or M0 residual."
)

BANNER = (
    "RESEARCH ONLY — CANDLE PATH ≠ ACTUAL FILL — "
    "FORWARD DISTRIBUTION ≠ TRADABLE EDGE — "
    "CONDITIONAL ALPHA ≠ EXECUTABLE ACTION — "
    "Δα_state ≠ EDGE — "
    "100-CONTRACT LEDGER ≠ $50 PRODUCTION SIZE — "
    "LIVE DEPLOYMENT: NOT AUTHORIZED"
)

CENTRAL_QUESTION = (
    "When the frozen state-vector model disagrees with the frozen price-only model, "
    "does the terminal outcome subsequently deviate from the price-only expectation "
    "in the predicted direction?"
)

SPECIFICATION_LOCKS = {
    "program": PROGRAM,
    "schema_version": SCHEMA_VERSION,
    "frozen": True,
    "units": UNITS,
    "primary_payoff": PRIMARY_PAYOFF,
    "primary_relationship": "mean_SIR_i -> mean_M0_residual_i",
    "weighting": {
        "PRIMARY": SURFACE_WEIGHTING_PRIMARY,
        "SECONDARY": SURFACE_WEIGHTING_SECONDARY,
        "occupancy_label": OCCUPANCY_LABEL,
        "rule": "Trade-level mean_t is primary. Row-level residual-on-residual is diagnostic.",
    },
    "maps": {
        "M0": "TRAIN trade-balanced cell mean of pi_terminal by price_bin_5",
        "M1": "TRAIN trade-balanced cell mean by (price_bin_5, score_bin_l1, clock_bin_l1, n_hat_bin_l1)",
        "fallback": "missing M1 -> M0(price) -> TRAIN global trade-mean",
        "not": "V5 L2/L3 Lambda lookup maps",
    },
    "cuts": {
        "magnitude_cents": list(MAGNITUDE_CUTS_CENTS),
        "concentration_pcts": list(CONCENTRATION_PCTS),
        "concentration_verdict_pct": CONCENTRATION_VERDICT_PCT,
        "concentration_verdict_share": CONCENTRATION_VERDICT_SHARE,
        "material_cents": MATERIAL_CENTS,
        "material_inventory_cents": MATERIAL_INVENTORY_CENTS,
        "material_inventory_note": "5¢ × 100 contracts = 500¢ = $5.00 research-inventory displacement. Not realizable P&L.",
        "n_deciles": N_DECILES,
        "decile_cuts": "TRAIN-frozen on mean_SIR_i via pandas qcut; HALT if not exactly 10 distinct bins",
        "decile_assignment": "pd.cut include_lowest=True right=True on persisted TRAIN edges",
        "decile_outside_train_range": "CLIP_TO_TRAIN_EXTREMA: sir < e0 -> decile 1; sir > e10 -> decile 10",
        "tail_ks": list(TAIL_KS),
        "persistence_k": PERSISTENCE_K,
        "persistence_median_min": PERSISTENCE_MEDIAN_MIN,
        "baseline_abs_cents": BASELINE_ABS_CENTS,
    },
    "bootstrap": {"n": BOOTSTRAP_GAMES, "seed": RANDOM_SEED, "cluster": "event_id", "interval": "p05_p95"},
    "min_side_trades": MIN_SIDE_TRADES,
    "v5_published": V5_PUBLISHED,
    "concentration_not_evidence": CONCENTRATION_NOT_EVIDENCE,
    "no_post_oos_search": True,
    "verdict_module_only": "verdict.py",
    "note": "Frozen before TRAIN/VAL/OOS V6 tables. Do not edit after this write.",
}

OOS_REPLICATION_PROTOCOL = {
    "program": PROGRAM,
    "schema_version": SCHEMA_VERSION,
    "frozen": True,
    "written_before_oos_tables": True,
    "units": UNITS,
    "primary_estimand": SURFACE_WEIGHTING_PRIMARY,
    "helpers": {
        "ZERO_COMPATIBLE": "bootstrap_p05 <= 0 <= bootstrap_p95",
        "TRAIN_DIRECTION_COMPATIBLE": (
            "NOT (train_effect > 0 AND p95 < 0) AND NOT (train_effect < 0 AND p05 > 0)"
        ),
        "DIRECTIONAL": "sign(OOS)==sign(TRAIN); INCONCLUSIVE if TRAIN effect is 0",
        "VAL_CONFIRMATION_REQUIRED": "VAL coverage adequate for that object",
        "replication_directional": (
            "DIRECTIONAL AND TRAIN_DIRECTION_COMPATIBLE AND VAL_CONFIRMED AND adequate_train_oos"
        ),
        "note": "ZERO_COMPATIBLE and TRAIN_DIRECTION_COMPATIBLE are distinct. Do not conflate.",
    },
    "coverage": {
        "min_side_trades": MIN_SIDE_TRADES,
        "thin": "INCONCLUSIVE, not FAIL",
    },
    "headline_priority": ["D", "C", "B", "A"],
    "headline_rules": {
        "A": "OOS rank-spread ZERO_COMPATIBLE AND OOS residual-spread ZERO_COMPATIBLE AND P(|mean_SIR_i|>=5¢)<0.05",
        "B": "residual replication_directional AND (top10 share < 0.40 OR P(|mean_SIR_i|>=5¢)<0.05)",
        "C": "(top10 share >= 0.40 OR P(|mean_SIR_i|>=5¢)>=0.05) AND (rank OR residual replication_directional). Concentration alone is insufficient.",
        "D": "C AND OOS rank spread >= 5¢ AND rank replication_directional AND residual replication_directional AND k=5 median duration >= 3 among trades that ever exceed 5¢",
    },
    "d_ceiling": (
        "V6-D means concentrated, persistent, reproducible deviation from the price-only "
        "expectation. It does not establish expected trading profit >= 5¢."
    ),
    "forbidden_in_headline": ["pi_40_framework", "candle_path", "descriptive_oos_maps"],
    "no_threshold_search": True,
    "decile_outside_train_range": "CLIP_TO_TRAIN_EXTREMA: sir < e0 -> decile 1; sir > e10 -> decile 10",
    "unclassified": "If A/B/C/D none fire: HALT UNCLASSIFIED_PRE_REGISTERED_OUTCOME. Do not silently classify as A.",
}

NO_OOS_TUNING_AUDIT = {
    "gate": "F",
    "status": "PASS",
    "oos_used": False,
    "selected_hyperparameters": (
        "none — 1/2/5/10¢, deciles, top 1/5/10/25%, 40% concentration rule, "
        "5¢ materiality, persistence k=5 duration>=3 pre-registered"
    ),
    "protocol_written_before_oos_tables": True,
    "note": "No search. TRAIN-frozen maps and TRAIN-frozen decile cuts only. OOS is the scientific test.",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_prefix(path: Path, n: int = 16) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:n]


def log(msg: str) -> None:
    print(f"[DRE_V6] {msg}", file=sys.stderr, flush=True)


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


def close(a, b, rel=IDENTITY_REL_TOL) -> bool:
    if a is None or b is None:
        return False
    return math.isclose(float(a), float(b), rel_tol=rel, abs_tol=1e-12)
