"""Shared CLI bootstrap."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def add_common(p: argparse.ArgumentParser) -> argparse.ArgumentParser:
    p.add_argument("--root", default=str(ROOT))
    p.add_argument("--sport")
    p.add_argument("--season")
    return p
