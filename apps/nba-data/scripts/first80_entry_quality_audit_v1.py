#!/usr/bin/env python3
"""Thin NBA entrypoint. Engine lives in ncaab-data (isolated; not a V1–V3 edit)."""

from __future__ import annotations

import runpy
from pathlib import Path

ENGINE = (
    Path(__file__).resolve().parents[2]
    / "ncaab-data"
    / "scripts"
    / "first80_entry_quality_audit_v1.py"
)

if __name__ == "__main__":
    runpy.run_path(str(ENGINE), run_name="__main__")
