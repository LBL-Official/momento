#!/usr/bin/env python3
"""Run Game Path Engine V2 in spec order. Research only."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable
STEPS = [
    "build_observations.py",
    "align_pbp_to_market.py",
    "time_alignment_audit.py",
    "build_game_state.py",
    "build_game_paths.py",
    "build_market_paths.py",
    "build_features.py",
    "build_buckets.py",
    "leakage_audit.py",
    "run_univariate.py",
    "run_bucket_tests.py",
    "run_interaction_tests.py",
    "fit_models.py",
    "run_experiments.py",
    "evaluate_economics.py",
    "portfolio_simulation.py",
    "report.py",
]


def main() -> int:
    for step in STEPS:
        print(f"=== {step} ===", flush=True)
        proc = subprocess.run([PY, str(HERE / step)], cwd=str(HERE))
        if proc.returncode != 0:
            print(f"{step} failed with {proc.returncode}", file=sys.stderr)
            return proc.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
