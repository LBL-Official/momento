"""Canonical Game identity for NBA, NCAAB, and MLB.

Phase 2 only. Source game identity → internal_game_id → Game.

This module does not mint IDs from Kalshi tickers, dates, or team names.
It does not persist GameMarketLink. It does not ingest candles, PBP,
settlement, or orderbook. It does not change execute.py.

Existing valid ID formats are preserved:

    NBA_{YYYYMMDD}_{AWAY}_{HOME}[_{n}]
    NCAAB_{YYYYMMDD}_{AWAY}_{HOME}[_{n}]
    MLB_{YYYYMMDD}_{AWAY}_{HOME}_{game_pk}

`mapping_status` on meta/game_identity.csv is a source-crosswalk flag,
not this module's identity status vocabulary.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from roller.config import RollerConfig
from roller.identity import (
    CONFIDENCE_HIGH,
    CONFIDENCE_NONE,
    MAPPING_MAPPED,
    MAPPING_UNMAPPED,
    base_game_id,
)
from roller.io_csv import read_csv, read_csv_optional, write_csv
from roller.timeutil import now_utc_iso

IDENTITY_RULE_VERSION = "1.0.0"

PHASE2_SPORTS = ("NBA", "NCAAB", "MLB")

# identity_build.assign_internal_ids omits game_pk. MLB IDs must not be reminted there.
SPORTS_IDENTITY_BUILD_MUST_NOT_REMINT = frozenset({"MLB"})

SOURCE_SYSTEM_BY_SPORT = {
    "NBA": "nba_stats",
    "NCAAB": "espn",
    "MLB": "mlb_statsapi",
    "ATP": "kalshi",
    "WTA": "kalshi",
}

SOURCE_FIELD_BY_SPORT = {
    "NBA": "nba_game_id",
    "NCAAB": "espn_game_id",
    "MLB": "game_pk",
}

# Must match roller.canonical.identity_build.IDENTITY_COLUMNS and schemas.json.
IDENTITY_ARTIFACT_COLUMNS = [
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

_BASKETBALL_ID = (
    r"^(NBA|NCAAB|WNBA)_(\d{8})_([A-Za-z0-9-]+)_([A-Za-z0-9-]+)(?:_([2-9]|[1-9]\d+))?$"
)
_MLB_ID = r"^MLB_(\d{8})_([A-Za-z0-9]+)_([A-Za-z0-9]+)_(\d+)$"
_BASKETBALL_RE = re.compile(_BASKETBALL_ID)
_MLB_RE = re.compile(_MLB_ID)
_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


class IdentityStatus(str, Enum):
    """Identity classification. Not warehouse coverage. Not mapping_status."""

    VALID = "VALID"
    DUPLICATE = "DUPLICATE"
    CONFLICT = "CONFLICT"
    AMBIGUOUS = "AMBIGUOUS"
    INVALID = "INVALID"
    MISSING = "MISSING"


@dataclass(frozen=True)
class ParsedInternalGameId:
    sport: str
    yyyymmdd: str
    away_team_id: str
    home_team_id: str
    rematch_n: int | None = None
    game_pk: str = ""


@dataclass(frozen=True)
class IdentityResolution:
    status: IdentityStatus
    internal_game_id: str = ""
    reason: str = ""
    source_game_id: str = ""
    source_system: str = ""


@dataclass(frozen=True)
class IdentityFinding:
    status: IdentityStatus
    internal_game_id: str
    sport: str
    reason: str
    source_game_id: str = ""


@dataclass
class SportIdentityCoverage:
    sport: str
    total_games: int = 0
    with_internal_game_id: int = 0
    without_internal_game_id: int = 0
    unique_internal_game_id: int = 0
    duplicate_internal_game_id: int = 0
    with_source_game_id: int = 0
    without_source_game_id: int = 0
    unique_source_game_id: int = 0
    duplicate_source_game_id: int = 0
    source_to_many_internal: int = 0
    internal_to_many_source: int = 0
    seasons: dict[str, int] = field(default_factory=dict)
    leagues: dict[str, int] = field(default_factory=dict)
    status_counts: dict[str, int] = field(default_factory=dict)
    scheduled_at_present: int = 0
    scheduled_at_absent: int = 0
    findings: list[IdentityFinding] = field(default_factory=list)


@dataclass
class GamesVsIdentity:
    sport: str
    games_only: int = 0
    identity_only: int = 0
    both: int = 0
    id_mismatch: int = 0
    source_mismatch: int = 0
    mismatched_ids: tuple[str, ...] = ()


@dataclass
class IdentityAuditReport:
    rule_version: str
    measured_at: str
    sports: dict[str, SportIdentityCoverage]
    identity_artifact_rows: int
    identity_artifact_by_sport: dict[str, int]
    games_vs_identity: dict[str, GamesVsIdentity]


@dataclass
class IdentityMaterializeResult:
    appended: int
    skipped_existing: int
    conflicts: int
    sports_appended: dict[str, int]
    identity_artifact_rows: int


def source_system_for(sport: str) -> str:
    return SOURCE_SYSTEM_BY_SPORT.get(str(sport or "").strip(), "")


def source_field_for(sport: str) -> str:
    return SOURCE_FIELD_BY_SPORT.get(str(sport or "").strip(), "")


def mlb_internal_game_id(
    *,
    official_date: str,
    away_abbreviation: str,
    home_abbreviation: str,
    game_pk: str,
) -> str:
    """Preserve mlb.ingest.internal_game_id semantics, including UNK fallback."""
    date = str(official_date or "").replace("-", "")
    away = str(away_abbreviation or "UNK")
    home = str(home_abbreviation or "UNK")
    pk = str(game_pk or "")
    return f"MLB_{date}_{away}_{home}_{pk}"


def basketball_base_id(sport: str, game_date: str, away_id: str, home_id: str) -> str:
    return base_game_id(sport, game_date, away_id, home_id)


def parse_internal_game_id(raw: str) -> ParsedInternalGameId | None:
    text = str(raw or "").strip()
    if not text:
        return None
    mlb = _MLB_RE.fullmatch(text)
    if mlb:
        yyyymmdd, away, home, pk = mlb.group(1), mlb.group(2), mlb.group(3), mlb.group(4)
        if not _valid_yyyymmdd(yyyymmdd):
            return None
        return ParsedInternalGameId(
            sport="MLB",
            yyyymmdd=yyyymmdd,
            away_team_id=away,
            home_team_id=home,
            game_pk=pk,
        )
    bb = _BASKETBALL_RE.fullmatch(text)
    if bb:
        yyyymmdd = bb.group(2)
        if not _valid_yyyymmdd(yyyymmdd):
            return None
        rematch = int(bb.group(5)) if bb.group(5) else None
        return ParsedInternalGameId(
            sport=bb.group(1),
            yyyymmdd=yyyymmdd,
            away_team_id=bb.group(3),
            home_team_id=bb.group(4),
            rematch_n=rematch,
        )
    return None


def internal_game_id_format_ok(raw: str, sport: str | None = None) -> bool:
    parsed = parse_internal_game_id(raw)
    if parsed is None:
        return False
    if sport and parsed.sport != str(sport).strip():
        return False
    return True


def _valid_yyyymmdd(raw: str) -> bool:
    if len(raw) != 8 or not raw.isdigit():
        return False
    try:
        datetime.strptime(raw, "%Y%m%d")
    except ValueError:
        return False
    return True


def _date_digits(game_date: str) -> str:
    text = str(game_date or "").strip()
    iso = _ISO_DATE.fullmatch(text)
    if iso:
        return f"{iso.group(1)}{iso.group(2)}{iso.group(3)}"
    return text.replace("-", "")[:8]


def classify_identity_record(row: dict[str, Any]) -> IdentityResolution:
    """Classify one record in isolation. Cross-row checks belong to audit_identity_records."""
    gid = str(row.get("internal_game_id") or "").strip()
    sport = str(row.get("sport") or "").strip()
    source = str(row.get("source_game_id") or "").strip()
    if not gid:
        return IdentityResolution(
            status=IdentityStatus.MISSING,
            reason="internal_game_id is required",
            source_game_id=source,
            source_system=source_system_for(sport),
        )
    parsed = parse_internal_game_id(gid)
    if parsed is None:
        return IdentityResolution(
            status=IdentityStatus.INVALID,
            internal_game_id=gid,
            reason="malformed internal_game_id",
            source_game_id=source,
            source_system=source_system_for(sport),
        )
    if sport and parsed.sport != sport:
        return IdentityResolution(
            status=IdentityStatus.INVALID,
            internal_game_id=gid,
            reason=f"sport {sport!r} does not match id prefix {parsed.sport}",
            source_game_id=source,
            source_system=source_system_for(sport),
        )
    league = str(row.get("league") or "").strip()
    if league and sport in PHASE2_SPORTS and league != sport:
        return IdentityResolution(
            status=IdentityStatus.INVALID,
            internal_game_id=gid,
            reason=f"impossible league {league!r} for sport {sport}",
            source_game_id=source,
            source_system=source_system_for(sport),
        )
    game_date = str(row.get("game_date") or "").strip()
    if game_date:
        digits = _date_digits(game_date)
        if digits and digits != parsed.yyyymmdd:
            return IdentityResolution(
                status=IdentityStatus.INVALID,
                internal_game_id=gid,
                reason="game_date does not match internal_game_id date",
                source_game_id=source,
                source_system=source_system_for(sport),
            )
    if parsed.sport == "MLB" and source and parsed.game_pk != source:
        return IdentityResolution(
            status=IdentityStatus.CONFLICT,
            internal_game_id=gid,
            reason="MLB game_pk in id does not match source_game_id",
            source_game_id=source,
            source_system=source_system_for(sport),
        )
    season = str(row.get("season") or "").strip()
    if not season:
        return IdentityResolution(
            status=IdentityStatus.INVALID,
            internal_game_id=gid,
            reason="season is required",
            source_game_id=source,
            source_system=source_system_for(sport),
        )
    return IdentityResolution(
        status=IdentityStatus.VALID,
        internal_game_id=gid,
        reason="",
        source_game_id=source,
        source_system=source_system_for(sport),
    )


def resolve_internal_game_id(
    *,
    sport: str,
    source_game_id: str = "",
    internal_game_id: str = "",
    by_source: dict[tuple[str, str], str] | None = None,
) -> IdentityResolution:
    """Resolve identity from warehouse/source facts only. No ticker or date+team guess."""
    sport_key = str(sport or "").strip()
    src = str(source_game_id or "").strip()
    given = str(internal_game_id or "").strip()
    lookup = by_source or {}
    source_sys = source_system_for(sport_key)

    if not src and not given:
        return IdentityResolution(
            status=IdentityStatus.MISSING,
            reason="no source_game_id and no internal_game_id",
            source_system=source_sys,
        )

    looked_up = lookup.get((sport_key, src), "") if src else ""
    if src and (sport_key, src) not in lookup:
        if given:
            if not internal_game_id_format_ok(given, sport_key):
                return IdentityResolution(
                    status=IdentityStatus.INVALID,
                    internal_game_id=given,
                    reason="malformed internal_game_id",
                    source_game_id=src,
                    source_system=source_sys,
                )
            return IdentityResolution(
                status=IdentityStatus.MISSING,
                internal_game_id=given,
                reason="source_game_id is not in the identity catalog",
                source_game_id=src,
                source_system=source_sys,
            )
        return IdentityResolution(
            status=IdentityStatus.MISSING,
            reason="source_game_id is not in the identity catalog",
            source_game_id=src,
            source_system=source_sys,
        )

    if src and looked_up and given and looked_up != given:
        return IdentityResolution(
            status=IdentityStatus.CONFLICT,
            internal_game_id=given,
            reason="source_game_id maps to a different internal_game_id",
            source_game_id=src,
            source_system=source_sys,
        )

    chosen = given or looked_up
    if not internal_game_id_format_ok(chosen, sport_key):
        return IdentityResolution(
            status=IdentityStatus.INVALID,
            internal_game_id=chosen,
            reason="malformed internal_game_id",
            source_game_id=src,
            source_system=source_sys,
        )
    return IdentityResolution(
        status=IdentityStatus.VALID,
        internal_game_id=chosen,
        source_game_id=src,
        source_system=source_sys,
    )


def existing_identity_lookups(
    rows: Iterable[dict[str, Any]],
) -> tuple[dict[tuple[str, str], str], dict[tuple[str, str], str]]:
    """Unique warehouse_game_id / source_game_id → internal_game_id.

    Conflicting keys are dropped (fail closed). No date+team fallback.
    """
    by_wh: dict[tuple[str, str], str] = {}
    by_src: dict[tuple[str, str], str] = {}
    wh_conflict: set[tuple[str, str]] = set()
    src_conflict: set[tuple[str, str]] = set()
    for rec in rows:
        sport = str(rec.get("sport") or "").strip()
        gid = str(rec.get("internal_game_id") or "").strip()
        if not sport or not gid:
            continue
        wh = str(rec.get("warehouse_game_id") or "").strip()
        src = str(rec.get("source_game_id") or "").strip()
        if wh:
            key = (sport, wh)
            prev = by_wh.get(key)
            if prev is not None and prev != gid:
                wh_conflict.add(key)
            else:
                by_wh[key] = gid
        if src:
            key = (sport, src)
            prev = by_src.get(key)
            if prev is not None and prev != gid:
                src_conflict.add(key)
            else:
                by_src[key] = gid
    for key in wh_conflict:
        by_wh.pop(key, None)
    for key in src_conflict:
        by_src.pop(key, None)
    return by_wh, by_src


def apply_preserved_internal_ids(
    assigned: list[dict[str, Any]],
    by_warehouse: dict[tuple[str, str], str],
    by_source: dict[tuple[str, str], str],
) -> list[dict[str, Any]]:
    """Keep an existing valid-or-recorded ID. Do not silently repair invalid IDs."""
    out: list[dict[str, Any]] = []
    for row in assigned:
        rec = dict(row)
        sport = str(rec.get("sport") or "").strip()
        wh = str(rec.get("warehouse_game_id") or "").strip()
        src = str(rec.get("source_game_id") or "").strip()
        preserved = ""
        if wh:
            preserved = by_warehouse.get((sport, wh), "")
        if not preserved and src:
            preserved = by_source.get((sport, src), "")
        if preserved:
            rec["internal_game_id"] = preserved
        out.append(rec)
    return out


def audit_identity_records(rows: list[dict[str, Any]], *, sport: str | None = None) -> SportIdentityCoverage:
    scoped = []
    for rec in rows:
        item = {k: ("" if v is None else v) for k, v in rec.items()}
        if sport and str(item.get("sport") or "").strip() != sport:
            continue
        scoped.append(item)
    label = sport or (str(scoped[0].get("sport") or "") if scoped else "")
    coverage = SportIdentityCoverage(sport=label)
    coverage.total_games = len(scoped)
    if not scoped:
        coverage.status_counts = {s.value: 0 for s in IdentityStatus}
        return coverage

    gid_rows: dict[str, list[int]] = defaultdict(list)
    src_gids: dict[tuple[str, str], set[str]] = defaultdict(set)
    gid_sources: dict[str, set[str]] = defaultdict(set)
    gid_identity: dict[str, set[tuple[str, str, str, str, str]]] = defaultdict(set)
    rematch_keys: dict[tuple[str, str, str, str], list[int]] = defaultdict(list)

    for i, rec in enumerate(scoped):
        gid = str(rec.get("internal_game_id") or "").strip()
        sport_i = str(rec.get("sport") or "").strip()
        src = str(rec.get("source_game_id") or "").strip()
        if gid:
            gid_rows[gid].append(i)
            gid_identity[gid].add(
                (
                    sport_i,
                    str(rec.get("league") or sport_i).strip(),
                    str(rec.get("season") or "").strip(),
                    str(rec.get("game_date") or "").strip(),
                    f"{rec.get('away_team_id') or ''}|{rec.get('home_team_id') or ''}",
                )
            )
        if src:
            src_gids[(sport_i, src)].add(gid)
            if gid:
                gid_sources[gid].add(src)
        rematch_keys[
            (
                sport_i,
                str(rec.get("game_date") or "").strip(),
                str(rec.get("away_team_id") or "").strip(),
                str(rec.get("home_team_id") or "").strip(),
            )
        ].append(i)

    source_conflicts = {k for k, ids in src_gids.items() if len({x for x in ids if x}) > 1}
    gid_source_conflicts = {gid for gid, srcs in gid_sources.items() if len(srcs) > 1}
    gid_field_conflicts = {gid for gid, variants in gid_identity.items() if len(variants) > 1}

    ambiguous_rows: set[int] = set()
    for key, idxs in rematch_keys.items():
        if len(idxs) < 2 or not key[0] or not key[1]:
            continue
        fingerprints = []
        for i in idxs:
            rec = scoped[i]
            fingerprints.append(
                (
                    str(rec.get("scheduled_at") or rec.get("scheduled_start") or "").strip(),
                    str(rec.get("warehouse_game_id") or "").strip(),
                    str(rec.get("source_game_id") or "").strip(),
                    str(rec.get("event_ticker") or "").strip(),
                )
            )
        if len(set(fingerprints)) == 1:
            ambiguous_rows.update(idxs)

    status_counts = {s.value: 0 for s in IdentityStatus}
    findings: list[IdentityFinding] = []
    seasons: dict[str, int] = defaultdict(int)
    leagues: dict[str, int] = defaultdict(int)

    for i, rec in enumerate(scoped):
        gid = str(rec.get("internal_game_id") or "").strip()
        sport_i = str(rec.get("sport") or "").strip()
        src = str(rec.get("source_game_id") or "").strip()
        isolated = classify_identity_record(rec)
        status = isolated.status
        reason = isolated.reason
        if status is IdentityStatus.VALID:
            if gid in gid_field_conflicts:
                status = IdentityStatus.CONFLICT
                reason = "same internal_game_id has conflicting identity fields"
            elif src and (sport_i, src) in source_conflicts:
                status = IdentityStatus.CONFLICT
                reason = "source_game_id maps to multiple internal_game_id values"
            elif gid in gid_source_conflicts:
                status = IdentityStatus.CONFLICT
                reason = "internal_game_id maps to multiple source_game_id values"
            elif gid and len(gid_rows.get(gid, [])) > 1:
                status = IdentityStatus.DUPLICATE
                reason = "duplicate internal_game_id"
            elif i in ambiguous_rows:
                status = IdentityStatus.AMBIGUOUS
                reason = "rematch group has no distinguishing source/warehouse/schedule key"

        status_counts[status.value] += 1
        if status is not IdentityStatus.VALID:
            findings.append(
                IdentityFinding(
                    status=status,
                    internal_game_id=gid,
                    sport=sport_i,
                    reason=reason,
                    source_game_id=src,
                )
            )

        if gid:
            coverage.with_internal_game_id += 1
        else:
            coverage.without_internal_game_id += 1
        if src:
            coverage.with_source_game_id += 1
        else:
            coverage.without_source_game_id += 1
        season = str(rec.get("season") or "").strip()
        if season:
            seasons[season] += 1
        league = str(rec.get("league") or sport_i).strip()
        if league:
            leagues[league] += 1
        scheduled = str(rec.get("scheduled_at") or rec.get("scheduled_start") or "").strip()
        if scheduled:
            coverage.scheduled_at_present += 1
        else:
            coverage.scheduled_at_absent += 1

    coverage.unique_internal_game_id = len(gid_rows)
    coverage.duplicate_internal_game_id = sum(1 for ids in gid_rows.values() if len(ids) > 1)
    nonempty_src = {k: v for k, v in src_gids.items() if k[1]}
    coverage.unique_source_game_id = len(nonempty_src)
    coverage.duplicate_source_game_id = sum(1 for ids in nonempty_src.values() if len(ids) > 1)
    coverage.source_to_many_internal = len(source_conflicts)
    coverage.internal_to_many_source = len(gid_source_conflicts)
    coverage.seasons = dict(sorted(seasons.items()))
    coverage.leagues = dict(sorted(leagues.items()))
    coverage.status_counts = status_counts
    coverage.findings = findings
    return coverage


def game_from_row(row: dict[str, Any]) -> Any:
    """Build the Phase 1 Game from a games.csv or identity row. Does not guess IDs."""
    from roller.warehouse.entities import Game

    sport = str(row.get("sport") or "").strip()
    scheduled = str(row.get("scheduled_at") or row.get("scheduled_start") or "").strip()
    return Game(
        internal_game_id=str(row.get("internal_game_id") or "").strip(),
        sport=sport,
        season=str(row.get("season") or "").strip(),
        league=str(row.get("league") or sport).strip(),
        game_date=str(row.get("game_date") or "").strip(),
        home_team_id=str(row.get("home_team_id") or "").strip(),
        away_team_id=str(row.get("away_team_id") or "").strip(),
        source_game_id=str(row.get("source_game_id") or "").strip(),
        warehouse_game_id=str(row.get("warehouse_game_id") or "").strip(),
        event_ticker=str(row.get("event_ticker") or "").strip(),
        scheduled_at=scheduled,
        source_system=str(row.get("source_system") or source_system_for(sport)),
        identity_rule_version=str(row.get("identity_rule_version") or IDENTITY_RULE_VERSION),
    )


def identity_artifact_path(cfg: RollerConfig) -> Path:
    return cfg.root / "meta" / "game_identity.csv"


def canonical_games_csv(cfg: RollerConfig, sport: str, season: str) -> Path | None:
    try:
        path = cfg.dataset_path(sport, season, "games")
    except KeyError:
        return None
    return path if path.is_file() else None


def _frame_records(path: Path) -> list[dict[str, Any]]:
    frame = read_csv(path)
    return [{str(k): ("" if v is None else str(v)) for k, v in rec.items()} for rec in frame.to_dict("records")]


def _compare_games_to_identity(
    sport: str,
    games: list[dict[str, Any]],
    identity: list[dict[str, Any]],
) -> GamesVsIdentity:
    games_ids = {str(r.get("internal_game_id") or "").strip() for r in games}
    games_ids.discard("")
    ident_ids = {
        str(r.get("internal_game_id") or "").strip()
        for r in identity
        if str(r.get("sport") or "").strip() == sport
    }
    ident_ids.discard("")
    games_by_id = {str(r.get("internal_game_id") or "").strip(): r for r in games}
    ident_by_id = {
        str(r.get("internal_game_id") or "").strip(): r
        for r in identity
        if str(r.get("sport") or "").strip() == sport
    }
    both = games_ids & ident_ids
    source_mismatch = 0
    mismatched: list[str] = []
    for gid in sorted(both):
        g_src = str(games_by_id[gid].get("source_game_id") or "").strip()
        i_src = str(ident_by_id[gid].get("source_game_id") or "").strip()
        if g_src != i_src:
            source_mismatch += 1
            mismatched.append(gid)
    return GamesVsIdentity(
        sport=sport,
        games_only=len(games_ids - ident_ids),
        identity_only=len(ident_ids - games_ids),
        both=len(both),
        id_mismatch=0,
        source_mismatch=source_mismatch,
        mismatched_ids=tuple(mismatched[:20]),
    )


def audit_phase2_disk(cfg: RollerConfig) -> IdentityAuditReport:
    """Measure NBA/NCAAB/MLB identity from games.csv plus the identity artifact."""
    identity_path = identity_artifact_path(cfg)
    identity_rows: list[dict[str, Any]] = []
    if identity_path.is_file():
        identity_rows = _frame_records(identity_path)
    by_sport_ident: dict[str, int] = defaultdict(int)
    for rec in identity_rows:
        by_sport_ident[str(rec.get("sport") or "").strip() or "?"] += 1

    sports: dict[str, SportIdentityCoverage] = {}
    vs: dict[str, GamesVsIdentity] = {}
    for sport in PHASE2_SPORTS:
        game_rows: list[dict[str, Any]] = []
        for season in cfg.season_labels(sport):
            path = canonical_games_csv(cfg, sport, season)
            if path is None:
                continue
            game_rows.extend(_frame_records(path))
        sports[sport] = audit_identity_records(game_rows, sport=sport)
        vs[sport] = _compare_games_to_identity(sport, game_rows, identity_rows)

    return IdentityAuditReport(
        rule_version=IDENTITY_RULE_VERSION,
        measured_at=now_utc_iso(),
        sports=sports,
        identity_artifact_rows=len(identity_rows),
        identity_artifact_by_sport=dict(sorted(by_sport_ident.items())),
        games_vs_identity=vs,
    )


def _identity_row_from_game(game: dict[str, Any], *, now: str) -> dict[str, str]:
    sport = str(game.get("sport") or "").strip()
    src = str(game.get("source_game_id") or "").strip()
    mapped = bool(src)
    return {
        "internal_game_id": str(game.get("internal_game_id") or "").strip(),
        "sport": sport,
        "season": str(game.get("season") or "").strip(),
        "game_date": str(game.get("game_date") or "").strip(),
        "home_team_id": str(game.get("home_team_id") or "").strip(),
        "away_team_id": str(game.get("away_team_id") or "").strip(),
        "home_team_name": str(game.get("home_team_name") or "").strip(),
        "away_team_name": str(game.get("away_team_name") or "").strip(),
        "source_game_id": src,
        "warehouse_game_id": str(game.get("warehouse_game_id") or "").strip(),
        "event_ticker": str(game.get("event_ticker") or "").strip(),
        "kalshi_market_yes_home": str(game.get("kalshi_market_yes_home") or "").strip(),
        "kalshi_market_yes_away": str(game.get("kalshi_market_yes_away") or "").strip(),
        "mapping_status": MAPPING_MAPPED if mapped else MAPPING_UNMAPPED,
        "mapping_confidence": CONFIDENCE_HIGH if mapped else CONFIDENCE_NONE,
        "created_at": now,
        "updated_at": now,
    }


def extend_identity_artifact(
    cfg: RollerConfig,
    *,
    sports: tuple[str, ...] = PHASE2_SPORTS,
    write: bool = True,
) -> IdentityMaterializeResult:
    """Append missing Phase 2 games onto meta/game_identity.csv.

    Copies existing canonical IDs from games.csv. Does not mint new IDs.
    Does not rewrite existing identity rows. Does not guess from tickers.
    """
    path = identity_artifact_path(cfg)
    existing = read_csv_optional(path, IDENTITY_ARTIFACT_COLUMNS)
    existing_ids = set()
    existing_src: dict[tuple[str, str], str] = {}
    if not existing.empty:
        for rec in existing.to_dict("records"):
            gid = str(rec.get("internal_game_id") or "").strip()
            sport = str(rec.get("sport") or "").strip()
            src = str(rec.get("source_game_id") or "").strip()
            if gid:
                existing_ids.add(gid)
            if sport and src:
                existing_src[(sport, src)] = gid

    now = now_utc_iso()
    new_rows: list[dict[str, str]] = []
    skipped = 0
    conflicts = 0
    appended_by_sport: dict[str, int] = {s: 0 for s in sports}

    for sport in sports:
        if sport not in PHASE2_SPORTS:
            continue
        for season in cfg.season_labels(sport):
            games_path = canonical_games_csv(cfg, sport, season)
            if games_path is None:
                continue
            for game in _frame_records(games_path):
                gid = str(game.get("internal_game_id") or "").strip()
                src = str(game.get("source_game_id") or "").strip()
                if not gid:
                    continue
                if gid in existing_ids:
                    skipped += 1
                    continue
                if src and existing_src.get((sport, src)) and existing_src[(sport, src)] != gid:
                    conflicts += 1
                    continue
                isolated = classify_identity_record(game)
                if isolated.status in {IdentityStatus.INVALID, IdentityStatus.CONFLICT, IdentityStatus.AMBIGUOUS}:
                    conflicts += 1
                    continue
                row = _identity_row_from_game(game, now=now)
                new_rows.append(row)
                existing_ids.add(gid)
                if src:
                    existing_src[(sport, src)] = gid
                appended_by_sport[sport] += 1

    if write and new_rows:
        added = pd.DataFrame(new_rows)
        if existing.empty:
            out = added
        else:
            out = pd.concat([existing, added], ignore_index=True)
        for col in IDENTITY_ARTIFACT_COLUMNS:
            if col not in out.columns:
                out[col] = ""
        out = out[IDENTITY_ARTIFACT_COLUMNS]
        out = out.sort_values(["sport", "game_date", "internal_game_id"]).reset_index(drop=True)
        write_csv(path, out, IDENTITY_ARTIFACT_COLUMNS)
        total = len(out)
    else:
        total = (0 if existing.empty else len(existing)) + len(new_rows)

    return IdentityMaterializeResult(
        appended=len(new_rows),
        skipped_existing=skipped,
        conflicts=conflicts,
        sports_appended=appended_by_sport,
        identity_artifact_rows=total,
    )


def audit_report_to_dict(report: IdentityAuditReport) -> dict[str, Any]:
    sports = {}
    for sport, cov in report.sports.items():
        sports[sport] = {
            "total_games": cov.total_games,
            "with_internal_game_id": cov.with_internal_game_id,
            "without_internal_game_id": cov.without_internal_game_id,
            "unique_internal_game_id": cov.unique_internal_game_id,
            "duplicate_internal_game_id": cov.duplicate_internal_game_id,
            "with_source_game_id": cov.with_source_game_id,
            "without_source_game_id": cov.without_source_game_id,
            "unique_source_game_id": cov.unique_source_game_id,
            "duplicate_source_game_id": cov.duplicate_source_game_id,
            "source_to_many_internal": cov.source_to_many_internal,
            "internal_to_many_source": cov.internal_to_many_source,
            "seasons": cov.seasons,
            "leagues": cov.leagues,
            "status_counts": cov.status_counts,
            "scheduled_at_present": cov.scheduled_at_present,
            "scheduled_at_absent": cov.scheduled_at_absent,
            "finding_count": len(cov.findings),
            "findings": [
                {
                    "status": f.status.value,
                    "internal_game_id": f.internal_game_id,
                    "sport": f.sport,
                    "reason": f.reason,
                    "source_game_id": f.source_game_id,
                }
                for f in cov.findings[:50]
            ],
        }
    return {
        "rule_version": report.rule_version,
        "measured_at": report.measured_at,
        "identity_artifact_rows": report.identity_artifact_rows,
        "identity_artifact_by_sport": report.identity_artifact_by_sport,
        "sports": sports,
        "games_vs_identity": {
            sport: {
                "games_only": row.games_only,
                "identity_only": row.identity_only,
                "both": row.both,
                "source_mismatch": row.source_mismatch,
                "mismatched_ids": list(row.mismatched_ids),
            }
            for sport, row in report.games_vs_identity.items()
        },
    }


# Re-export for identity_build without implying a ticker join.
__all__ = [
    "IDENTITY_RULE_VERSION",
    "PHASE2_SPORTS",
    "SPORTS_IDENTITY_BUILD_MUST_NOT_REMINT",
    "SOURCE_SYSTEM_BY_SPORT",
    "IDENTITY_ARTIFACT_COLUMNS",
    "IdentityStatus",
    "IdentityResolution",
    "apply_preserved_internal_ids",
    "audit_identity_records",
    "audit_phase2_disk",
    "classify_identity_record",
    "existing_identity_lookups",
    "extend_identity_artifact",
    "game_from_row",
    "internal_game_id_format_ok",
    "mlb_internal_game_id",
    "parse_internal_game_id",
    "resolve_internal_game_id",
]
