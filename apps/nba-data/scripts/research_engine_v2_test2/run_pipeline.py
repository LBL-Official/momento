#!/usr/bin/env python3
"""Run Test 2 waterfall. Hard-stop after Phase 1 or leakage failure."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable
STEPS = [
    "build_observations.py",
    "build_possessions.py",
    "overlay_market.py",
    "phase1_validate.py",
    "build_features.py",
    "leakage_audit.py",
    "analyze.py",
    "write_report.py",
    "enrich_features.py",
    "upgrade_analyze.py",
    "write_full_report.py",
    "export_dashboard.py",
]
HARD_STOP = {"phase1_validate.py", "leakage_audit.py"}


def main() -> int:
    for step in STEPS:
        print(f"\n=== {step} ===", flush=True)
        rc = subprocess.call([PY, str(HERE / step)], cwd=str(HERE))
        if rc != 0:
            print(f"FAIL {step} rc={rc}", file=sys.stderr)
            if step in HARD_STOP:
                print("HARD STOP — later phases not run.", file=sys.stderr)
            return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
