#!/usr/bin/env python3
"""Score path, lead path, and game-volatility features (pre-entry only)."""

from __future__ import annotations

import sys

from bundle import compute_game_features
from common import OUT, read_parquet_rows, write_parquet

SCORE_COLS = [
    "score_differential_mean",
    "score_differential_stdev",
    "score_differential_trend",
    "score_differential_velocity",
    "maximum_team_lead",
    "maximum_team_deficit",
    "lead_range",
    "distance_from_max_lead",
    "distance_from_max_deficit",
    "comeback_magnitude",
    "maximum_deficit_overcome",
    "points_scored_since_max_deficit",
    "time_since_max_deficit_s",
    "lead_decay",
    "net_score_change_last_2m",
    "net_score_change_last_5m",
    "net_score_change_last_10m",
    "n_score_path_points",
]

LEAD_COLS = [
    "number_of_lead_changes",
    "number_of_ties",
    "time_since_last_lead_change_s",
    "time_since_last_tie_s",
    "lead_changes_last_5_game_minutes",
    "lead_changes_last_10_game_minutes",
    "ties_last_5_game_minutes",
    "ties_last_10_game_minutes",
    "current_lead_duration_s",
    "path_state",
]

VOL_COLS = [
    "score_diff_stdev_2m",
    "score_diff_stdev_5m",
    "score_diff_stdev_10m",
    "score_diff_range_2m",
    "score_diff_range_5m",
    "score_diff_range_10m",
    "score_diff_abs_change_2m",
    "score_diff_abs_change_5m",
    "score_diff_abs_change_10m",
    "scoring_burst_intensity_5m",
    "team_scoring_rate_diff_5m",
    "scoring_run_imbalance",
    "last_scoring_run_team",
    "last_scoring_run_points",
    "last_scoring_run_duration_s",
    "largest_prior_run_team",
    "largest_prior_run_points",
]


def _subset(o, feat, cols):
    rec = {
        "observation_id": o["observation_id"],
        "entry_decision_time": o["entry_decision_time"],
        "alignment_confidence": o.get("alignment_confidence"),
    }
    for k in cols:
        rec[k] = feat.get(k)
    return rec


def main() -> int:
    obs = read_parquet_rows(OUT / "observations.parquet")
    if not obs:
        print("missing observations", file=sys.stderr)
        return 1
    score, lead, vol = [], [], []
    for o in obs:
        feat = compute_game_features(o)
        score.append(_subset(o, feat, SCORE_COLS))
        lead.append(_subset(o, feat, LEAD_COLS))
        vol.append(_subset(o, feat, VOL_COLS))
    write_parquet(OUT / "score_path_features.parquet", score)
    write_parquet(OUT / "lead_path_features.parquet", lead)
    write_parquet(OUT / "game_volatility_features.parquet", vol)
    print(f"game_paths n={len(score)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
