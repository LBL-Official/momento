"""Capture Program v1 — research-only shared constants and economics.

Does not touch live trading, Risk, FIRST01, V1–V4, or the frozen audit.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
NBA_SCRIPTS = SCRIPTS_DIR.parent
if str(NBA_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(NBA_SCRIPTS))

ROOT = Path(
    "/Users/user/Desktop/Momento/Backtesting Suite/Data/NBA/2025-2026/warehouse"
)
AUDIT = ROOT / "derived" / "nba" / "first80_execution_audit"
OUT = ROOT / "derived" / "nba" / "momento_capture_program_v1"
SPEC_DIR = Path("/Users/user/Desktop/Momento/docs/research/nba/capture-program-v1")
SCHEMA_DIR = SCRIPTS_DIR / "schema"
EPISODES = OUT / "episodes"
REP = OUT / "reports"

DIR_BASELINE = OUT / "historical_path_baseline"
DIR_EXEC = OUT / "execution_scenarios"
DIR_FEE = OUT / "fee_scenarios"
DIR_FILL = OUT / "fill_models"
DIR_STOP = OUT / "stop_models"
DIR_CAP = OUT / "capacity"
DIR_PORT = OUT / "portfolio"
DIR_LEDGER = OUT / "live_ledger"
DIR_VAL = OUT / "validation"

PROGRAM_VERSION = "MOMENTO_NBA_CAPTURE_PROGRAM_V1"
SOURCE_DATASET_VERSION = "first80_execution_audit_2025-26_frozen"
ASSUMPTIONS_VERSION = "CAPTURE_ASSUMPTIONS_V1"
SEED = 20260901
N_MC = 100_000
BANKROLL0_CENTS = 1_000_000  # $10,000
ENTRY_CENTS = 80
SETTLE_WIN_CENTS = 100
R_UNIT_CENTS = 20  # +1R winner at 80→100

# Frozen close-path identity (must be reproduced, not recomputed from candles).
FROZEN_N = 1230
FROZEN_SURVIVORS = 910
FROZEN_STOPS_CLOSE = 320
FROZEN_P = FROZEN_SURVIVORS / FROZEN_N  # 0.739837...
FROZEN_GROSS_EV_R = 3.0 * FROZEN_P - 2.0  # +0.219512...
FROZEN_P_BE_GROSS = 2.0 / 3.0

# Conservative prior haircut — not a claim of the true rate.
PRIOR_P = 0.725
PRIOR_STRENGTH = 40.0  # pseudo-counts; mean 0.725 → α=29, β=11

# Frozen source hashes recorded at program start (STEP 1). Validation fails
# if these files change.
FROZEN_SHA256 = {
    "summary.json": "b5549b8a7e7d76ede6707b2576a142e4e67260ec824599ba1ee6b6e23a4ad0d7",
    "ledger_baseline.json": "884ff121705ae8f4495839bd1ecb63134f40df75fd7503f159f3352469ee640d",
    "ledger_conservative.json": "49a9199a8d512f60f5d72f52199343469470ef2908e2f19981e4cb18f70dd9a8",
    "candidates.json": "28f4b6acd87f952165b26a4925dcd56af8daee1c7ccf717580faf71c3a87078e",
    "rejected_conservative.json": "b0bb3ad1fd415270939086f4ed43f6d5ad86c4c37325a54fb9c2b740d0d3d56c",
    "REPORT.md": "58b6d697ee79069f28d6201b2d38ce63f0e4753bf3750ddf159bb5c84589b25f",
    "nba_80_40_execution_audit.py": "37c02aa9f5089d4d9e4f6242ba3ae4cd1e21488f5dd52e9dc9c998ab5681dd1f",
}

ALLOWED_STATUS = frozenset({"OBSERVED", "ESTIMATED", "SIMULATED", "UNAVAILABLE"})
STATUS_RANK = {
    "UNAVAILABLE": 0,
    "SIMULATED": 1,
    "ESTIMATED": 2,
    "OBSERVED": 3,
}

SURVIVAL_GRID = [round(x, 4) for x in [0.65 + 0.01 * i for i in range(11)]]
FILL_GRID = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5]
PARTIAL_GRID = [0.25, 0.50, 0.75, 1.00]
STOP_CENTS_GRID = [40, 39, 38, 35, 30]
FRACTIONS = [0.01, 0.02, 0.03, 0.05]
WEEKLY_TARGETS = [0.015, 0.020]

# Frozen overlap statistics — SIGNAL capacity, not executable fills.
SIGNAL_CAPACITY = {
    "cap_1": {"accepted": 505, "skipped": 725, "max_open_observed": 1},
    "cap_5": {"accepted": 1192, "skipped": 38, "max_open_observed": 5},
    "unlimited": {"accepted": 1230, "skipped": 0, "max_open_observed": 8},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def provenance(**extra) -> dict:
    row = {
        "program_version": PROGRAM_VERSION,
        "source_dataset_version": SOURCE_DATASET_VERSION,
        "created_at": utc_now(),
        "assumptions_version": ASSUMPTIONS_VERSION,
        "live_execution_changed": False,
        "observation_disclaimer": (
            "HISTORICAL PATH is not an executed fill. "
            "SIMULATED rows are assumption surfaces, not forecasts."
        ),
    }
    row.update(extra)
    return row


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n")


def load_json(path: Path):
    return json.loads(path.read_text())


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_dirs() -> None:
    for d in (
        DIR_BASELINE,
        DIR_EXEC,
        DIR_FEE,
        DIR_FILL,
        DIR_STOP,
        DIR_CAP,
        DIR_PORT,
        DIR_LEDGER,
        DIR_VAL,
        REP,
        EPISODES,
        OUT / "schema",
    ):
        d.mkdir(parents=True, exist_ok=True)


def write_parquet(path: Path, rows: list[dict]) -> None:
    import pandas as pd

    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)


def empty_parquet(path: Path, columns: list[str]) -> None:
    import pandas as pd

    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({c: [] for c in columns}).to_parquet(path, index=False)


def load_frozen_ledger() -> list[dict]:
    return load_json(AUDIT / "ledger_baseline.json")


def reproduce_counts(ledger: list[dict]) -> dict:
    n = len(ledger)
    survivors = sum(1 for r in ledger if r.get("winner_or_stop") == "WIN")
    stops = sum(1 for r in ledger if r.get("stop_triggered") is True)
    return {
        "n": n,
        "survivors": survivors,
        "stops_close": stops,
        "p_survive": survivors / n if n else None,
        "matches_frozen": n == FROZEN_N
        and survivors == FROZEN_SURVIVORS
        and stops == FROZEN_STOPS_CLOSE,
    }


def ev_gross_R(p: float) -> float:
    """EV = 3p − 2 at +1R / −2R."""
    return 3.0 * p - 2.0


def stop_loss_cents(stop_cents: int, entry_cents: int = ENTRY_CENTS) -> int:
    return entry_cents - stop_cents


def winner_cents(entry_cents: int = ENTRY_CENTS) -> int:
    return SETTLE_WIN_CENTS - entry_cents


def p_break_even(w: float, l_abs: float) -> float | None:
    den = w + l_abs
    if den <= 0:
        return None
    return l_abs / den


def ev_from_wl(p: float, w: float, l_abs: float) -> float:
    return p * w - (1.0 - p) * l_abs


def classify_region(ev_R: float) -> str:
    """Scenario labels, not production claims.

    A: EV_R ≥ 0.10 — robust under the stated assumptions
    B: 0 < EV_R < 0.10 — execution-sensitive
    C: EV_R ≤ 0 — structurally unprofitable under the stated assumptions
    """
    if ev_R <= 0:
        return "REGION_C_UNPROFITABLE"
    if ev_R < 0.10:
        return "REGION_B_EXECUTION_SENSITIVE"
    return "REGION_A_ROBUSTLY_PROFITABLE"


def allocated_return(pnl_cents: float, allocated_cents: float) -> float:
    if allocated_cents <= 0:
        return 0.0
    return pnl_cents / allocated_cents


def wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (float("nan"), float("nan"))
    p = successes / n
    z2 = z * z
    den = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / den
    rad = z * math.sqrt((p * (1.0 - p) + z2 / (4 * n)) / n) / den
    return (max(0.0, center - rad), min(1.0, center + rad))


def beta_mean(a: float, b: float) -> float:
    return a / (a + b)


def beta_median(a: float, b: float) -> float:
    # Closed-form is incomplete-beta inverse; use mean as fallback if scipy missing.
    try:
        from scipy.stats import beta as beta_dist

        return float(beta_dist.ppf(0.5, a, b))
    except Exception:
        return beta_mean(a, b)


def beta_ci95(a: float, b: float) -> tuple[float, float]:
    try:
        from scipy.stats import beta as beta_dist

        return (float(beta_dist.ppf(0.025, a, b)), float(beta_dist.ppf(0.975, a, b)))
    except Exception:
        lo, hi = wilson_ci(int(round(a)), int(round(a + b)))
        return lo, hi


def beta_sf(x: float, a: float, b: float) -> float:
    """P(p > x) for p ~ Beta(a,b)."""
    try:
        from scipy.stats import beta as beta_dist

        return float(beta_dist.sf(x, a, b))
    except Exception:
        mu = beta_mean(a, b)
        var = a * b / (((a + b) ** 2) * (a + b + 1.0))
        sd = math.sqrt(max(var, 1e-18))
        z = (x - mu) / sd
        return 0.5 * math.erfc(z / math.sqrt(2.0))


def prior_ab(p: float = PRIOR_P, strength: float = PRIOR_STRENGTH) -> tuple[float, float]:
    a = p * strength
    b = (1.0 - p) * strength
    return a, b
