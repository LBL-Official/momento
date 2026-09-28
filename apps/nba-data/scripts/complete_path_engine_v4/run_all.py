#!/usr/bin/env python3
"""Run Complete Path Engine V4."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable
STEPS = [
    "build_trade_universe.py",
    "build_arrival_curves.py",
    "leakage_audit.py",
    "mean_curves.py",
    "fit_path_models.py",
    "evaluate.py",
    "report.py",
]


def main() -> int:
    for step in STEPS:
        print(f"=== {step} ===", flush=True)
        r = subprocess.run([PY, str(HERE / step)], cwd=str(HERE))
        if r.returncode != 0:
            print(f"FAILED {step} code={r.returncode}", file=sys.stderr)
            return r.returncode
    print("V4 pipeline complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
