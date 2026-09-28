#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from roller.admin import load_identity
from roller.canonical.games import canonicalize_games
from roller.config import RollerConfig


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    p.add_argument("--sport", required=True)
    p.add_argument("--season", required=True)
    args = p.parse_args()
    cfg = RollerConfig(Path(args.root))
    df = canonicalize_games(cfg, args.sport, args.season, load_identity(cfg))
    print(f"games rows={len(df)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
