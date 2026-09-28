#!/usr/bin/env python3
"""Game-state snapshot at first-80 (time + score)."""

from __future__ import annotations

import sys

from bundle import compute_game_features
from common import OUT, read_parquet_rows, write_parquet

STATE_COLS = [
    "quarter",
    "game_seconds_elapsed",
    "game_seconds_remaining",
    "period_seconds_remaining",
    "half",
    "early_game",
    "mid_game",
    "late_game",
    "flag_Q4",
    "flag_OT",
    "team_score",
    "opponent_score",
    "score_differential",
    "absolute_score_differential",
    "total_points",
    "points_per_game_minute",
    "team_share_of_total_points",
    "lead_size",
    "deficit_size",
    "team_is_leading",
    "team_is_trailing",
    "game_is_tied",
    "pace_proxy",
    "game_phase",
    "path_state",
]


def main() -> int:
    obs = read_parquet_rows(OUT / "observations.parquet")
    if not obs:
        print("missing observations", file=sys.stderr)
        return 1
    rows = []
    for o in obs:
        feat = compute_game_features(o)
        rec = {
            "observation_id": o["observation_id"],
            "entry_decision_time": o["entry_decision_time"],
            "alignment_confidence": o.get("alignment_confidence"),
        }
        for k in STATE_COLS:
            rec[k] = feat.get(k)
        rows.append(rec)
    write_parquet(OUT / "game_state_entry.parquet", rows)
    print(f"game_state n={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
