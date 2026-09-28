#!/usr/bin/env python3
"""Thin NBA entrypoint. Research only."""

from __future__ import annotations

import runpy
from pathlib import Path

ENGINE = (
    Path(__file__).resolve().parents[3]
    / "research"
    / "first80_alpha_decomposition_v1"
    / "src"
    / "run_experiment.py"
)

if __name__ == "__main__":
    runpy.run_path(str(ENGINE), run_name="__main__")
