#!/usr/bin/env python3
"""Run Dynamic Path Engine V3 in the specified phase order."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable
STEPS = [
    "build_trade_universe.py",
    "build_post_entry_panel.py",
    "build_market_states.py",
    "build_game_states.py",
    "alignment_diagnostics.py",
    "build_targets.py",
    "build_features.py",
    "leakage_audit.py",
    "fit_univariate.py",
    "fit_hazard_models.py",
    "fit_survival_models.py",
    "evaluate_models.py",
    "simulate_dynamic_policy.py",
    "report.py",
]


def main() -> int:
    for step in STEPS:
        print(f"=== {step} ===", flush=True)
        r = subprocess.run([PY, str(HERE / step)], cwd=str(HERE))
        if r.returncode != 0:
            print(f"FAILED {step} code={r.returncode}", file=sys.stderr)
            return r.returncode
    print("V3 pipeline complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
