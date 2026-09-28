"""Source-driven NBA warehouse ingest. Phase 17.

Discovers canonical / identity / Suite sources, reuses Phase 3–8 publishers,
validates, then atomically publishes the Phase 8 parquet tree.

Does not change Auto Roller rq_index ingest. Does not start Phase 18 verify.
Does not fetch the network. Does not invent L2, ticks, fills, or settlement.
Tests must not point this at the live canonical warehouse.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd

from roller.canonical.markets import markets_parquet
from roller.config import RollerConfig
from roller.ingest.games import load_sport_games
from roller.io_csv import sha256_file, write_json
from roller.timeutil import now_utc_iso
from roller.warehouse.coverage import get_catalog
from roller.warehouse.hashing import partition_fingerprint
from roller.warehouse.identity import IDENTITY_RULE_VERSION, extend_identity_artifact, identity_artifact_path
from roller.warehouse.layout import (
    OBSERVATION_BASIS_DIR,
    OBS_FINGERPRINT_COLS,
    PBP_FINGERPRINT_COLS,
    SETTLE_FINGERPRINT_COLS,
    assert_layout_contract,
    fingerprint_frame,
    orderbook_partition_exists,
    warehouse_root,
    write_nba_warehouse,
)
from roller.warehouse.layout_v0 import LINK_RULE_VERSION, crosswalk_path, observations_dir, pbp_dir
from roller.warehouse.market_link import build_and_write_nba_market_links, load_nba_crosswalk
from roller.warehouse.observations import project_nba_observations
from roller.warehouse.orderbook import declare_nba_orderbook_capability
from roller.warehouse.partitioning import list_month_csvs, list_month_parquets, month_key
from roller.warehouse.pbp_events import project_nba_pbp
from roller.warehouse.settlement import build_and_write_nba_settlements

PHASE17_SPORT = "NBA"
DEFAULT_SEASON = "2025-2026"
INGEST_RECORD_NAME = "ingest_run.json"
STAGING_SUFFIX = ".staging"
BACKUP_SUFFIX = ".old"
TRANSFORM_VERSIONS = {
    "identity": IDENTITY_RULE_VERSION,
    "link": LINK_RULE_VERSION,
    "observations": "1.0.0",
    "pbp": "1.0.0",
    "settlement": "1.0.0",
    "orderbook": "1.0.0",
    "layout": "1.0.0",
    "auto_ingest": "1.0.0",
}


class IngestStatus(str, Enum):
    UNCHANGED = "UNCHANGED"
    PUBLISHED = "PUBLISHED"
    FAILED = "INGEST_FAILED"


@dataclass(frozen=True)
class SourceFile:
    kind: str
    path: str
    present: bool
    sha256: str
    month: str = ""


@dataclass
class IngestResult:
    status: IngestStatus
    sport: str = PHASE17_SPORT
    season: str = DEFAULT_SEASON
    reason: str = ""
    source_files: tuple[SourceFile, ...] = ()
    source_fingerprint: str = ""
    skipped_stages: tuple[str, ...] = ()
    ran_stages: tuple[str, ...] = ()
    output_fingerprints: dict[str, str] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    catalog_version: str = ""
    warehouse_version: str = ""
    published_root: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "sport": self.sport,
            "season": self.season,
            "reason": self.reason,
            "source_files": [
                {
                    "kind": s.kind,
                    "path": s.path,
                    "present": s.present,
                    "sha256": s.sha256,
                    "month": s.month,
                }
                for s in self.source_files
            ],
            "source_fingerprint": self.source_fingerprint,
            "skipped_stages": list(self.skipped_stages),
            "ran_stages": list(self.ran_stages),
            "output_fingerprints": dict(self.output_fingerprints),
            "provenance": dict(self.provenance),
            "catalog_version": self.catalog_version,
            "warehouse_version": self.warehouse_version,
            "published_root": self.published_root,
        }


def _hash_if(path: Path) -> str:
    return sha256_file(path) if path.is_file() else ""


def _rel(cfg: RollerConfig, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(cfg.root.resolve()))
    except ValueError:
        return str(path)


def _optional_dataset(cfg: RollerConfig, season: str, name: str) -> Path | None:
    try:
        return cfg.dataset_path(PHASE17_SPORT, season, name)
    except KeyError:
        return None


def _suite_markets_path(cfg: RollerConfig, season: str) -> Path:
    _, _, wh = load_sport_games(cfg, PHASE17_SPORT, season)
    return markets_parquet(wh, cfg.season_meta(PHASE17_SPORT, season)["warehouse_sport"])


def discover_nba_sources(cfg: RollerConfig, season: str = DEFAULT_SEASON) -> list[SourceFile]:
    """What canonical / identity / Suite source exists. Not what FIRST80 needs."""
    files: list[SourceFile] = []

    def add(kind: str, path: Path | None, *, month: str = "") -> None:
        if path is None:
            files.append(SourceFile(kind=kind, path="", present=False, sha256="", month=month))
            return
        present = path.is_file()
        files.append(
            SourceFile(
                kind=kind,
                path=_rel(cfg, path) if path.exists() or path.parent.exists() else str(path),
                present=present,
                sha256=_hash_if(path),
                month=month,
            )
        )

    add("canonical_games", _optional_dataset(cfg, season, "games"))
    add("canonical_markets", _optional_dataset(cfg, season, "kalshi_markets"))
    add("identity", identity_artifact_path(cfg))
    add("suite_markets", _suite_markets_path(cfg, season))

    candles = _optional_dataset(cfg, season, "kalshi_candles")
    if candles is not None and candles.is_dir():
        for path in list_month_csvs(candles):
            add("candles_month", path, month=month_key(path))
    elif candles is None or not candles.exists():
        add("candles_month", candles)

    pbp = _optional_dataset(cfg, season, "pbp")
    if pbp is not None and pbp.is_dir():
        for path in list_month_csvs(pbp):
            add("pbp_month", path, month=month_key(path))
    elif pbp is None or not pbp.exists():
        add("pbp_month", pbp)

    return files


def source_fingerprint(sources: list[SourceFile]) -> str:
    payload = "\n".join(f"{s.kind}\t{s.month}\t{s.path}\t{s.sha256}\t{int(s.present)}" for s in sources)
    versions = "\n".join(f"{k}={v}" for k, v in sorted(TRANSFORM_VERSIONS.items()))
    return hashlib.sha256(f"{payload}\n{versions}".encode("utf-8")).hexdigest()


def ingest_record_path(root: Path) -> Path:
    return root / INGEST_RECORD_NAME


def read_ingest_record(root: Path) -> dict[str, Any] | None:
    path = ingest_record_path(root)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _stage_hashes(sources: list[SourceFile], kinds: set[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for src in sources:
        if src.kind in kinds:
            key = f"{src.kind}:{src.month}" if src.month else src.kind
            out[key] = src.sha256
    return out


def _last_stage_hashes(record: dict[str, Any] | None, kinds: set[str]) -> dict[str, str]:
    if not record:
        return {}
    stored = record.get("source_hashes") or {}
    return {k: v for k, v in stored.items() if k.split(":")[0] in kinds}


def _hashes_match(sources: list[SourceFile], record: dict[str, Any] | None, kinds: set[str]) -> bool:
    if record is None:
        return False
    if (record.get("transform_versions") or {}) != TRANSFORM_VERSIONS:
        return False
    return _stage_hashes(sources, kinds) == _last_stage_hashes(record, kinds)


def _output_fingerprints(root: Path) -> dict[str, str]:
    fps: dict[str, str] = {}
    for name, rel in (
        ("games", Path("games") / "games.parquet"),
        ("markets", Path("markets") / "markets.parquet"),
        ("links", Path("game_market_links") / "links.parquet"),
        ("settlements", Path("settlements") / "settlements.parquet"),
    ):
        path = root / rel
        fps[name] = _hash_if(path)
        if path.is_file() and name == "settlements":
            frame = pd.read_parquet(path)
            fp, n = fingerprint_frame(frame, SETTLE_FINGERPRINT_COLS)
            fps["settlements_rows"] = str(n)
            fps["settlements_content"] = fp
    obs = root / "observations" / OBSERVATION_BASIS_DIR
    fps["observations"] = partition_fingerprint(list_month_parquets(obs))
    if obs.is_dir():
        parts: list[str] = []
        rows = 0
        for path in list_month_parquets(obs):
            frame = pd.read_parquet(path)
            fp, n = fingerprint_frame(frame, OBS_FINGERPRINT_COLS)
            parts.append(f"{month_key(path)}:{fp}")
            rows += n
        fps["observations_content"] = ";".join(parts)
        fps["observations_rows"] = str(rows)
    pbp = root / "pbp"
    fps["pbp"] = partition_fingerprint(list_month_parquets(pbp))
    if pbp.is_dir():
        parts = []
        rows = 0
        for path in list_month_parquets(pbp):
            frame = pd.read_parquet(path)
            fp, n = fingerprint_frame(frame, PBP_FINGERPRINT_COLS)
            parts.append(f"{month_key(path)}:{fp}")
            rows += n
        fps["pbp_content"] = ";".join(parts)
        fps["pbp_rows"] = str(rows)
    return fps


def _validate_publishers(cfg: RollerConfig, season: str) -> None:
    identity = identity_artifact_path(cfg)
    if not identity.is_file():
        raise ValueError("missing identity artifact")
    ident = pd.read_csv(identity, dtype=str).fillna("")
    nba = ident[ident["sport"].astype(str) == PHASE17_SPORT] if not ident.empty and "sport" in ident.columns else ident
    if nba.empty or not nba["internal_game_id"].astype(str).str.strip().ne("").any():
        raise ValueError("missing identity")
    gids = nba["internal_game_id"].astype(str).str.strip()
    if int(gids.duplicated().sum()) != 0:
        raise ValueError("duplicate games")

    xwalk = load_nba_crosswalk(cfg)
    if xwalk.empty:
        raise ValueError("missing GameMarketLink crosswalk")
    if "link_status" in xwalk.columns and (xwalk["link_status"].astype(str) == "AMBIGUOUS").any():
        raise ValueError("ambiguous link")
    if "ticker" in xwalk.columns and int(xwalk["ticker"].astype(str).str.strip().duplicated().sum()) != 0:
        raise ValueError("duplicate markets")

    for path in list_month_parquets(observations_dir(cfg, PHASE17_SPORT, season)):
        frame = pd.read_parquet(path)
        if "duplicate_key" in frame.columns and (frame["duplicate_key"].astype(str) == "1").any():
            raise ValueError("duplicate observations")
        if "available_at" in frame.columns:
            linked = frame
            if "game_link_status" in frame.columns:
                linked = frame[frame["game_link_status"].astype(str) == "LINKED"]
            blank = linked["available_at"].astype(str).str.strip().eq("")
            if bool(blank.any()):
                raise ValueError("missing timestamp")
        if "yes_bid_close" in frame.columns:
            raw = frame["yes_bid_close"].astype(str).str.strip()
            nonempty = raw[raw != ""]
            if not nonempty.empty:
                coerced = pd.to_numeric(nonempty, errors="coerce")
                if coerced.isna().any():
                    raise ValueError("malformed price")

    for path in list_month_parquets(pbp_dir(cfg, PHASE17_SPORT, season)):
        frame = pd.read_parquet(path)
        if {"internal_game_id", "event_number"}.issubset(frame.columns):
            keys = frame["internal_game_id"].astype(str) + "\0" + frame["event_number"].astype(str)
            linked = frame
            if "game_link_status" in frame.columns:
                linked = frame[frame["game_link_status"].astype(str) == "LINKED"]
                keys = linked["internal_game_id"].astype(str) + "\0" + linked["event_number"].astype(str)
            if int(keys.duplicated().sum()) != 0:
                raise ValueError("duplicate PBP events")
        if "game_link_status" in frame.columns and (frame["game_link_status"].astype(str) == "AMBIGUOUS").any():
            raise ValueError("ambiguous link")


def _validate_staging(root: Path) -> None:
    assert_layout_contract(root)
    if orderbook_partition_exists(root):
        raise ValueError("orderbook parquet must not be published")
    man_path = root / "manifest.json"
    if not man_path.is_file():
        raise ValueError("missing warehouse manifest")
    man = json.loads(man_path.read_text(encoding="utf-8"))
    if man.get("observation_basis") != "TRADABLE_YES_BID":
        raise ValueError("observation basis must remain TRADABLE_YES_BID")
    if man.get("pbp_pit_aligned_to_candles") is not False:
        raise ValueError("pbp_pit_aligned_to_candles must stay false")
    if man.get("tick_data_available") is not False:
        raise ValueError("tick fabrication is not allowed")
    if man.get("orderbook_data_available") is not False:
        raise ValueError("orderbook fabrication is not allowed")
    if man.get("candle_pit_field") != "available_at":
        raise ValueError("available_at must remain the candle PIT field")
    settle = root / "settlements" / "settlements.parquet"
    if settle.is_file():
        frame = pd.read_parquet(settle)
        if "ticker" in frame.columns and int(frame["ticker"].astype(str).str.strip().duplicated().sum()) != 0:
            raise ValueError("duplicate settlements")


def _atomic_replace(staging: Path, published: Path) -> None:
    backup = published.with_name(published.name + BACKUP_SUFFIX)
    if backup.exists():
        shutil.rmtree(backup)
    replaced = False
    try:
        if published.exists():
            published.rename(backup)
            replaced = True
        staging.rename(published)
    except Exception:
        if replaced and backup.exists() and not published.exists():
            backup.rename(published)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def _write_ingest_record(
    root: Path,
    *,
    sources: list[SourceFile],
    fingerprint: str,
    acquire_time: str,
    output_fingerprints: dict[str, str],
    stages: list[str],
    skipped: list[str],
) -> dict[str, Any]:
    record = {
        "artifact": "nba_warehouse_ingest",
        "sport": PHASE17_SPORT,
        "acquire_time": acquire_time,
        "source_paths": [s.path for s in sources if s.path],
        "source_hashes": _stage_hashes(
            sources,
            {s.kind for s in sources},
        ),
        "source_fingerprint": fingerprint,
        "transform_versions": dict(TRANSFORM_VERSIONS),
        "output_fingerprints": output_fingerprints,
        "ran_stages": stages,
        "skipped_stages": skipped,
        "pbp_pit_aligned_to_candles": False,
        "observation_basis": "TRADABLE_YES_BID",
    }
    write_json(ingest_record_path(root), record)
    return record


def run_nba_warehouse_ingest(
    cfg: RollerConfig,
    *,
    season: str = DEFAULT_SEASON,
    force: bool = False,
) -> IngestResult:
    """Discover → normalize → validate → stage → publish. Fail closed."""
    acquire_time = now_utc_iso()
    sources = discover_nba_sources(cfg, season)
    fingerprint = source_fingerprint(sources)
    published = warehouse_root(cfg, PHASE17_SPORT, season)
    last = read_ingest_record(published)
    empty = IngestResult(
        status=IngestStatus.FAILED,
        season=season,
        source_files=tuple(sources),
        source_fingerprint=fingerprint,
        published_root=str(published),
    )

    games = next((s for s in sources if s.kind == "canonical_games"), None)
    if games is None or not games.present:
        return IngestResult(
            **{**empty.__dict__, "reason": "missing canonical games"},
        )

    if (
        not force
        and last is not None
        and last.get("source_fingerprint") == fingerprint
        and published.is_dir()
        and (published / "manifest.json").is_file()
    ):
        try:
            _validate_staging(published)
        except ValueError as exc:
            return IngestResult(**{**empty.__dict__, "reason": str(exc)})
        return IngestResult(
            status=IngestStatus.UNCHANGED,
            season=season,
            reason="source hashes unchanged",
            source_files=tuple(sources),
            source_fingerprint=fingerprint,
            skipped_stages=("identity", "links", "observations", "pbp", "settlement", "orderbook", "layout"),
            output_fingerprints=dict(last.get("output_fingerprints") or {}),
            provenance=dict(last),
            warehouse_version=str((json.loads((published / "manifest.json").read_text())).get("updated_at") or ""),
            published_root=str(published),
        )

    skipped: list[str] = []
    ran: list[str] = []
    staging = published.with_name(published.name + STAGING_SUFFIX)
    if staging.exists():
        shutil.rmtree(staging)

    try:
        identity_kinds = {"canonical_games", "identity"}
        link_kinds = {"canonical_games", "identity", "canonical_markets", "suite_markets"}
        obs_kinds = link_kinds | {"candles_month"}
        pbp_kinds = {"canonical_games", "identity", "pbp_month"}
        settle_kinds = {"suite_markets"} | link_kinds

        if force or not _hashes_match(sources, last, identity_kinds):
            extend_identity_artifact(cfg, sports=(PHASE17_SPORT,), write=True)
            ran.append("identity")
        else:
            skipped.append("identity")

        if force or not _hashes_match(sources, last, link_kinds):
            build_and_write_nba_market_links(cfg, season=season)
            ran.append("links")
        else:
            skipped.append("links")

        if force or not _hashes_match(sources, last, obs_kinds):
            project_nba_observations(cfg, season=season, write=True)
            ran.append("observations")
        else:
            skipped.append("observations")

        if force or not _hashes_match(sources, last, pbp_kinds):
            project_nba_pbp(cfg, season=season, write=True)
            ran.append("pbp")
        else:
            skipped.append("pbp")

        if force or not _hashes_match(sources, last, settle_kinds):
            build_and_write_nba_settlements(cfg, season=season)
            ran.append("settlement")
        else:
            skipped.append("settlement")

        declare_nba_orderbook_capability(cfg, season=season, write=True)
        ran.append("orderbook")

        _validate_publishers(cfg, season)
        write_nba_warehouse(cfg, season=season, dest=staging)
        ran.append("layout")
        _validate_staging(staging)
        fps = _output_fingerprints(staging)
        record = _write_ingest_record(
            staging,
            sources=sources,
            fingerprint=fingerprint,
            acquire_time=acquire_time,
            output_fingerprints=fps,
            stages=ran,
            skipped=skipped,
        )
        _atomic_replace(staging, published)
    except Exception as exc:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        return IngestResult(
            **{**empty.__dict__, "reason": f"{type(exc).__name__}: {exc}", "ran_stages": tuple(ran), "skipped_stages": tuple(skipped)},
        )

    catalog_version = ""
    warehouse_version = ""
    try:
        catalog = get_catalog(cfg, sport=PHASE17_SPORT, season=season)
        catalog_version = catalog.catalog_version
        warehouse_version = catalog.warehouse_version
    except Exception:
        man = json.loads((published / "manifest.json").read_text(encoding="utf-8"))
        warehouse_version = str(man.get("updated_at") or "")

    return IngestResult(
        status=IngestStatus.PUBLISHED,
        season=season,
        reason="published",
        source_files=tuple(sources),
        source_fingerprint=fingerprint,
        skipped_stages=tuple(skipped),
        ran_stages=tuple(ran),
        output_fingerprints=fps,
        provenance=record,
        catalog_version=catalog_version,
        warehouse_version=warehouse_version,
        published_root=str(published),
    )


def ingest_mlb_warehouse_desk(cfg: RollerConfig, *, season: str = DEFAULT_SEASON) -> dict[str, Any]:
    """Phase 17 MLB desk ingest. Does not rewrite the NBA warehouse or Confirm & Run."""
    from roller.warehouse.mlb_desk import ingest_mlb_warehouse

    return ingest_mlb_warehouse(cfg, season=season)


def ingest_ncaab_warehouse_desk(cfg: RollerConfig, *, season: str = DEFAULT_SEASON) -> dict[str, Any]:
    """Phase 17 NCAAB desk ingest. Does not rewrite NBA/MLB or Confirm & Run."""
    from roller.warehouse.ncaab_desk import ingest_ncaab_warehouse

    return ingest_ncaab_warehouse(cfg, season=season)


def ingest_tennis_warehouse_desks(cfg: RollerConfig, *, season: str = DEFAULT_SEASON) -> dict[str, Any]:
    """Phase 17 ATP+WTA desk ingest. One shared-tree read. Does not rewrite Confirm & Run."""
    from roller.warehouse.tennis_desk import ingest_tennis_warehouses

    return ingest_tennis_warehouses(cfg, season=season)
