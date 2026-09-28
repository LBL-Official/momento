#!/usr/bin/env python3
"""NCAAB P5 vs P5 wrapper around ingest_orderbook_snapshots.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TARGET = Path(__file__).with_name("ingest_orderbook_snapshots.py")


if __name__ == "__main__":
    raise SystemExit(subprocess.call([sys.executable, str(TARGET), "--sport", "NCAAB", *sys.argv[1:]]))
