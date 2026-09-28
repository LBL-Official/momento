#!/usr/bin/env python3
"""Discover warehouse games (read-only)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from roller.config import RollerConfig
from roller.ingest.games import load_sport_games


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    p.add_argument("--sport", required=True)
    p.add_argument("--season", required=True)
    args = p.parse_args()
    games, xwalk, wh = load_sport_games(RollerConfig(Path(args.root)), args.sport, args.season)
    print(f"warehouse={wh} games={len(games)} crosswalk={len(xwalk)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
