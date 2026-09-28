"""Frozen numeric rules. Keep identical to research/sugarland/v1/SPEC.md."""

from __future__ import annotations

SPEC_VERSION = "v1"
UNIVERSE_ID = "SUGARLAND_PREGAME_V1"

SPREAD_CAP_E4 = 1000
ABOVE_70_LO = 7000
BELOW_100 = 10000
AROUND_80_LO = 7800
AROUND_80_HI = 8200
CROSS_80 = 8000
CROSS_THRESHOLDS = (7800, 8000, 8200)
FIRST_THRESHOLDS = (6800, 7000, 7200)

ENDPOINT_AGE_SEC = 30 * 60
ENDPOINT_AGE_SENSITIVITIES = (5 * 60, 15 * 60, 30 * 60, 60 * 60)
SLOPE_AGE_SEC = 60 * 60
GRID_LOOKBACK_SEC = 14 * 24 * 3600
GRID_SEC = 15 * 60
SCHEDULE_QUARANTINE_SEC = 6 * 3600

HORIZONS_H = (48, 24, 12, 6, 2, 1)
AROUND_HORIZONS = (48, 24)

SLOPE_MIN_WEIGHTS = 8
SLOPE_MIN_SPAN_H = 6.0
SLOPE_MIN_COVERAGE = 0.50

BOOTSTRAP_REPS = 1000
BOOTSTRAP_SEED = 20260923

PRICE_BANDS = ("(70,75)", "[75,80)", "[80,85)", "[85,90)", "[90,100)")
LEAD_BUCKETS = ("[0,1)", "[1,2)", "[2,6)", "[6,12)", "[12,24)", "[24,48)", ">=48")

ENTRY_FEATURES = (
    "anchor_bid_pp",
    "spread_cents",
    "volume",
    "is_nba",
    "is_ncaab",
    "is_wnba",
    "is_mlb",
)
