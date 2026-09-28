#!/usr/bin/env python3
"""Import one CLOB /prices-history JSON into warehouse raw prices."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from roller.config import RollerConfig
from roller.ingest.games import load_sport_games
from roller.ingest.polymarket import write_raw_prices


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("page_json")
    p.add_argument("--sport", required=True)
    p.add_argument("--season", required=True)
    p.add_argument("--token-id", required=True)
    p.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = p.parse_args()
    payload = json.loads(Path(args.page_json).read_text(encoding="utf-8"))
    hist = payload.get("history") if isinstance(payload, dict) else payload
    if not isinstance(hist, list):
        print("no history")
        return 1
    points = []
    seen = set()
    for row in hist:
        t = row.get("t")
        pval = row.get("p")
        if t is None or pval is None:
            continue
        ti = int(t)
        if ti in seen:
            continue
        seen.add(ti)
        points.append({"t": ti, "p": pval})
    points.sort(key=lambda r: r["t"])
    cfg = RollerConfig(Path(args.root))
    _, _, wh = load_sport_games(cfg, args.sport, args.season)
    path = write_raw_prices(wh, args.sport, args.token_id, points)
    print(f"token={args.token_id[:12]}... points={len(points)} path={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
