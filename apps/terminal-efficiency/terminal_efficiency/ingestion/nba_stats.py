"""NBA Stats PBP/box already on disk for 2024–25. Optional timeActual wrap."""

from __future__ import annotations

import subprocess
from pathlib import Path

from terminal_efficiency.paths import REPO_ROOT, warehouse
from terminal_efficiency.provenance import data_gap, record_provenance


def pbp_counts(season: str) -> dict:
    raw = warehouse("NBA", season) / "raw" / "nba_stats"
    pbp = raw / "pbp_v3"
    box = raw / "boxscore_summary"
    live = raw / "pbp_live"
    sched = raw / "schedule"
    return {
        "pbp_v3": len(list(pbp.glob("*.json"))) if pbp.exists() else 0,
        "boxscore_summary": len(list(box.glob("*.json"))) if box.exists() else 0,
        "pbp_live": len(list(live.glob("*.json"))) if live.exists() else 0,
        "schedule_files": len(list(sched.glob("*.json"))) if sched.exists() else 0,
    }


def record_nba_pbp_status(season: str) -> dict:
    counts = pbp_counts(season)
    dest = warehouse("NBA", season) / "manifests" / "nba" / "terminal_efficiency_nba_stats_status.json"
    extra: dict = {"counts": counts}
    if counts["pbp_v3"] == 0:
        extra["data_gap"] = data_gap(
            source="NBA Stats PlayByPlayV3",
            required_field="pbp_v3 JSON",
            why="no files",
            future_source="nba_pbp_overnight_ingest.py",
            impact="cannot build Dataset B",
        )
        extra["status"] = "MISSING"
    else:
        extra["status"] = "AVAILABLE"
    if counts["pbp_live"] == 0:
        extra["timeactual_gap"] = data_gap(
            source="NBA live CDN timeActual",
            required_field="pbp_live",
            why="directory empty or absent",
            future_source="nba_pbp_live_timeactual_ingest.py",
            impact="candle alignment MODELED for this season",
        )
    record_provenance(
        dest,
        source="nba_stats",
        action="status",
        season=season,
        league="NBA",
        extra=extra,
    )
    return extra


def try_timeactual_ingest(season: str, *, timeout_s: int = 90) -> dict:
    """Attempt existing live ingest. Do not invent timeActual on failure."""
    script = REPO_ROOT / "apps" / "nba-data" / "scripts" / "nba_pbp_live_timeactual_ingest.py"
    dest = warehouse("NBA", season) / "manifests" / "nba" / "terminal_efficiency_timeactual_attempt.json"
    if not script.exists():
        gap = data_gap(
            source="nba_pbp_live_timeactual_ingest.py",
            required_field="timeActual",
            why="script missing",
            future_source=str(script),
            impact="MODELED alignment only",
        )
        record_provenance(dest, source="pbp_live", action="skip", season=season, league="NBA", extra={"data_gap": gap})
        return {"ok": False, "data_gap": gap}
    env = {"NBA_PBP_WAREHOUSE_SEASON": season}
    try:
        proc = subprocess.run(
            ["python3", str(script), "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
            env={**dict(**__import__("os").environ), **env},
        )
        extra = {
            "ok": proc.returncode == 0,
            "note": "help probe only; full live ingest is optional and must not invent timestamps",
            "help_tail": (proc.stdout or proc.stderr or "")[-1500:],
            "counts_after": pbp_counts(season),
        }
        if pbp_counts(season)["pbp_live"] == 0:
            extra["data_gap"] = data_gap(
                source="NBA live CDN",
                required_field="timeActual",
                why="pbp_live still empty; full ingest not launched automatically (rate-limit / historical CDN uncertain)",
                future_source="manual nba_pbp_live_timeactual_ingest.py",
                impact="PERIOD_BOUNDED_LINEAR_GAME_CLOCK labeled MODELED",
            )
        record_provenance(dest, source="pbp_live", action="help-probe", season=season, league="NBA", extra=extra)
        return extra
    except Exception as exc:  # noqa: BLE001
        gap = data_gap(
            source="NBA live CDN",
            required_field="timeActual",
            why=str(exc),
            future_source="nba_pbp_live_timeactual_ingest.py",
            impact="MODELED alignment",
        )
        record_provenance(dest, source="pbp_live", action="failed", season=season, league="NBA", extra={"data_gap": gap})
        return {"ok": False, "data_gap": gap}
