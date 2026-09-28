"""Frozen definitions and paths. Do not silently change FIRST80 or TOUCH40."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

PROGRAM = "FIRST80_ALPHA_DECOMPOSITION_V1"
SCHEMA_VERSION = "1.0.0"
RESEARCH_DATE = "2026-09-04"
LIVE_EXECUTION_CHANGED = False
RANDOM_SEED = 42
BOOTSTRAP_DRAWS = 200

REPO = Path("/Users/user/Desktop/Momento")
WAREHOUSE = REPO / "Backtesting Suite" / "Data" / "NBA" / "2025-2026" / "warehouse"
NORM = WAREHOUSE / "normalized" / "nba"
AUDIT = WAREHOUSE / "derived" / "nba" / "first80_execution_audit"
GPE_V2 = WAREHOUSE / "derived" / "nba" / "momento_game_path_engine_v2"
PADE = WAREHOUSE / "derived" / "nba" / "possession_adjusted_deterioration_engine_v1"
CANDLES = NORM / "candles_1m"

ROOT = REPO / "research" / "first80_alpha_decomposition_v1"
SRC = ROOT / "src"
DATA = ROOT / "data"
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
REPORTS = ROOT / "reports"
TESTS = ROOT / "tests"
DOCS = REPO / "docs" / "research" / "first80_alpha_decomposition_v1"
WH_OUT = WAREHOUSE / "derived" / "nba" / "first80_alpha_decomposition_v1"

BANNER = (
    "RESEARCH ONLY — OBSERVED CALIBRATION DEVIATION ≠ PROVEN MARKET INEFFICIENCY — "
    "TERMINAL ALPHA ≠ PATH ALPHA — PATH SURVIVAL ≠ INDEPENDENT EDGE — "
    "CONDITIONAL INFORMATION ≠ EXECUTABLE PROFIT — HISTORICAL CANDLE PATH ≠ ACTUAL FILL — "
    "HEDGE OPPORTUNITY ≠ LOCKED-IN ALPHA — LIVE EXECUTION = FALSE"
)

# Frozen close-path identity (nba_80_40_execution_audit.py). Do not rebuild.
FROZEN_GAMES = 1362
FROZEN_N = 1230
FROZEN_SURVIVORS = 910
FROZEN_STOPS = 320
FROZEN_NO80 = 132
FROZEN_WINS = 1019
FROZEN_LOSSES = 211
FROZEN_WIN_AND_NO40 = 910
FROZEN_WIN_AND_T40 = 109
FROZEN_LOSS_AND_NO40 = 0
FROZEN_LOSS_AND_T40 = 211
FROZEN_P_W = FROZEN_WINS / FROZEN_N
FROZEN_P_NOT40_GIVEN_W = FROZEN_WIN_AND_NO40 / FROZEN_WINS
FROZEN_P_JOINT = FROZEN_WIN_AND_NO40 / FROZEN_N

HIT80_E4 = 8000
HIT40_E4 = 4000
MAX_SPREAD_E4 = 1000
NULL_P_W = 0.80
ENTRY_CENTS = 80

THRESHOLDS_CENTS = (60, 65, 70, 75, 80, 85, 90, 95)
HEDGE_THRESHOLDS_CENTS = (5, 10, 15, 20, 25, 30)

# Frozen chronological splits from the execution audit. Do not retune on OOS.
SPLIT_RESEARCH_END = "2025-12-31"
SPLIT_VAL_END = "2026-03-15"
SPLIT_MAP = {"IN_SAMPLE": "TRAIN", "TRAIN": "TRAIN", "VALIDATION": "VALIDATION", "OOS": "OOS"}

# A priori matching bins. Locked before OOS inspection of matched tables.
SCORE_ABS_BINS = ((0, 4, "0-4"), (5, 9, "5-9"), (10, 19, "10-19"), (20, 10**9, "20+"))
CLOCK_BINS = ((0, 720, "Q4_LE12"), (721, 1440, "Q3ish"), (1441, 2160, "Q2ish"), (2161, 10**9, "EARLY"))

ACCEPTABLE = ("A_TERMINAL_CALIBRATION_ONLY", "B_PATH_EFFECT_ONLY", "C_BOTH", "D_INCONCLUSIVE")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str) -> None:
    print(f"[F80_DECOMP] {msg}", flush=True)


def canon_split(s: str | None) -> str:
    return SPLIT_MAP.get(s or "", s or "UNSPLIT")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_clean(obj), indent=2, default=str) + "\n")


def _clean(o):
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        x = float(o)
        return None if math.isnan(x) or math.isinf(x) else x
    return o


def write_parquet(path: Path, df) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), path)


def write_csv(path: Path, df) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


SPECIFICATION_LOCKS = {
    "program": PROGRAM,
    "schema_version": SCHEMA_VERSION,
    "frozen": True,
    "live_execution_changed": False,
    "banner": BANNER,
    "first80_definition": (
        "First tradable yes_bid_close >= 80¢ after a prior tradable close < 80¢, "
        "two-sided uncrossed spread <= 10¢, inside the game-day window. "
        "One observation per event: earliest timestamp; same-minute ties excluded. "
        "Source: apps/nba-data/scripts/nba_80_40_execution_audit.py. DO NOT REDEFINE."
    ),
    "touch40_definition": (
        "Primary T_40 = first subsequent completed candle AFTER the first-80 candle "
        "with tradable yes_bid_close <= 40¢ (stop_close_triggered / Y_40_CLOSE). "
        "Wick (yes_bid_low) is secondary and is not the primary research object."
    ),
    "W": "expiration_result_yes on the FIRST80 ticker (Kalshi YES settlement).",
    "null_terminal": NULL_P_W,
    "thresholds_cents": list(THRESHOLDS_CENTS),
    "hedge_thresholds_cents": list(HEDGE_THRESHOLDS_CENTS),
    "splits": {
        "TRAIN": f"game_date <= {SPLIT_RESEARCH_END}",
        "VALIDATION": f"{SPLIT_RESEARCH_END} < game_date <= {SPLIT_VAL_END}",
        "OOS": f"game_date > {SPLIT_VAL_END}",
        "source": "frozen execution-audit cuts; not retuned",
    },
    "matching_bins_locked": {
        "score_abs": [x[2] for x in SCORE_ABS_BINS],
        "quarter": ["1", "2", "3", "4", "OT"],
        "lead_state": ["LEAD", "TRAIL", "TIE"],
        "home": [True, False],
    },
    "classification_rules": {
        "terminal_distinguishable": (
            "One-sided exact binomial p-value vs p=0.80 < 0.05 on FULL, "
            "AND OOS point estimate > 0.80. Cluster bootstrap is reported; "
            "it does not by itself authorize a stronger claim."
        ),
        "independent_path": (
            "Among terminal winners, P(~T40|W, FIRST80) differs from FIRST75 and/or "
            "stratum-matched FIRST75 with an OOS interval on the difference that "
            "excludes 0. If the control is nearly identical to the treated set, "
            "the path test is INCONCLUSIVE."
        ),
        "letters": ACCEPTABLE,
        "do_not_tune_on_oos": True,
    },
    "not": [
        "true fair value",
        "executable fill",
        "locked-in alpha",
        "live trading",
        "proven market inefficiency",
    ],
}
