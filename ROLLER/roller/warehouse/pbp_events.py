"""Project NBA PBP CSV into warehouse_v0. Phase 5.

Links through source_game_id → identity → internal_game_id.
Does not invent wall clocks from game clock. Does not join candles.
Does not infer possession. Identity linkage is not PIT alignment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from roller.config import RollerConfig
from roller.io_csv import read_csv, read_csv_optional, write_json
from roller.timeutil import now_utc_iso
from roller.warehouse.identity import identity_artifact_path
from roller.warehouse.layout_v0 import pbp_dir, warehouse_v0_readme_path
from roller.warehouse.partitioning import list_month_csvs, month_key, month_parquet

PHASE5_SPORT = "NBA"

PBP_COLUMNS = [
    "internal_game_id",
    "source_internal_game_id",
    "source_game_id",
    "game_link_status",
    "event_number",
    "event_timestamp",
    "time_actual",
    "available_at",
    "ingested_at",
    "timestamp_status",
    "availability_quality",
    "period",
    "clock",
    "home_score",
    "away_score",
    "score_differential_home",
    "event_type",
    "event_description",
    "team_tricode",
    "possession",
    "person_id",
    "sub_type",
    "shot_result",
    "team_id",
    "player_name",
    "home_away",
    "source",
]


@dataclass
class PbpBuild:
    months: dict[str, int] = field(default_factory=dict)
    rows: int = 0
    linked_rows: int = 0
    conflict_rows: int = 0
    unlinked_rows: int = 0
    blank_event_timestamp: int = 0
    duplicate_event_keys: int = 0
    games_with_pbp: int = 0
    date_min: str = ""
    date_max: str = ""


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def source_game_index(identity: pd.DataFrame, *, sport: str = PHASE5_SPORT) -> dict[str, set[str]]:
    """source_game_id → internal_game_id set. Conflicts stay as multiple values."""
    out: dict[str, set[str]] = {}
    scoped = identity
    if not identity.empty and "sport" in identity.columns:
        scoped = identity[identity["sport"].astype(str) == sport]
    for rec in scoped.to_dict("records"):
        src = _text(rec.get("source_game_id"))
        gid = _text(rec.get("internal_game_id"))
        if not src or not gid:
            continue
        out.setdefault(src, set()).add(gid)
    return out


def pbp_csv_dir(cfg: RollerConfig, season: str = "2025-2026") -> Path:
    return cfg.dataset_path(PHASE5_SPORT, season, "pbp")


def project_pbp_frame(
    frame: pd.DataFrame,
    source_index: dict[str, set[str]],
    extra_columns: tuple[str, ...] = (),
) -> pd.DataFrame:
    cols = list(PBP_COLUMNS)
    for col in extra_columns:
        if col not in cols:
            cols.append(col)
    if frame.empty:
        return pd.DataFrame(columns=cols)
    work = frame.copy()
    src = work.get("source_game_id", pd.Series("", index=work.index)).map(_text)
    csv_gid = work.get("internal_game_id", pd.Series("", index=work.index)).map(_text)
    resolved: list[str] = []
    status: list[str] = []
    for source_id, stamped in zip(src.tolist(), csv_gid.tolist()):
        candidates = tuple(sorted(source_index.get(source_id, ())))
        if not source_id:
            status.append("UNLINKED")
            resolved.append("")
        elif len(candidates) > 1:
            status.append("AMBIGUOUS")
            resolved.append("")
        elif not candidates:
            status.append("UNLINKED")
            resolved.append("")
        elif stamped and stamped != candidates[0]:
            status.append("CONFLICT")
            resolved.append("")
        else:
            status.append("LINKED")
            resolved.append(candidates[0])
    work["source_internal_game_id"] = csv_gid
    work["internal_game_id"] = resolved
    work["game_link_status"] = status
    work["source_game_id"] = src
    work["event_number"] = work.get("event_number", pd.Series("", index=work.index)).map(_text)
    work["event_timestamp"] = work.get("event_timestamp", pd.Series("", index=work.index)).map(_text)
    work["source"] = work.get("source_dataset", pd.Series("pbp", index=work.index)).map(_text)
    for col in extra_columns:
        if col in work.columns:
            work[col] = work[col].map(_text)
        else:
            work[col] = ""
    for col in cols:
        if col not in work.columns:
            work[col] = ""
    out = work[cols].copy()
    # Source sequence is authoritative. Timestamp is not the sort key.
    out["_seq"] = pd.to_numeric(out["event_number"], errors="coerce")
    out = out.sort_values(["internal_game_id", "_seq", "event_number"], kind="mergesort")
    return out.drop(columns=["_seq"]).reset_index(drop=True)


def _update_stats(stats: PbpBuild, frame: pd.DataFrame, month: str) -> None:
    stats.months[month] = int(len(frame))
    stats.rows += int(len(frame))
    stats.linked_rows += int((frame["game_link_status"] == "LINKED").sum())
    stats.conflict_rows += int((frame["game_link_status"] == "CONFLICT").sum())
    stats.unlinked_rows += int((frame["game_link_status"] == "UNLINKED").sum())
    stats.blank_event_timestamp += int(frame["event_timestamp"].astype(str).str.strip().eq("").sum())
    if not frame.empty:
        keys = frame["internal_game_id"].astype(str) + "\0" + frame["event_number"].astype(str)
        stats.duplicate_event_keys += int(keys.duplicated().sum())
        times = frame["event_timestamp"].astype(str)
        nonempty = times[times.str.strip() != ""]
        if not nonempty.empty:
            lo, hi = nonempty.min(), nonempty.max()
            if not stats.date_min or lo < stats.date_min:
                stats.date_min = lo
            if not stats.date_max or hi > stats.date_max:
                stats.date_max = hi


def project_nba_pbp(
    cfg: RollerConfig,
    *,
    season: str = "2025-2026",
    identity: pd.DataFrame | None = None,
    write: bool = True,
) -> tuple[PbpBuild, dict[str, Any]]:
    if identity is None:
        identity = read_csv_optional(identity_artifact_path(cfg))
    index = source_game_index(identity, sport=PHASE5_SPORT)
    src_dir = pbp_csv_dir(cfg, season)
    out_dir = pbp_dir(cfg, PHASE5_SPORT, season)
    stats = PbpBuild()
    games: set[str] = set()
    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        readme = warehouse_v0_readme_path(cfg, PHASE5_SPORT, season)
        if not readme.is_file():
            readme.write_text(
                "Provisional NBA warehouse_v0. Not Confirm & Run. Phase 8 will relocate.\n",
                encoding="utf-8",
            )
    for path in list_month_csvs(src_dir):
        month = month_key(path)
        projected = project_pbp_frame(read_csv(path), index)
        _update_stats(stats, projected, month)
        games.update(g for g in projected["internal_game_id"].astype(str) if g)
        if write:
            projected.to_parquet(month_parquet(out_dir, month), index=False)
    stats.games_with_pbp = len(games)
    nba_ident = identity[identity["sport"].astype(str) == PHASE5_SPORT] if not identity.empty else identity
    with_source = 0
    without_source = 0
    if not nba_ident.empty:
        src = nba_ident["source_game_id"].astype(str).str.strip()
        with_source = int((src != "").sum())
        without_source = int((src == "").sum())
    report = {
        "sport": PHASE5_SPORT,
        "rows": stats.rows,
        "linked_rows": stats.linked_rows,
        "conflict_rows": stats.conflict_rows,
        "unlinked_rows": stats.unlinked_rows,
        "blank_event_timestamp": stats.blank_event_timestamp,
        "duplicate_event_keys": stats.duplicate_event_keys,
        "games_with_pbp": stats.games_with_pbp,
        "identity_games": int(len(nba_ident)),
        "identity_with_source_game_id": with_source,
        "identity_without_source_game_id": without_source,
        "months": stats.months,
        "date_min": stats.date_min,
        "date_max": stats.date_max,
        "output_dir": str(out_dir),
        "updated_at": now_utc_iso(),
        "pit_join_performed": False,
        "timestamps_invented": False,
        "possession_inferred": False,
    }
    if write:
        write_json(out_dir / "manifest.json", report)
    return stats, report
