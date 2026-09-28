"""CLI: python -m roller.research_query.indexes build --league NBA --season 2025-2026"""

from __future__ import annotations

import argparse
import json
import sys
import time

from roller.config import RollerConfig
from roller.research_query.indexes.builder import build_index
from roller.research_query.models import BASIS_LAST_TRADE, BASIS_TRADABLE
from roller.research_query.season_mapping import sport_from_league, warehouse_season

# Primary research warehouses. 2026-27 stubs are skipped if the tree is empty.
BUILD_ALL = (
    ("ATP", "2025-2026", BASIS_TRADABLE),
    ("WTA", "2025-2026", BASIS_TRADABLE),
    ("NBA", "2025-2026", BASIS_TRADABLE),
    ("NCAAB", "2025-2026", BASIS_TRADABLE),
    ("MLB", "2025-2026", BASIS_LAST_TRADE),
    ("MLB", "2025-2026", BASIS_TRADABLE),
    ("WNBA", "2025", BASIS_TRADABLE),
    ("WNBA", "2026", BASIS_TRADABLE),
    ("ATP", "2025-2026", BASIS_LAST_TRADE),
    ("WTA", "2025-2026", BASIS_LAST_TRADE),
)


def _dataset_ready(cfg: RollerConfig, league: str, season: str, basis: str) -> bool:
    sport = sport_from_league(league)
    wh = warehouse_season(season, sport)
    name = "kalshi_last_trade" if basis == BASIS_LAST_TRADE else "kalshi_candles"
    try:
        path = cfg.dataset_path(sport, wh, name)
    except (KeyError, FileNotFoundError):
        return False
    if path.is_file():
        return path.stat().st_size > 0
    if path.is_dir():
        return any(path.rglob("*.csv"))
    return False


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build ROLLER research-query observation indexes")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--league", required=True)
    b.add_argument("--season", required=True)
    b.add_argument(
        "--basis",
        default=BASIS_TRADABLE,
        choices=(BASIS_TRADABLE, BASIS_LAST_TRADE, "tradable", "last_trade"),
    )
    all_p = sub.add_parser("build-all")
    all_p.add_argument("--league", action="append", dest="leagues")
    args = p.parse_args(argv)

    def _basis(raw: str) -> str:
        token = str(raw or "").strip()
        if token in {BASIS_LAST_TRADE, "last_trade"}:
            return BASIS_LAST_TRADE
        return BASIS_TRADABLE

    if args.cmd == "build":
        man = build_index(league=args.league, season=args.season, basis=_basis(args.basis))
        print(json.dumps(man.to_dict(), indent=2, sort_keys=True))
        return 0

    cfg = RollerConfig()
    wanted = {str(x).upper() for x in (args.leagues or [])}
    rc = 0
    for league, season, basis in BUILD_ALL:
        if wanted and league not in wanted:
            continue
        if not _dataset_ready(cfg, league, season, basis):
            print(f"SKIP {league} {season} {basis} — dataset absent", file=sys.stderr)
            continue
        t0 = time.perf_counter()
        print(f"BUILD {league} {season} {basis}", flush=True)
        try:
            man = build_index(league=league, season=season, basis=basis, cfg=cfg)
        except Exception as exc:  # noqa: BLE001 — keep remaining sports building
            print(f"FAIL {league} {season} {basis}: {type(exc).__name__}: {exc}", file=sys.stderr)
            rc = 1
            continue
        elapsed = time.perf_counter() - t0
        print(
            json.dumps(
                {
                    "league": man.league,
                    "season": man.season,
                    "basis": basis,
                    "ticker_count": man.ticker_count,
                    "bar_rows": man.bar_rows,
                    "elapsed_s": round(elapsed, 3),
                },
                sort_keys=True,
            ),
            flush=True,
        )
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
