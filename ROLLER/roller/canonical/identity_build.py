"""Build meta/game_identity.csv and meta/teams.csv.

Basketball IDs come from assign_internal_ids. Existing valid IDs are
preserved by warehouse/source key. MLB is not reminted here (game_pk
identities are copied from canonical games.csv by warehouse.identity).
"""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from roller.config import RollerConfig
from roller.identity import (
    CONFIDENCE_NONE,
    MAPPING_REVIEW,
    MAPPING_UNMAPPED,
    assign_internal_ids,
    mapping_from_crosswalk,
)
from roller.ingest.games import (
    index_crosswalk,
    infer_market_tickers,
    load_sport_games,
    source_id_field,
)
from roller.io_csv import read_csv_optional, write_csv
from roller.timeutil import now_utc_iso
from roller.warehouse.identity import (
    SPORTS_IDENTITY_BUILD_MUST_NOT_REMINT,
    apply_preserved_internal_ids,
    existing_identity_lookups,
)

IDENTITY_COLUMNS = [
    "internal_game_id",
    "sport",
    "season",
    "game_date",
    "home_team_id",
    "away_team_id",
    "home_team_name",
    "away_team_name",
    "source_game_id",
    "warehouse_game_id",
    "event_ticker",
    "kalshi_market_yes_home",
    "kalshi_market_yes_away",
    "mapping_status",
    "mapping_confidence",
    "created_at",
    "updated_at",
]

TEAM_COLUMNS = [
    "team_id",
    "sport",
    "season",
    "team_name",
    "conference",
]


