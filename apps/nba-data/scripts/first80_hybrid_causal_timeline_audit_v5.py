#!/usr/bin/env python3
"""Thin NBA entrypoint. Engine lives in ncaab-data (not a V1–V4 edit)."""

from __future__ import annotations

import runpy
from pathlib import Path

ENGINE = (
    Path(__file__).resolve().parents[2]
    / "ncaab-data"
    / "scripts"
    / "first80_hybrid_causal_timeline_audit_v5.py"
)

if __name__ == "__main__":
    runpy.run_path(str(ENGINE), run_name="__main__")
