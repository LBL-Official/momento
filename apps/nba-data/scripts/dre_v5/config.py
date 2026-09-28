"""DRE V5 constants and specification locks. Research only.

Never writes to PADE / DRE V2 / DRE V3 / DRE V4.
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

PROGRAM = "MOMENTO_DYNAMIC_RISK_ENGINE_V5"
SCHEMA_VERSION = "1.0.0"
RESEARCH_DATE = "2026-09-03"
LIVE_EXECUTION_CHANGED = False
RANDOM_SEED = 42

REPO = Path("/Users/user/Desktop/Momento")
NBA_SCRIPTS = REPO / "apps" / "nba-data" / "scripts"
NCAAB_SCRIPTS = REPO / "apps" / "ncaab-data" / "scripts"
WAREHOUSE = REPO / "Backtesting Suite" / "Data" / "NBA" / "2025-2026" / "warehouse"
NORM = WAREHOUSE / "normalized" / "nba"
CANDLES_DIR = NORM / "candles_1m"
PADE_OUT = WAREHOUSE / "derived" / "nba" / "possession_adjusted_deterioration_engine_v1"
V2_OUT = WAREHOUSE / "derived" / "nba" / "dynamic_risk_engine_v2"
V3_OUT = WAREHOUSE / "derived" / "nba" / "dynamic_risk_engine_v3"
V4_OUT = WAREHOUSE / "derived" / "nba" / "dynamic_risk_engine_v4"
OUT = WAREHOUSE / "derived" / "nba" / "dynamic_risk_engine_v5"
DASH_PUBLIC = REPO / "frontend" / "dre-v5" / "public" / "data"
DOCS = REPO / "docs" / "research"

GATES_F80 = {"n": 1230, "survivors": 910, "stops": 320, "leaks": 0, "surv_pct": 73.9837}
UNIVERSE_N = 1230
PANEL_TRADES_EXPECTED = 1221
PANEL_ROWS_EXPECTED = 139966
UNRESOLVED_EXPECTED = 9
CONTRACTS_RESEARCH = 100
ENTRY_PRICE_CENTS = 80
# V_mtm_cents = Q * P_A1_cents. Never possessions. At entry: 100 * 80 = 8000 cents.
V_MTM_ENTRY_CENTS = CONTRACTS_RESEARCH * ENTRY_PRICE_CENTS
DELTA_INV = 100
BRANCH_THRESHOLD_CENTS = 40
PRICE_DOMAIN_CENTS = (0, 100)
REG_GAME_S = 2880.0
UNITS = "cents_per_contract"

PADE_REQUIRED = (
    "05_trade_possession_panel.parquet",
    "06_state_features.parquet",
    "07_forward_labels.parquet",
    "12_data_leakage_audit.parquet",
    "14_manifest.json",
    "03_possessions.parquet",
)
PADE_SHA256_PREFIX = {
    "05_trade_possession_panel.parquet": "90358b686356cec9",
    "06_state_features.parquet": "3faea9b4bb24b5a5",
    "07_forward_labels.parquet": "4074b3dace253866",
    "12_data_leakage_audit.parquet": "0d0d6f92b355542e",
    "14_manifest.json": "4cfa0845821f5e66",
    "03_possessions.parquet": "5682d436fa2e2396",
}
V4_REQUIRED = (
    "03_state_panel.parquet",
    "15_discovery_verdict.json",
    "01_run_manifest.json",
    "NO_OOS_TUNING_AUDIT.json",
    "04_universe_accounting.json",
    "07_leakage_audit.json",
    "08_split_audit.json",
)
V4_SHA256_PREFIX = {
    "03_state_panel.parquet": "2e09b7219e7c9b74",
    "15_discovery_verdict.json": "54c8af4bc77acf3f",
    "01_run_manifest.json": "eb66b13f519d4606",
    "NO_OOS_TUNING_AUDIT.json": "b9f6f71ce9ac8481",
    "04_universe_accounting.json": "8cf80641d54aa958",
    "07_leakage_audit.json": "fafe5e785497568e",
    "08_split_audit.json": "5a587ef816373ea4",
}

# Lock 1
SURFACE_WEIGHTING_PRIMARY = "TRADE_BALANCED"
SURFACE_WEIGHTING_SECONDARY = "STATE_OCCUPANCY_WEIGHTED"

# Lock 6 — prior pace
PACE_K = 10
PACE_MIN_GAMES = 3
PACE_RX_IDENTITY = "PACE_A1_PLUS_PACE_A2"
PACE_CHRONOLOGY = "COMPLETED_BEFORE_G_START_WALL_END_TS"
POSSESSION_ROW_IS_OFFENSIVE = True

MIN_CELL_ROWS = 50
MIN_CELL_TRADES = 15
BOOTSTRAP_GAMES = 200
# Frozen once. Do not retune after seeing OOS.
MAE_MATERIAL_CENTS = 0.5
MAGNITUDE_BAND = (0.5, 2.0)
PRIMARY_PAYOFF = "pi_terminal"
DIAGNOSTIC_PAYOFF_40 = "pi_40_framework"

# Pre-registered L1 / L2 / L3 (TRAIN/VAL only; not OOS-tuned)
PRICE_BIN_CENTS = 5
PRICE_BIN_L2_CENTS = 10
PRIMARY_PRICE_LO = 60
PRIMARY_CONTRASTS = (
    {
        "id": "L3_clock_early_late_60",
        "level": "L3",
        "slice": "clock",
        "price_lo": 60,
        "price_width": 5,
        "a": "early",
        "b": "late",
        "direction": "b_minus_a",
    },
    {
        "id": "L3_score_lead_trail_60",
        "level": "L3",
        "slice": "score",
        "price_lo": 60,
        "price_width": 5,
        "a": "tie_trail",
        "b": "lead",
        "direction": "b_minus_a",
    },
    {
        "id": "L3_nhat_high_low_60",
        "level": "L3",
        "slice": "n_hat",
        "price_lo": 60,
        "price_width": 5,
        "a": "low",
        "b": "high",
        "direction": "b_minus_a",
    },
)

CLOCK_L1 = ("Q1_Q2", "Q3", "Q4_GT6", "Q4_2_6", "Q4_LT2", "OT")
# Frozen L2 clock. OT is not folded into LATE.
CLOCK_L2 = ("early", "late", "OT")
CLOCK_L2_FROM_L1 = {
    "Q1_Q2": "early",
    "Q3": "early",
    "Q4_GT6": "late",
    "Q4_2_6": "late",
    "Q4_LT2": "late",
    "OT": "OT",
}
SCORE_L1 = ("ge_p10", "p5_9", "p1_4", "zero", "m1_4", "le_m5")
NHAT_L1 = ("high", "mid", "low")

FEATURE_COLS = (
    "possession_index",
    "possessions_since_entry",
    "n_hat_remaining_prior",
    "is_A1_team_offense",
    "score_differential_from_A1",
    "d_sd_1",
    "d_sd_3",
    "d_sd_5",
    "elapsed_game_seconds",
    "game_seconds_remaining",
    "clock_cluster_30s",
    "clock_bin_l1",
    "score_bin_l1",
    "n_hat_bin_l1",
    "price_bin_5",
    "A1_yes_bid_cents",
    "current_price_cents",
    "A2_yes_bid_cents",
    "rel_a1_a2_cents",
    "complement_residual_cents",
    "V_mtm_cents",
    "delta_inv",
    "sigma_P",
    "pace_a1_prior",
    "pace_a2_prior",
    "r_x_prior",
)

LABEL_COLS = (
    "y_settle_yes",
    "pi_terminal",
    "pi_mtm",
    "pi_40_framework",
    "actual_remaining_possessions",
    "y_min_le_40_k5",
    "y_min_le_40_end",
    "future_min_end",
    "already_in_branch_40",
    "at_risk_40",
    "y_future_hit_40",
)

FORBIDDEN_IN_FEATURES = (
    "actual_remaining",
    "future_min",
    "future_max",
    "future_det",
    "future_mae",
    "y_settle",
    "y_rec",
    "y_det",
    "y_min",
    "y_jump",
    "y_future",
    "pi_terminal",
    "pi_mtm",
    "pi_40",
    "path_class",
    "target_delta",
    "h_N",
    "h_E",
)

# Frozen once. Written to OOS_REPLICATION_PROTOCOL.json before any OOS table.
# Do not edit after the first production write.
OOS_REPLICATION_PROTOCOL = {
    "program": PROGRAM,
    "schema_version": SCHEMA_VERSION,
    "frozen": True,
    "written_before_oos_tables": True,
    "units": "cents_per_contract",
    "note": (
        "Persists OOS is not visual similarity. "
        "Do not require classical p<0.05 in both TRAIN and OOS. "
        "OOS is ~237 games. Mechanical double-significance is not the gate. "
        "This object is frozen. Implementation must not change thresholds after seeing results."
    ),
    "surface_weighting": {
        "PRIMARY": SURFACE_WEIGHTING_PRIMARY,
        "SECONDARY": SURFACE_WEIGHTING_SECONDARY,
        "rule": "No row count may implicitly determine the economic weighting of a conditional payoff estimate without being labeled.",
    },
    "primary_payoff": {
        "name": PRIMARY_PAYOFF,
        "formula": "100*Y - 80",
        "units": "cents_per_contract",
        "values": [20, -80],
        "never_realized": [0],
        "identity": "alpha_frozen = 100*p_settle_yes - 80",
        "quantiles": (
            "P10/P50/P90 are empirical under the quantile convention. "
            "They are not hardcoded. A realized payoff of 0 never occurs. "
            "Depending on p_settle, P10 is typically -80, P50 is -80 or +20, P90 is typically +20."
        ),
        "interpretation": (
            "Because the frozen terminal payoff has only two outcomes, the primary "
            "conditional payoff surface is an affine transformation of the conditional "
            "terminal settlement probability. V5 does not treat this identity as a defect."
        ),
    },
    "diagnostic_40_framework": {
        "name": DIAGNOSTIC_PAYOFF_40,
        "label": "CANDLE_PATH_PROXY",
        "disclaimer": "OBSERVED CANDLE PATH ≠ EXECUTED STOP",
        "formula": "-40 if path reaches P_A1_cents <= 40 else 100*Y-80",
        "forbidden_in": [
            "primary_alpha_headline",
            "discovery_lambda",
            "scientific_oos_lambda",
            "primary_gradient",
            "M0_M1",
            "central_scientific_verdict",
        ],
    },
    "inventory": {
        "Q": CONTRACTS_RESEARCH,
        "V_mtm_cents": "100 * P_A1_cents",
        "delta_inv": DELTA_INV,
        "not": "100 * offensive_possessions",
    },
    "clock_l2": {
        "EARLY": ["Q1_Q2", "Q3"],
        "LATE": ["Q4_GT6", "Q4_2_6", "Q4_LT2"],
        "OT": ["OT"],
        "note": "OT is separately flagged and is not folded into LATE. Early-vs-late contrasts exclude OT.",
    },
    "layers": {
        "directional": "sign(OOS) == sign(TRAIN); VAL same sign if VAL is adequate.",
        "magnitude": "report OOS_effect / TRAIN_effect; no requirement that it equal 1.",
        "uncertainty": (
            "game-clustered bootstrap (200, seed 42), 5th–95th percentile interval. "
            "Compatible with TRAIN direction iff the interval is not entirely on the opposite side of 0 from TRAIN."
        ),
    },
    "classification": {
        "ROBUST": (
            "adequate TRAIN and OOS (50 rows and 15 trades each side); "
            "sign(OOS)==sign(TRAIN); "
            "OOS/TRAIN magnitude ratio in [0.5, 2.0]; "
            "game-clustered bootstrap interval compatible with TRAIN direction; "
            "if VAL adequate, sign(VAL)==sign(TRAIN)."
        ),
        "PARTIAL": (
            "sign(OOS)==sign(TRAIN) but VAL flips, or ratio outside [0.5, 2.0], "
            "or bootstrap interval is compatible with direction but the ROBUST conjunction fails."
        ),
        "INCONCLUSIVE": "either side fails 50 rows and 15 trades, or TRAIN effect is ~0 so sign is undefined.",
        "FAIL": "adequate TRAIN and OOS coverage and sign(OOS) != sign(TRAIN).",
    },
    "magnitude_band": list(MAGNITUDE_BAND),
    "bootstrap": {
        "n": BOOTSTRAP_GAMES,
        "seed": RANDOM_SEED,
        "cluster": "event_id",
        "interval": "p05_p95",
        "compatibility": "interval is not entirely on the opposite side of 0 from TRAIN",
    },
    "min_display_cell": {"n_rows": MIN_CELL_ROWS, "n_unique_trades": MIN_CELL_TRADES},
    "contrasts": list(PRIMARY_CONTRASTS),
    "lambda": {
        "DISCOVERY": "TRAIN surface → TRAIN paths",
        "VALIDATION": "TRAIN-frozen surface → VAL paths",
        "SCIENTIFIC_OOS": "TRAIN-frozen surface → OOS paths. This is the scientific test.",
        "DESCRIPTIVE_OOS": "OOS-only surface → OOS paths. Descriptive evidence only. Never the scientific verdict.",
        "formula_scientific": "-(alpha_TRAIN(X_{t+1}) - alpha_TRAIN(X_t))",
        "formula_descriptive": "-(alpha_OOS(X_{t+1}) - alpha_OOS(X_t))",
        "not_claimed": "isolated partial alpha / partial tau",
        "payoff": PRIMARY_PAYOFF,
    },
    "price_dominance": {
        "M0": "alpha ~ A1 5-cent bins only",
        "M1": "alpha ~ A1 5-cent + score_l1 + clock_l1 + n_hat_l1",
        "fit": "TRAIN trade-balanced cell means",
        "trade_prediction": "hat_alpha_i = (1/T_i) * sum_t hat_alpha_TRAIN(X_it)",
        "mae_primary": "MAE = (1/N) * sum_i |Pi_i - hat_alpha_i|  (TRADE_BALANCED)",
        "mae_occupancy": "row-level MAE is STATE_OCCUPANCY_WEIGHTED DIAGNOSTIC only",
        "evaluate": "OOS trade-balanced MAE of predicted alpha vs realized pi_terminal",
        "material_mae_cents": MAE_MATERIAL_CENTS,
        "M1_beats_M0": (
            "(MAE_M0 - MAE_M1) >= 0.5 cents AND the game-clustered bootstrap "
            "5th–95th interval of (MAE_M0 - MAE_M1) lies entirely above 0."
        ),
        "meaning": (
            "Price dominance does not mean basketball state has zero association with payoff. "
            "It means additional state segmentation does not demonstrate sufficient reproducible "
            "information beyond the observed A1 price coordinate under the V5 protocol."
        ),
    },
    "headline_priority": ["A", "C", "B", "D"],
    "headline_rules": {
        "A": "At least one non-price L3 contrast ROBUST (clock or score at matched price) OR M1 beats M0.",
        "C": "L3 n_hat high vs low at [60,65) cents is ROBUST (may coexist; C is recorded even if A also holds).",
        "B": "M1 does not beat M0 AND at least one M0 price-bin contrast shows OOS structure (price bins differ).",
        "D": "No L2/L3 contrast ROBUST and M1 does not beat M0.",
    },
}

BANNER = (
    "RESEARCH ONLY — CANDLE PATH ≠ ACTUAL FILL — "
    "FORWARD DISTRIBUTION ≠ TRADABLE EDGE — "
    "CONDITIONAL ALPHA ≠ EXECUTABLE ACTION — "
    "100-CONTRACT LEDGER ≠ $50 PRODUCTION SIZE — "
    "LIVE DEPLOYMENT: NOT AUTHORIZED"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_prefix(path: Path, n: int = 16) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:n]


def log(msg: str) -> None:
    print(f"[DRE_V5] {msg}", file=sys.stderr, flush=True)


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


def e4_to_cents(v) -> float | None:
    if v is None:
        return None
    return float(v) / 100.0
