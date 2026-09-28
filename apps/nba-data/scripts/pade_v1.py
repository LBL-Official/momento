#!/usr/bin/env python3
"""Thin entrypoint for PADE V1. Research only."""

from __future__ import annotations

import runpy
from pathlib import Path

ENGINE = Path(__file__).resolve().parent / "pade_v1" / "run.py"

if __name__ == "__main__":
    runpy.run_path(str(ENGINE), run_name="__main__")
