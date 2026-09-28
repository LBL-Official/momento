"""Serve persisted Lubbock artifacts. Does not recompute N."""

from __future__ import annotations

import csv
import io
import json

from roller.choosin_texas.lubbock.schedule import repo_root
from roller.choosin_texas.models import ChoosinTexasError

SUMMARY = "research/choosin_texas/lubbock/v1/summary.json"


def load_summary() -> dict:
    path = repo_root() / SUMMARY
    if not path.exists():
        raise ChoosinTexasError("DATA_REQUIRED", "Lubbock v1 artifacts are not on disk")
    return json.loads(path.read_text())


def handle_lubbock() -> dict:
    payload = load_summary()
    payload["submits"] = False
    payload["live_execution"] = False
    payload["net_ev"] = "UNAVAILABLE"
    return payload


def handle_export_csv(sport: str, season: str, phase: str, grain: str) -> tuple[str, str]:
    summary = load_summary()
    series = next(
        (
            row
            for row in summary["series"]
            if row["sport"] == sport and row["season_id"] == season and row["phase"] == phase
        ),
        None,
    )
    if series is None:
        raise ChoosinTexasError("DATA_REQUIRED", "no Lubbock series for that sport, season, and phase")
    key = {"decile": "deciles", "quintile": "quintiles", "cumulative": "cumulative"}.get(grain)
    if key is None:
        raise ChoosinTexasError("DATA_REQUIRED", "grain must be decile, quintile, or cumulative")
    buffer = io.StringIO()
    rows = series[key]
    fields = [
        "bucket_id",
        "kind",
        "status",
        "schedule_completeness",
        "warehouse_games",
        "first80_rows",
        "rank_lo",
        "rank_hi",
        "date_min",
        "date_max",
        "p_t40",
        "p_yes",
        "gross_ev_cents",
        "gross_ev_lo",
        "gross_ev_hi",
        "legacy_shorthand_ev_cents",
        "hold_ev_cents",
        "net_ev",
        "path_completeness",
        "win_no_t40",
        "win_t40",
        "loss_no_t40",
        "loss_t40",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        if row.get("status") == "UNAVAILABLE":
            writer.writerow({"bucket_id": row.get("bucket_id"), "status": "UNAVAILABLE", "net_ev": "UNAVAILABLE"})
            continue
        interval = row.get("gross_ev_interval") or {}
        flat = dict(row)
        flat["gross_ev_lo"] = interval.get("lo", "UNAVAILABLE")
        flat["gross_ev_hi"] = interval.get("hi", "UNAVAILABLE")
        writer.writerow(flat)
    filename = f"lubbock_{sport}_{season}_{phase}_{grain}.csv"
    return filename, buffer.getvalue()
