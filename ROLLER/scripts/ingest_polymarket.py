#!/usr/bin/env python3
"""Ingest official Polymarket 1-minute last-trade history into warehouse + ROLLER.

Does not invent bid/ask. Does not substitute Kalshi. Links via internal_game_id.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from roller.canonical.polymarket_candles import ingest_polymarket_sport
from roller.config import RollerConfig


DEFAULT_JOBS = [
    ("NBA", "2025-2026"),
    ("NCAAB", "2025-2026"),
    ("WNBA", "2025"),
    ("WNBA", "2026"),
]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    p.add_argument("--sport", action="append")
    p.add_argument("--season")
    p.add_argument("--discover-only", action="store_true")
    p.add_argument("--canonicalize-only", action="store_true")
    p.add_argument("--max-events", type=int)
    args = p.parse_args()
    cfg = RollerConfig(Path(args.root))
    if args.sport and args.season:
        jobs = [(s, args.season) for s in args.sport]
    elif args.sport:
        jobs = [(s, season) for s in args.sport for season in cfg.season_labels(s) if (s, season) in DEFAULT_JOBS or season in {"2025-2026", "2025", "2026"}]
        if not jobs:
            jobs = [(s, cfg.season_labels(s)[0]) for s in args.sport]
    else:
        jobs = list(DEFAULT_JOBS)
    discover = not args.canonicalize_only
    download = not args.discover_only and not args.canonicalize_only
    canonicalize = not args.discover_only
    for sport, season in jobs:
        print(f"polymarket ingest {sport} {season}", flush=True)
        report = ingest_polymarket_sport(
            cfg,
            sport,
            season,
            discover=discover,
            download=download,
            canonicalize=canonicalize,
            max_events=args.max_events,
        )
        print(
            " ".join(f"{k}={v}" for k, v in report.items()),
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
