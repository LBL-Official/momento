#!/usr/bin/env python3
"""Run Path Engine V1 pipeline in spec order."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable
STEPS = [
    "build_observations.py",
    "build_features.py",
    "leakage_audit.py",
    "fit_models.py",
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
