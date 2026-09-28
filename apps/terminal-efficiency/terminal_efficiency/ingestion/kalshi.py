"""Wrap existing warehouse CLIs. Do not invent candle payloads."""

from __future__ import annotations

import subprocess
from pathlib import Path

from terminal_efficiency.paths import REPO_ROOT, warehouse
from terminal_efficiency.provenance import data_gap, record_provenance, write_json


def _cli_package(league: str) -> str:
    return "momento-nba-data" if league.upper() == "NBA" else "momento-ncaab-data"


def kalshi_raw_present(league: str, season: str) -> bool:
    root = warehouse(league, season) / "raw" / "kalshi"
    return root.exists() and any(root.rglob("*.jsonl.gz"))


def candle_ticker_count(league: str, season: str) -> int:
    sport = "nba" if league.upper() == "NBA" else "ncaab"
    candles = warehouse(league, season) / "raw" / "kalshi" / sport / "candlesticks"
    if not candles.exists():
        return 0
    return sum(1 for p in candles.iterdir() if p.is_dir())


def run_kalshi_download(league: str, season: str, *, dry_run: bool = True) -> dict:
    """Call cargo warehouse CLI. dry_run default avoids accidental huge live pulls."""
    pkg = _cli_package(league)
    cmd = ["cargo", "run", "-p", pkg, "--", "download-all", "--season", season]
    if dry_run:
        cmd.append("--dry-run")
    dest = warehouse(league, season) / "manifests" / league.lower() / "terminal_efficiency_kalshi_ingest.json"
    try:
        proc = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=120 if dry_run else 3600,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        gap = data_gap(
            source="Kalshi via " + pkg,
            required_field="1-minute CANDLESTICK_TOP_OF_BOOK",
            why=str(exc),
            future_source="retry momento-*-data when network allows",
            impact="TRAIN WITHOUT CANDLES; Dataset C DATA_GAP",
        )
        record_provenance(
            dest,
            source=pkg,
            action="download-all",
            season=season,
            league=league,
            extra={"ok": False, "dry_run": dry_run, "data_gap": gap},
        )
        return {"ok": False, "dry_run": dry_run, "data_gap": gap}

    ok = proc.returncode == 0
    extra = {
        "ok": ok,
        "dry_run": dry_run,
        "returncode": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-4000:],
        "stderr_tail": (proc.stderr or "")[-2000:],
        "candle_ticker_count": candle_ticker_count(league, season),
        "command": cmd,
    }
    if not ok:
        extra["data_gap"] = data_gap(
            source="Kalshi via " + pkg,
            required_field="1-minute CANDLESTICK_TOP_OF_BOOK",
            why=f"cli exit {proc.returncode}",
            future_source="retry when Kalshi HTTP is reachable",
            impact="TRAIN WITHOUT CANDLES; never synthesize prices",
        )
    record_provenance(dest, source=pkg, action="download-all", season=season, league=league, extra=extra)
    return extra


def record_existing_kalshi_gap(league: str, season: str) -> dict:
    n = candle_ticker_count(league, season)
    dest = warehouse(league, season) / "manifests" / league.lower() / "terminal_efficiency_kalshi_status.json"
    if n == 0:
        gap = data_gap(
            source=f"Kalshi {league} {season}",
            required_field="candles_1m",
            why="no candlestick ticker directories on disk",
            future_source="momento-*-data download-all --season " + season,
            impact="training uses Datasets A/B only",
        )
        status = {"status": "MISSING", "candle_ticker_count": 0, "data_gap": gap}
    elif league.upper() == "NBA" and season == "2024-2025" and n < 200:
        gap = data_gap(
            source=f"Kalshi {league} {season}",
            required_field="full-season candles_1m",
            why=f"only {n} ticker dirs (playoff-scale); events file may mix later seasons",
            future_source="full download-all --season 2024-2025",
            impact="Dataset C PARTIAL; do not synthesize the rest",
        )
        status = {"status": "PARTIAL", "candle_ticker_count": n, "data_gap": gap}
    else:
        status = {"status": "AVAILABLE", "candle_ticker_count": n}
    write_json(dest, status)
    return status
