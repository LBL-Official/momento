#!/usr/bin/env python3
"""Write identity-derived Polymarket slug batch URLs (official Gamma /events)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from roller.admin import load_identity
from roller.config import RollerConfig
from roller.ingest.polymarket import identity_slugs


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    p.add_argument("--sport", required=True)
    p.add_argument("--season", required=True)
    p.add_argument("--batch-size", type=int, default=6)
    p.add_argument("--mapped-only", action="store_true")
    p.add_argument("--out", required=True)
    args = p.parse_args()
    cfg = RollerConfig(Path(args.root))
    ident = load_identity(cfg)
    sub = ident[(ident["sport"] == args.sport) & (ident["season"] == args.season)]
    if args.mapped_only:
        sub = sub[sub["mapping_status"] == "MAPPED"]
    slugs: list[str] = []
    for rec in sub.to_dict("records"):
        slugs.extend(
            identity_slugs(
                args.sport,
                str(rec.get("game_date") or ""),
                str(rec.get("away_team_id") or ""),
                str(rec.get("home_team_id") or ""),
            )
        )
    # unique preserve
    seen = set()
    uniq = []
    for s in slugs:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for i in range(0, len(uniq), args.batch_size):
        batch = uniq[i : i + args.batch_size]
        params = [("slug", s) for s in batch]
        lines.append("https://gamma-api.polymarket.com/events?" + urlencode(params))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"games={len(sub)} slugs={len(uniq)} batches={len(lines)} out={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
