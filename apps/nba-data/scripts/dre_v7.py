#!/usr/bin/env python3
"""Thin entrypoint for DRE V7. Research only.

If scientific artifacts already exist, the runner completes reports and
dashboard from those artifacts. It does not remeasure after seeing OOS.
"""

from __future__ import annotations

import runpy
from pathlib import Path

ENGINE = Path(__file__).resolve().parent / "dre_v7" / "run.py"

if __name__ == "__main__":
    runpy.run_path(str(ENGINE), run_name="__main__")
