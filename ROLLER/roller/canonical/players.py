"""Player identity. No silent merges. Ambiguous names → REVIEW_REQUIRED."""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from roller.config import RollerConfig
from roller.io_csv import read_csv_optional, write_csv

PLAYER_COLUMNS = [
    "player_id",
    "sport",
    "display_name",
    "source",
    "status",
    "notes",
]


def players_path(cfg: RollerConfig):
    return cfg.root / "meta" / "players.csv"


def load_players(cfg: RollerConfig) -> pd.DataFrame:
    return read_csv_optional(players_path(cfg), columns=PLAYER_COLUMNS)


def collect_player_rows(events: pd.DataFrame, sport: str) -> list[dict]:
    if events is None or events.empty or "person_id" not in events.columns:
        return []
    seen: dict[tuple[str, str], dict] = {}
    for rec in events.to_dict("records"):
        pid = str(rec.get("person_id") or "").strip()
        if not pid:
            continue
        name = str(rec.get("player_name") or "").strip()
        key = (sport, pid)
        if key not in seen:
            seen[key] = {
                "player_id": pid,
                "sport": sport,
                "display_name": name,
                "source": "pbp_live.personId",
                "status": "OK",
                "notes": "",
            }
        elif name and not seen[key]["display_name"]:
            seen[key]["display_name"] = name
        elif name and seen[key]["display_name"] and name != seen[key]["display_name"]:
            seen[key]["status"] = "REVIEW_REQUIRED"
            seen[key]["notes"] = "conflicting display names for the same player_id"
    return mark_ambiguous_names(list(seen.values()))


def mark_ambiguous_names(rows: list[dict]) -> list[dict]:
    by_name: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        name = str(row.get("display_name") or "").strip().lower()
        if not name:
            continue
        by_name[(row["sport"], name)].append(row)
    for group in by_name.values():
        ids = {r["player_id"] for r in group}
        if len(ids) > 1:
            for r in group:
                r["status"] = "REVIEW_REQUIRED"
                r["notes"] = "same display_name maps to multiple player_id values; not merged"
    return rows


def upsert_players(cfg: RollerConfig, sport: str, events: pd.DataFrame) -> pd.DataFrame:
    incoming = collect_player_rows(events, sport)
    existing = load_players(cfg)
    by_key: dict[tuple[str, str], dict] = {}
    if not existing.empty:
        for rec in existing.to_dict("records"):
            by_key[(str(rec.get("sport") or ""), str(rec.get("player_id") or ""))] = rec
    for rec in incoming:
        key = (rec["sport"], rec["player_id"])
        if key not in by_key:
            by_key[key] = rec
            continue
        prev = by_key[key]
        if rec["display_name"] and not prev.get("display_name"):
            prev["display_name"] = rec["display_name"]
        if rec["status"] == "REVIEW_REQUIRED":
            prev["status"] = "REVIEW_REQUIRED"
            prev["notes"] = rec.get("notes") or prev.get("notes") or ""
    merged = mark_ambiguous_names(list(by_key.values()))
    df = pd.DataFrame(merged)
    if df.empty:
        df = pd.DataFrame(columns=PLAYER_COLUMNS)
    else:
        df = df[PLAYER_COLUMNS].sort_values(["sport", "player_id"]).reset_index(drop=True)
    write_csv(players_path(cfg), df, PLAYER_COLUMNS)
    return df
