#!/usr/bin/env python3
"""Master ROLLER maintenance command. Default: offline rebuild from warehouse evidence."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from roller.config import RollerConfig
from roller.maintenance.update import update_all


def main() -> int:
    p = argparse.ArgumentParser(description="Update ROLLER from existing warehouse evidence")
    p.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    p.add_argument("--sport", action="append")
    p.add_argument("--season")
    p.add_argument("--fetch", action="store_true", help="invoke existing warehouse CLIs (network)")
    p.add_argument("--skip-pbp", action="store_true")
    p.add_argument("--skip-candles", action="store_true")
    p.add_argument("--skip-validate", action="store_true")
    args = p.parse_args()
    cfg = RollerConfig(Path(args.root))
    sports = args.sport
    seasons = None
    if args.season and sports:
        seasons = {s: [args.season] for s in sports}
    result = update_all(
        cfg,
        sports=sports,
        seasons=seasons,
        fetch=args.fetch,
        include_pbp=not args.skip_pbp,
        include_candles=not args.skip_candles,
        validate=not args.skip_validate,
    )
    print(f"status={result.get('status')} integrity={result['integrity'].get('status')} leakage={result['leakage'].get('status')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
