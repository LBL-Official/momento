#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from roller.admin import load_dataset, load_identity
from roller.canonical.pbp import canonicalize_pbp
from roller.config import RollerConfig


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    p.add_argument("--sport", required=True)
    p.add_argument("--season", required=True)
    args = p.parse_args()
    cfg = RollerConfig(Path(args.root))
    n = canonicalize_pbp(cfg, args.sport, args.season, load_identity(cfg), load_dataset(cfg, args.sport, args.season, "games"))
    print(f"pbp rows={n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
