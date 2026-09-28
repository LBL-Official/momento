#!/usr/bin/env python3
"""Forward-only Kalshi orderbook snapshots → ROLLER.

NBA all open KXNBAGAME markets. NCAAB open KXNCAAMBGAME P5 vs P5 only.
MLB all open KXMLBGAME markets. Forward-only live snapshots.
Does not invent historical L2. Settled books are empty and are not history.
Does not submit orders. Does not change live FIRST01 / Risk / Execution.

Cron (October onward, during the slate):

  */1 * * * * cd /path/ROLLER && .venv/bin/python scripts/ingest_orderbook_snapshots.py --once
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from roller.admin import load_identity
from roller.canonical.orderbook import append_snapshot_csv, raw_orderbook_dir, snapshot_row
from roller.config import RollerConfig
from roller.ingest.orderbook import SERIES, get_orderbook, iter_open_tickers
from roller.paths import ensure_season_dirs
from roller.timeutil import now_utc_iso


def _season_for(cfg: RollerConfig, sport: str, captured_at: str) -> str:
    labels = cfg.season_labels(sport)
    if not labels:
        raise KeyError(sport)
    day = str(captured_at)[:10]
    if sport in {"NBA", "NCAAB"} and day >= "2026-10-01":
        return "2026-2027" if "2026-2027" in labels else labels[-1]
    if sport == "WNBA":
        year = day[:4]
        return year if year in labels else labels[-1]
    return labels[0] if day < "2026-10-01" else labels[-1]


def _ncaab_p5_events(cfg: RollerConfig, season: str, markets: list[dict]) -> set[str]:
    by_event: dict[str, list[dict]] = defaultdict(list)
    for m in markets:
        ev = str(m.get("event_ticker") or m.get("event_id") or "")
        by_event[ev].append(m)
    keep: set[str] = set()
    for ev, ms in by_event.items():
        codes = [str(m.get("ticker") or "").rsplit("-", 1)[-1] for m in ms if m.get("ticker")]
        if len(codes) < 2:
            continue
        if cfg.is_p5_vs_p5("NCAAB", season, codes[0], codes[1]):
            keep.add(ev)
    return keep


def collect_once(cfg: RollerConfig, sports: list[str]) -> dict[str, int]:
    ident = load_identity(cfg)
    captured = now_utc_iso()
    counts = {s: 0 for s in sports}
    for sport in sports:
        series = SERIES.get(sport)
        if not series:
            continue
        season = _season_for(cfg, sport, captured)
        ensure_season_dirs(cfg.root, sport, cfg.season_meta(sport, season)["path_key"])
        markets = iter_open_tickers(series)
        if sport == "NCAAB":
            ok = _ncaab_p5_events(cfg, season, markets)
            markets = [m for m in markets if str(m.get("event_ticker") or m.get("event_id") or "") in ok]
        raw_dir = raw_orderbook_dir(cfg, sport, season)
        raw_dir.mkdir(parents=True, exist_ok=True)
        for m in markets:
            ticker = str(m.get("ticker") or "")
            if not ticker:
                continue
            try:
                book = get_orderbook(ticker)
            except RuntimeError as exc:
                print(f"orderbook skip {sport} {ticker}: {exc}", flush=True)
                continue
            row = snapshot_row(
                cfg,
                sport=sport,
                season=season,
                ticker=ticker,
                captured_at=captured,
                payload=book,
                identity=ident,
            )
            payload = {
                "ticker": ticker,
                "sport": sport,
                "season": season,
                "captured_at": captured,
                "orderbook_fp": book.get("orderbook_fp") or book,
            }
            raw_path = raw_dir / captured[:10] / f"{ticker}_{captured.replace(':', '')}.json"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            append_snapshot_csv(cfg, sport, season, row)
            counts[sport] += 1
            time.sleep(0.05)
    return counts


def main() -> int:
    p = argparse.ArgumentParser(description="Ingest live Kalshi orderbook snapshots into ROLLER")
    p.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    p.add_argument("--sport", action="append", help="NBA, NCAAB, and/or MLB (repeatable)")
    p.add_argument("--once", action="store_true", help="one pass then exit (cron)")
    p.add_argument("--interval-seconds", type=int, default=60)
    args = p.parse_args()
    cfg = RollerConfig(Path(args.root))
    sports = args.sport or ["NBA", "NCAAB"]
    unknown = [s for s in sports if s not in SERIES]
    if unknown:
        print(f"unsupported sports for orderbook ingest: {unknown}", flush=True)
        return 2
    while True:
        counts = collect_once(cfg, sports)
        print(f"orderbook snapshots {now_utc_iso()} {counts}", flush=True)
        if args.once:
            return 0
        time.sleep(max(5, args.interval_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
