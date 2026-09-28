#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from roller.admin import load_dataset
from roller.config import RollerConfig
from roller.features.d2d import build_d2d_daily


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    p.add_argument("--sport", required=True)
    p.add_argument("--season", required=True)
    args = p.parse_args()
    cfg = RollerConfig(Path(args.root))
    games = load_dataset(cfg, args.sport, args.season, "games")
    df = build_d2d_daily(cfg, args.sport, args.season, games)
    print(f"d2d_daily rows={len(df)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
