#!/usr/bin/env python3
"""Run Capture Program v1 in the specified STEP order. Research only."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable
STEPS = [
    "00_reproduce_baseline.py",
    "01_build_execution_scenarios.py",
    "02_model_entry_capture.py",
    "03_model_stop_capture.py",
    "04_build_fee_model.py",
    "05_capacity_analysis.py",
    "06_portfolio_simulation.py",
    "07_live_episode_ledger.py",
    "08_validation.py",
    "09_report.py",
]


def main() -> int:
    for step in STEPS:
        print(f"=== {step} ===", flush=True)
        r = subprocess.run([PY, str(HERE / step)], cwd=str(HERE))
        if r.returncode != 0:
            print(f"FAILED {step} code={r.returncode}", file=sys.stderr)
            return r.returncode
    print("Capture Program v1 complete; LIVE EXECUTION CHANGED: FALSE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