def build_identity(cfg: RollerConfig, sports: list[str] | None = None) -> pd.DataFrame:
    now = now_utc_iso()
    existing = read_csv_optional(cfg.root / "meta" / "game_identity.csv", IDENTITY_COLUMNS)
    created = {}
    if not existing.empty and "internal_game_id" in existing.columns:
        created = dict(zip(existing["internal_game_id"], existing.get("created_at", pd.Series(dtype=str))))

    raw_rows: list[dict] = []
    pair_counts: dict[tuple, int] = defaultdict(int)
    rebuild = sports or cfg.sport_ids()
    keep = pd.DataFrame(columns=IDENTITY_COLUMNS)
    if not existing.empty and "sport" in existing.columns:
        keep = existing[~existing["sport"].isin(rebuild)].copy()
        if keep.empty:
            keep = pd.DataFrame(columns=IDENTITY_COLUMNS)
        elif list(keep.columns) != IDENTITY_COLUMNS:
            for col in IDENTITY_COLUMNS:
                if col not in keep.columns:
                    keep[col] = ""
            keep = keep[IDENTITY_COLUMNS]
        protected = existing[existing["sport"].isin(SPORTS_IDENTITY_BUILD_MUST_NOT_REMINT)]
        restore = protected[protected["sport"].isin(rebuild)]
        if not restore.empty:
            keep = restore.copy() if keep.empty else pd.concat([keep, restore], ignore_index=True)

    for sport in rebuild:
        if sport in SPORTS_IDENTITY_BUILD_MUST_NOT_REMINT:
            continue
        for season in cfg.season_labels(sport):
            games, xwalk, _wh = load_sport_games(cfg, sport, season)
            if not games:
                continue
            by_event = index_crosswalk(xwalk)
            src_field = source_id_field(sport)
            for g in games:
                home = cfg.canon_team_id(sport, season, str(g.get("home_team_code") or "").strip())
                away = cfg.canon_team_id(sport, season, str(g.get("away_team_code") or "").strip())
                date = str(g.get("game_date") or "")[:10]
                pair_counts[(sport, date, away, home)] += 1
                ev = str(g.get("event_id") or g.get("event_ticker") or "")
                cw = by_event.get(ev) or by_event.get(str(g.get("event_ticker") or "")) or {}
                src = cw.get(src_field) or ""
                home_t, away_t = infer_market_tickers(
                    g, home, away, lambda code: cfg.canon_team_id(sport, season, code)
                )
                has_tickers = bool(home_t and away_t)
                unique = pair_counts[(sport, date, away, home)] == 1
                # uniqueness among warehouse games is computed after the loop
                status, conf = mapping_from_crosswalk(cw.get("match_status"), True, has_tickers)
                if not src and (cw.get("match_status") or "").upper() != "MATCHED":
                    status, conf = MAPPING_UNMAPPED, CONFIDENCE_NONE
                raw_rows.append(
                    {
                        "sport": sport,
                        "season": season,
                        "game_date": date,
                        "home_team_id": home,
                        "away_team_id": away,
                        "home_team_name": g.get("home_team") or "",
                        "away_team_name": g.get("away_team") or "",
                        "source_game_id": src,
                        "warehouse_game_id": g.get("game_id") or "",
                        "event_ticker": g.get("event_ticker") or ev,
                        "kalshi_market_yes_home": home_t,
                        "kalshi_market_yes_away": away_t,
                        "mapping_status": status,
                        "mapping_confidence": conf,
                        "scheduled_start": g.get("scheduled_start") or "",
                        "_event_id": ev,
                    }
                )

    # Non-unique date+pair → REVIEW_REQUIRED unless already UNMAPPED
    seen: dict[tuple, int] = defaultdict(int)
    for r in raw_rows:
        seen[(r["sport"], r["game_date"], r["away_team_id"], r["home_team_id"])] += 1
    for r in raw_rows:
        key = (r["sport"], r["game_date"], r["away_team_id"], r["home_team_id"])
        if seen[key] > 1 and r["mapping_status"] != MAPPING_UNMAPPED:
            # rematches still MAP if MATCHED and we have distinct scheduled_start / event
            pass

    produced = {str(r.get("sport") or "") for r in raw_rows}
    if not existing.empty and "sport" in existing.columns:
        for sport in rebuild:
            if sport in SPORTS_IDENTITY_BUILD_MUST_NOT_REMINT:
                continue
            if sport not in produced:
                extra = existing[existing["sport"] == sport]
                if not extra.empty:
                    keep = extra.copy() if keep.empty else pd.concat([keep, extra], ignore_index=True)

    assigned = assign_internal_ids(raw_rows)
    if not existing.empty:
        by_wh, by_src = existing_identity_lookups(existing.to_dict("records"))
        assigned = apply_preserved_internal_ids(assigned, by_wh, by_src)
    for r in assigned:
        r["created_at"] = created.get(r["internal_game_id"]) or now
        r["updated_at"] = now
        r.pop("scheduled_start", None)
        r.pop("_event_id", None)

    df = pd.DataFrame(assigned)
    if df.empty:
        df = pd.DataFrame(columns=IDENTITY_COLUMNS)
    else:
        df = df[IDENTITY_COLUMNS]
    if not keep.empty:
        df = pd.concat([keep, df], ignore_index=True)
    if df.empty:
        df = pd.DataFrame(columns=IDENTITY_COLUMNS)
    else:
        df = df[IDENTITY_COLUMNS]
        df = df.sort_values(["sport", "game_date", "internal_game_id"]).reset_index(drop=True)
    write_csv(cfg.root / "meta" / "game_identity.csv", df, IDENTITY_COLUMNS)
    _write_teams(cfg, df)
    return df


def _write_teams(cfg: RollerConfig, identity: pd.DataFrame) -> None:
    rows = []
    seen = set()
    for rec in identity.to_dict("records"):
        for side, name_key in (("home_team_id", "home_team_name"), ("away_team_id", "away_team_name")):
            tid = rec.get(side)
            key = (rec["sport"], rec["season"], tid)
            if not tid or key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "team_id": tid,
                    "sport": rec["sport"],
                    "season": rec["season"],
                    "team_name": rec.get(name_key) or tid,
                    "conference": cfg.conference_of(rec["sport"], rec["season"], str(tid)) or "",
                }
            )
    teams = pd.DataFrame(rows)
    if teams.empty:
        teams = pd.DataFrame(columns=TEAM_COLUMNS)
    else:
        teams = teams.sort_values(["sport", "season", "team_id"]).reset_index(drop=True)
    write_csv(cfg.root / "meta" / "teams.csv", teams, TEAM_COLUMNS)
