"""PBP sequence join. Not candle-PIT."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from roller.austin.clock import clock_to_seconds, parse_utc, period_to_quarter
from roller.austin.config import DEFAULT
from roller.austin.errors import AustinError
from roller.config import RollerConfig
from roller.warehouse.layout import pbp_dir
from roller.warehouse.partitioning import list_month_parquets

PBP_COLS = (
    "internal_game_id",
    "event_timestamp",
    "period",
    "clock",
    "home_score",
    "away_score",
)


def load_pbp(
    game_ids: set[str],
    *,
    sport: str = "NBA",
    season: str = "2025-2026",
) -> dict[str, list[dict[str, Any]]]:
    cfg = RollerConfig()
    directory = pbp_dir(cfg, sport=sport, season=season)
    files = list_month_parquets(directory)
    if not files:
        raise AustinError("DATA_REQUIRED", f"no PBP parquet under {directory}")
    wanted = {str(x) for x in game_ids}
    grouped: dict[str, list[dict[str, Any]]] = {gid: [] for gid in wanted}
    for path in files:
        frame = pd.read_parquet(path, columns=list(PBP_COLS))
        frame["internal_game_id"] = frame["internal_game_id"].astype(str)
        frame = frame[frame["internal_game_id"].isin(wanted)]
        for rec in frame.itertuples(index=False):
            stamp = parse_utc(rec.event_timestamp)
            if stamp is None:
                continue
            grouped[str(rec.internal_game_id)].append(
                {
                    "ts": stamp,
                    "period": period_to_quarter(rec.period),
                    "seconds_remaining": clock_to_seconds(rec.clock),
                    "home_score": _opt_int(rec.home_score),
                    "away_score": _opt_int(rec.away_score),
                }
            )
    for gid, rows in grouped.items():
        rows.sort(key=lambda item: item["ts"])
        grouped[gid] = rows
    return grouped


def state_at(events: list[dict[str, Any]], when: datetime) -> dict[str, Any] | None:
    if not events:
        return None
    chosen: dict[str, Any] | None = None
    for row in events:
        if row["ts"] <= when:
            chosen = row
        else:
            break
    return chosen


def _opt_int(value: object) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def pbp_status() -> str:
    return DEFAULT.pbp_status
