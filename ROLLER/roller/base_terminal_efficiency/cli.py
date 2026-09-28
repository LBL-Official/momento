"""python -m roller.base_terminal_efficiency.cli build --league NBA --season 2025-2026"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import defaultdict
from pathlib import Path

from roller.admin import load_dataset
from roller.base_terminal_efficiency.builder import observations_for_ticker
from roller.base_terminal_efficiency.empirical import measure
from roller.base_terminal_efficiency.manifest import (
    MANIFEST_NAME,
    BaseTeManifest,
    checksum_paths,
    now_utc,
    write_manifest,
)
from roller.base_terminal_efficiency.models import DATA_REQUIRED
from roller.base_terminal_efficiency.versions import CODE_VERSION, SCHEMA_VERSION, SEMANTICS_VERSION
from roller.config import RollerConfig


def _git_sha(cwd: Path | None = None) -> str | None:
    starts = [cwd, Path.cwd(), Path(__file__).resolve().parents[3]]
    for start in starts:
        if start is None:
            continue
        try:
            out = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=start,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            return out.strip() or None
        except (OSError, subprocess.CalledProcessError):
            continue
    return None


def _derived_root(cfg: RollerConfig, sport: str, season: str) -> Path:
    games = cfg.dataset_path(sport, season, "games")
    return games.parent.parent / "derived" / "base_terminal_efficiency" / SEMANTICS_VERSION


def build(
    *,
    league: str,
    season: str,
    cfg: RollerConfig | None = None,
    max_tickers: int | None = None,
) -> dict:
    cfg = cfg or RollerConfig()
    sport = league
    try:
        candles = load_dataset(cfg, sport, season, "kalshi_candles")
        pbp = load_dataset(cfg, sport, season, "pbp")
        games = load_dataset(cfg, sport, season, "games")
    except FileNotFoundError:
        return {"status": DATA_REQUIRED, "reason": "source warehouse missing"}
    try:
        markets = load_dataset(cfg, sport, season, "kalshi_markets")
    except FileNotFoundError:
        markets = None
    if candles is None or candles.empty:
        return {"status": DATA_REQUIRED, "reason": "kalshi_candles empty"}
    by_ticker: dict[str, list] = defaultdict(list)
    for rec in candles.to_dict("records"):
        by_ticker[str(rec.get("ticker") or "")].append(rec)
    pbp_by: dict[str, list] = defaultdict(list)
    if pbp is not None and not pbp.empty:
        for rec in pbp.to_dict("records"):
            pbp_by[str(rec.get("internal_game_id") or "")].append(rec)
    games_by = {}
    if games is not None and not games.empty:
        for rec in games.to_dict("records"):
            games_by[str(rec.get("internal_game_id") or "")] = rec
    mkt_by = {}
    if markets is not None and not markets.empty:
        for rec in markets.to_dict("records"):
            mkt_by[str(rec.get("ticker") or "")] = rec
    dest = _derived_root(cfg, sport, season)
    obs_path = dest / "observations" / "observations.jsonl"
    paths_path = dest / "paths" / "paths.jsonl"
    obs_path.parent.mkdir(parents=True, exist_ok=True)
    paths_path.parent.mkdir(parents=True, exist_ok=True)
    n_obs = 0
    games_seen: set[str] = set()
    tickers_seen: set[str] = set()
    coverage: list[str] = []
    source_paths = [
        Path(cfg.dataset_path(sport, season, "kalshi_candles")),
        Path(cfg.dataset_path(sport, season, "pbp")),
        Path(cfg.dataset_path(sport, season, "games")),
    ]
    checks = checksum_paths(source_paths)
    ds_ver = hashlib.sha256("|".join(f"{k}:{v}" for k, v in sorted(checks.items())).encode()).hexdigest()
    with obs_path.open("w", encoding="utf-8") as of, paths_path.open("w", encoding="utf-8") as pf:
        for i, (ticker, recs) in enumerate(sorted(by_ticker.items())):
            if max_tickers is not None and i >= max_tickers:
                break
            if not ticker:
                continue
            gid = str(recs[0].get("internal_game_id") or "")
            rows, path = observations_for_ticker(
                recs,
                pbp_by.get(gid, []),
                game=games_by.get(gid),
                market=mkt_by.get(ticker),
                league=league,
                season=season,
                source_version=ds_ver,
                attach_terminal=True,
            )
            for row in rows:
                of.write(json.dumps(row.to_dict(), sort_keys=True) + "\n")
                n_obs += 1
                games_seen.add(row.game_id)
                tickers_seen.add(row.ticker)
                coverage.append(row.observation_ts)
            if path:
                pf.write(json.dumps(path, sort_keys=True) + "\n")
    coverage.sort()
    man = BaseTeManifest(
        schema_version=SCHEMA_VERSION,
        semantics_version=SEMANTICS_VERSION,
        code_version=CODE_VERSION,
        dataset_version=ds_ver,
        git_sha=_git_sha(cfg.root),
        build_timestamp_utc=now_utc(),
        league=league,
        season=season,
        source_paths=[str(p) for p in source_paths],
        source_checksums=checks,
        observation_count=n_obs,
        game_count=len(games_seen),
        ticker_count=len(tickers_seen),
        coverage_start=coverage[0] if coverage else None,
        coverage_end=coverage[-1] if coverage else None,
        extra={"terminal_note": "kalshi_markets absent → TERMINAL_MISSING"},
    )
    write_manifest(dest / MANIFEST_NAME, man)
    summary = measure([])
    summary.update(
        {
            "status": "COMPLETE",
            "n_entry": n_obs,
            "n_terminal_missing": n_obs if not mkt_by else summary["n_terminal_missing"],
            "derived_root": str(dest),
        }
    )
    return {"status": "COMPLETE", "manifest": man.to_dict(), "summary": summary}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Base Terminal Efficiency builder")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--league", required=True)
    b.add_argument("--season", required=True)
    b.add_argument("--max-tickers", type=int, default=None)
    args = p.parse_args(argv)
    if args.cmd == "build":
        out = build(league=args.league, season=args.season, max_tickers=args.max_tickers)
        print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if out.get("status") == "COMPLETE" else 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
