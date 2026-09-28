#!/usr/bin/env python3
"""Thin NBA entrypoint. Engine lives in ncaab-data (shared, not a V1 edit)."""

from __future__ import annotations

import runpy
from pathlib import Path

ENGINE = (
    Path(__file__).resolve().parents[2]
    / "ncaab-data"
    / "scripts"
    / "first80_opponent_hedge_frontier_v2.py"
)

if __name__ == "__main__":
    runpy.run_path(str(ENGINE), run_name="__main__")
