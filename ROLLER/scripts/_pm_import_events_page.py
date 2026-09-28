#!/usr/bin/env python3
"""Import a Gamma /events JSON page into warehouse raw/polymarket/{sport}/events."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from roller.config import RollerConfig
from roller.ingest.games import load_sport_games
from roller.ingest.polymarket import write_raw_events


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("page_json")
    p.add_argument("--sport", required=True)
    p.add_argument("--season", required=True)
    p.add_argument("--no-date-filter", action="store_true")
    p.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = p.parse_args()
    cfg = RollerConfig(Path(args.root))
    raw = json.loads(Path(args.page_json).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        print("not a list")
        return 1
    window = ((cfg.polymarket.get("season_windows") or {}).get(args.sport) or {}).get(args.season) or {}
    lo = str(window.get("event_date_from") or "")
    hi = str(window.get("event_date_to") or "")
    kept = []
    for ev in raw:
        d = str(ev.get("eventDate") or "")[:10]
        if not args.no_date_filter:
            if lo and d and d < lo:
                continue
            if hi and d and d > hi:
                continue
        markets = []
        for m in ev.get("markets") or []:
            if str(m.get("sportsMarketType") or "") == "moneyline":
                markets.append(
                    {
                        "id": m.get("id"),
                        "sportsMarketType": m.get("sportsMarketType"),
                        "outcomes": m.get("outcomes"),
                        "clobTokenIds": m.get("clobTokenIds"),
                        "question": m.get("question"),
                        "slug": m.get("slug"),
                        "gameStartTime": m.get("gameStartTime"),
                        "closed": m.get("closed"),
                    }
                )
        if not ev.get("teams") or not str(ev.get("eventDate") or "").strip():
            continue
        slim = {
            "id": ev.get("id"),
            "slug": ev.get("slug"),
            "title": ev.get("title"),
            "eventDate": ev.get("eventDate"),
            "startTime": ev.get("startTime"),
            "gameId": ev.get("gameId"),
            "teams": ev.get("teams"),
            "sport": ev.get("sport"),
            "seriesSlug": ev.get("seriesSlug"),
            "markets": markets,
        }
        kept.append(slim)
    _, _, wh = load_sport_games(cfg, args.sport, args.season)
    paths = write_raw_events(wh, args.sport, kept)
    dates = [str(e.get("eventDate") or "") for e in raw]
    print(
        f"imported={len(paths)} page={len(raw)} "
        f"date_min={min(dates) if dates else ''} date_max={max(dates) if dates else ''}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
