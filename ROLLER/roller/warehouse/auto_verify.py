"""Phase 18 NBA warehouse verification. Read-only.

Inspects a published Phase 8 parquet warehouse after Phase 17 ingest.
Does not ingest, rewrite the warehouse, or start frontend work.
Does not write the live warehouse. Does not invent L2, ticks, fills,
settlement, or PBP↔candle PIT alignment.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from roller.config import RollerConfig
from roller.io_csv import sha256_file
from roller.research_query.models import (
    EntryCondition,
    EntryOp,
    ExitOutcome,
    PathCondition,
    PathOp,
    ResearchQuestion,
    ResearchStatus,
    TerminalOutcome,
    TouchOrdinal,
    Universe,
)
from roller.warehouse.auto_ingest import INGEST_RECORD_NAME
from roller.warehouse.conditional_backtest import run_conditional_backtest
from roller.warehouse.coverage import (
    CATALOG_VERSION,
    DATA_REQUIRED_CAPABILITIES,
    OBS_BASIS,
    OBS_RESOLUTION,
    OPERATION_REQUIRED_CAPABILITIES,
    PIT_FIELD,
    READY_CAPABILITIES,
    CapabilityName,
    get_catalog,
)
from roller.warehouse.hashing import partition_fingerprint
from roller.warehouse.identity import IDENTITY_RULE_VERSION, internal_game_id_format_ok, parse_internal_game_id
from roller.warehouse.layout import (
    OBS_SORT,
    OBSERVATION_BASIS_DIR,
    PBP_SORT,
    assert_layout_contract,
    orderbook_partition_exists,
    warehouse_root,
)
from roller.warehouse.partitioning import list_month_parquets, month_key
from roller.warehouse.research_compiler import compile_research

VERIFY_VERSION = "1.0.0"
PHASE18_SPORT = "NBA"
DEFAULT_SEASON = "2025-2026"

_ISO_MINUTE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00(?:Z|[+-]\d{2}:\d{2})$")
_FORBIDDEN_PBP_JOIN_COLS = frozenset(
    {
        "candle_available_at",
        "joined_available_at",
        "observation_available_at",
        "candle_minute",
        "pbp_candle_join",
        "aligned_to_candle",
        "yes_bid_close",
        "yes_bid_open",
        "yes_bid_high",
        "yes_bid_low",
        "yes_ask_close",
        "last_close_e4",
        "best_yes_bid_e4",
    }
)
_FORBIDDEN_OBS_FILL_COLS = frozenset(
    {
        "forward_filled",
        "interpolated",
        "invented_minute",
        "synthetic_tick",
        "fill_price",
    }
)
_EXPECTED_MATRIX = {
    CapabilityName.GAME.value: ResearchStatus.READY.value,
    CapabilityName.MARKET.value: ResearchStatus.READY.value,
    CapabilityName.GAME_MARKET_LINK.value: ResearchStatus.READY.value,
    CapabilityName.TRADABLE_YES_BID_1M.value: ResearchStatus.READY.value,
    CapabilityName.CANDLE_PIT.value: ResearchStatus.READY.value,
    CapabilityName.SETTLEMENT.value: ResearchStatus.READY.value,
    CapabilityName.PBP.value: ResearchStatus.READY.value,
    CapabilityName.ORDERBOOK.value: ResearchStatus.DATA_REQUIRED.value,
    CapabilityName.TICK.value: ResearchStatus.DATA_REQUIRED.value,
    CapabilityName.HISTORICAL_L2.value: ResearchStatus.DATA_REQUIRED.value,
    CapabilityName.HISTORICAL_TICK.value: ResearchStatus.DATA_REQUIRED.value,
    CapabilityName.PBP_MARKET_PIT_ALIGNMENT.value: ResearchStatus.OPERATION_REQUIRED.value,
}


class VerifyStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass
class CheckResult:
    name: str
    status: VerifyStatus
    detail: str = ""
    counts: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "detail": self.detail,
            "counts": dict(self.counts),
        }


@dataclass
class VerifyReport:
    status: VerifyStatus
    verify_version: str = VERIFY_VERSION
    sport: str = PHASE18_SPORT
    season: str = DEFAULT_SEASON
    warehouse_root: str = ""
    warehouse_version: str = ""
    catalog_version: str = CATALOG_VERSION
    identity_version: str = IDENTITY_RULE_VERSION
    manifest_fingerprint: str = ""
    ingest_fingerprint: str = ""
    ingest_record_present: bool = False
    observation_basis: str = OBS_BASIS
    resolution: str = OBS_RESOLUTION
    pit_field: str = PIT_FIELD
    identity: dict[str, Any] = field(default_factory=dict)
    markets: dict[str, Any] = field(default_factory=dict)
    observations: dict[str, Any] = field(default_factory=dict)
    settlements: dict[str, Any] = field(default_factory=dict)
    pbp: dict[str, Any] = field(default_factory=dict)
    capability_matrix: dict[str, str] = field(default_factory=dict)
    reproducibility: dict[str, Any] = field(default_factory=dict)
    checks: list[CheckResult] = field(default_factory=list)
    failures: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "verify_version": self.verify_version,
            "sport": self.sport,
            "season": self.season,
            "warehouse_root": self.warehouse_root,
            "warehouse_version": self.warehouse_version,
            "catalog_version": self.catalog_version,
            "identity_version": self.identity_version,
            "manifest_fingerprint": self.manifest_fingerprint,
            "ingest_fingerprint": self.ingest_fingerprint,
            "ingest_record_present": self.ingest_record_present,
            "observation_basis": self.observation_basis,
            "resolution": self.resolution,
            "pit_field": self.pit_field,
            "identity": dict(self.identity),
            "markets": dict(self.markets),
            "observations": dict(self.observations),
            "settlements": dict(self.settlements),
            "pbp": dict(self.pbp),
            "capability_matrix": dict(self.capability_matrix),
            "reproducibility": dict(self.reproducibility),
            "checks": [c.to_dict() for c in self.checks],
            "failures": list(self.failures),
        }


def _text(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _series_text(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series([""] * len(frame), index=frame.index, dtype="string")
    return frame[column].map(_text).astype("string")


def _ok(name: str, detail: str = "", **counts: Any) -> CheckResult:
    return CheckResult(name=name, status=VerifyStatus.PASS, detail=detail, counts=dict(counts))


def _fail(name: str, detail: str, **counts: Any) -> CheckResult:
    return CheckResult(name=name, status=VerifyStatus.FAIL, detail=detail, counts=dict(counts))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_parquet(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    if columns is None:
        return pd.read_parquet(path)
    try:
        return pd.read_parquet(path, columns=columns)
    except Exception:
        frame = pd.read_parquet(path)
        keep = [c for c in columns if c in frame.columns]
        return frame[keep] if keep else frame.iloc[:, 0:0]


def _yyyymmdd(game_date: str) -> str:
    return _text(game_date).replace("-", "")[:8]


def verify_question() -> ResearchQuestion:
    """Generic warehouse-backed question used for reproducibility."""
    return ResearchQuestion(
        universe=Universe(
            sports=(PHASE18_SPORT,),
            leagues=(PHASE18_SPORT,),
            seasons=(DEFAULT_SEASON,),
            markets=("kalshi",),
            market_data=("candles",),
            game_data=(),
            date_from="2025-10-10",
            date_to="2025-10-10",
        ),
        entry_conditions=(
            EntryCondition(
                id="e1",
                ordinal=TouchOrdinal.FIRST_TOUCH,
                price_e4=6300,
                operation=EntryOp.CROSS,
            ),
        ),
        path_conditions=(
            PathCondition(id="win", op=PathOp.REACH, price_e4=8700, outcome=ExitOutcome.WIN),
            PathCondition(id="loss", op=PathOp.REACH, price_e4=4100, outcome=ExitOutcome.LOSS),
        ),
        terminal=TerminalOutcome.BOTH,
        requested_dimensions=("HOLD_TO_SETTLEMENT",),
    )


def _l2_question() -> ResearchQuestion:
    q = verify_question()
    return ResearchQuestion(
        universe=Universe(
            sports=q.universe.sports,
            leagues=q.universe.leagues,
            seasons=q.universe.seasons,
            markets=q.universe.markets,
            market_data=("historical_l2",),
            game_data=q.universe.game_data,
            date_from=q.universe.date_from,
            date_to=q.universe.date_to,
        ),
        entry_conditions=q.entry_conditions,
        path_conditions=q.path_conditions,
        terminal=q.terminal,
        requested_dimensions=q.requested_dimensions,
    )


def _tick_question() -> ResearchQuestion:
    q = verify_question()
    return ResearchQuestion(
        universe=Universe(
            sports=q.universe.sports,
            leagues=q.universe.leagues,
            seasons=q.universe.seasons,
            markets=q.universe.markets,
            market_data=("historical_tick",),
            game_data=q.universe.game_data,
            date_from=q.universe.date_from,
            date_to=q.universe.date_to,
        ),
        entry_conditions=q.entry_conditions,
        path_conditions=q.path_conditions,
        terminal=q.terminal,
        requested_dimensions=q.requested_dimensions,
    )


def _pbp_align_question() -> ResearchQuestion:
    q = verify_question()
    return ResearchQuestion(
        universe=Universe(
            sports=q.universe.sports,
            leagues=q.universe.leagues,
            seasons=q.universe.seasons,
            markets=q.universe.markets,
            market_data=q.universe.market_data,
            game_data=("pbp",),
            date_from=q.universe.date_from,
            date_to=q.universe.date_to,
        ),
        entry_conditions=q.entry_conditions,
        path_conditions=q.path_conditions,
        terminal=q.terminal,
        requested_dimensions=("PBP_MARKET_PIT_ALIGNMENT",),
    )


def _verify_layout(root: Path) -> CheckResult:
    try:
        assert_layout_contract(root)
    except ValueError as exc:
        return _fail("layout", str(exc))
    extra = [
        p.name
        for p in (root / "observations").glob("basis=*")
        if p.name != OBSERVATION_BASIS_DIR
    ]
    if extra:
        return _fail("layout", f"non-canonical observation basis present: {extra}")
    if orderbook_partition_exists(root):
        return _fail("layout", "orderbook parquet must not be published")
    return _ok("layout", "canonical TRADABLE_YES_BID tree only")


def _verify_manifest(root: Path) -> tuple[CheckResult, dict[str, Any], str]:
    path = root / "manifest.json"
    if not path.is_file():
        return _fail("manifest", "missing warehouse manifest"), {}, ""
    man = _read_json(path)
    fp = sha256_file(path)
    errors: list[str] = []
    if man.get("observation_basis") != OBS_BASIS:
        errors.append(f"observation_basis={man.get('observation_basis')}")
    if man.get("observation_resolution") != OBS_RESOLUTION:
        errors.append(f"observation_resolution={man.get('observation_resolution')}")
    if man.get("candle_pit_field") != PIT_FIELD:
        errors.append(f"candle_pit_field={man.get('candle_pit_field')}")
    if man.get("pbp_pit_aligned_to_candles") is not False:
        errors.append("pbp_pit_aligned_to_candles must stay false")
    if man.get("tick_data_available") is not False:
        errors.append("tick_data_available must stay false")
    if man.get("orderbook_data_available") is not False:
        errors.append("orderbook_data_available must stay false")
    if man.get("candle_pit_available") is not True:
        errors.append("candle_pit_available must stay true")
    if man.get("available_at_preserved") is not True:
        errors.append("available_at_preserved must stay true")
    if errors:
        return _fail("manifest", "; ".join(errors), fingerprint=fp), man, fp
    return _ok("manifest", "frozen observation / PIT / capability flags", fingerprint=fp), man, fp


def _verify_identity(root: Path, season: str) -> tuple[CheckResult, dict[str, Any], dict[str, Any]]:
    games = _read_parquet(root / "games" / "games.parquet")
    markets = _read_parquet(root / "markets" / "markets.parquet")
    links = _read_parquet(root / "game_market_links" / "links.parquet")
    if games.empty:
        return _fail("identity", "canonical games missing"), {}, {}
    gids = _series_text(games, "internal_game_id")
    if int(gids.eq("").sum()) != 0:
        return _fail("identity", "blank internal_game_id"), {}, {}
    if int(gids.duplicated().sum()) != 0:
        return _fail("identity", "duplicate canonical identities", duplicates=int(gids.duplicated().sum())), {}, {}
    bad_fmt = [gid for gid in gids.tolist() if not internal_game_id_format_ok(gid, PHASE18_SPORT)]
    if bad_fmt:
        return _fail("identity", f"invalid internal_game_id format: {bad_fmt[:3]}", invalid=len(bad_fmt)), {}, {}

    dates = _series_text(games, "game_date")
    away = _series_text(games, "away_team_id")
    home = _series_text(games, "home_team_id")
    sport = _series_text(games, "sport")
    mismatch = 0
    for gid, gd, aw, ho, sp in zip(gids.tolist(), dates.tolist(), away.tolist(), home.tolist(), sport.tolist()):
        parsed = parse_internal_game_id(gid)
        if parsed is None:
            mismatch += 1
            continue
        if parsed.sport != PHASE18_SPORT or (sp and sp != PHASE18_SPORT):
            mismatch += 1
            continue
        if _yyyymmdd(gd) and parsed.yyyymmdd != _yyyymmdd(gd):
            mismatch += 1
            continue
        if aw and parsed.away_team_id != aw:
            mismatch += 1
            continue
        if ho and parsed.home_team_id != ho:
            mismatch += 1
            continue
    if mismatch:
        return _fail("identity", "internal_game_id is not deterministic vs game fields", mismatch=mismatch), {}, {}

    src = _series_text(games, "source_game_id")
    src_present = src[src != ""]
    if int(src_present.duplicated().sum()) != 0:
        return _fail(
            "identity",
            "ambiguous source_game_id mapping",
            ambiguous_source=int(src_present.duplicated().sum()),
        ), {}, {}

    if links.empty:
        return _fail("identity", "game-market links missing"), {}, {}
    mid = _series_text(links, "market_id")
    if mid.eq("").any():
        mid = _series_text(links, "ticker")
    if int(mid.eq("").sum()) != 0:
        return _fail("identity", "blank market identity on links"), {}, {}
    if int(mid.duplicated().sum()) != 0:
        return _fail("identity", "duplicate market IDs on links", duplicates=int(mid.duplicated().sum())), {}, {}
    link_status = _series_text(links, "link_status")
    ambiguous = int(link_status.eq("AMBIGUOUS").sum())
    if ambiguous:
        return _fail("identity", "ambiguous identity mappings", ambiguous=ambiguous), {}, {}
    link_gids = _series_text(links, "internal_game_id")
    game_set = set(gids.tolist())
    linked = link_status.eq("LINKED")
    unresolved = [gid for gid, ok in zip(link_gids.tolist(), linked.tolist()) if ok and gid not in game_set]
    if unresolved:
        return _fail("identity", "linked market does not resolve to a canonical game", unresolved=len(unresolved)), {}, {}

    market_tickers = _series_text(markets, "ticker") if not markets.empty else pd.Series(dtype="string")
    if not markets.empty and int(market_tickers.eq("").sum()) != 0:
        return _fail("identity", "blank ticker on markets"), {}, {}
    if not markets.empty and int(market_tickers.duplicated().sum()) != 0:
        return _fail("identity", "duplicate tickers", duplicates=int(market_tickers.duplicated().sum())), {}, {}

    identity = {
        "game_count": int(len(games)),
        "duplicate_games": 0,
        "ambiguous_links": 0,
        "unresolved_links": 0,
        "season": season,
    }
    market_counts = {
        "market_count": int(len(markets)),
        "link_count": int(len(links)),
        "linked_count": int(linked.sum()),
        "unlinked_count": int(link_status.eq("UNLINKED").sum()),
    }
    return _ok("identity", "canonical games and GameMarketLink resolve", **identity), identity, market_counts


def _verify_observations(root: Path, man: dict[str, Any], games: set[str]) -> tuple[CheckResult, dict[str, Any]]:
    obs_root = root / "observations"
    extra = [p.name for p in obs_root.glob("basis=*") if p.name != OBSERVATION_BASIS_DIR]
    if extra:
        return _fail("observations", f"another observation basis is present: {extra}"), {}
    directory = obs_root / OBSERVATION_BASIS_DIR
    files = list_month_parquets(directory)
    if not files:
        return _fail("observations", "no observation month partitions"), {}

    rows = 0
    silent_dup = 0
    flagged_dup = 0
    blank_ts = 0
    unsorted = 0
    bad_basis = 0
    invented = 0
    fill_flags = 0
    unresolved = 0
    months: dict[str, int] = {}
    sample_cols = [
        "internal_game_id",
        "market_id",
        "ticker",
        "available_at",
        "basis",
        "duplicate_key",
    ]
    for path in files:
        names = {f.name for f in pq.ParquetFile(path).schema_arrow}
        if _FORBIDDEN_OBS_FILL_COLS & names:
            fill_flags += 1
        present = [c for c in sample_cols if c in names]
        work = pd.read_parquet(path, columns=present)
        n = int(len(work))
        rows += n
        months[month_key(path)] = n
        ts = _series_text(work, "available_at")
        blank_ts += int(ts.eq("").sum())
        mid = _series_text(work, "market_id")
        if mid.eq("").all() and "ticker" in work.columns:
            mid = _series_text(work, "ticker")
        keys = mid + "\0" + ts
        flagged = (
            _series_text(work, "duplicate_key").eq("1")
            if "duplicate_key" in work.columns
            else pd.Series(False, index=work.index)
        )
        collision = keys.duplicated(keep=False)
        flagged_dup += int((collision & flagged).sum())
        silent_dup += int((collision & ~flagged).sum())
        gid = _series_text(work, "internal_game_id")
        if games:
            unresolved += int((~gid.isin(games) & gid.ne("")).sum())
        if "basis" in work.columns:
            bad_basis += int((~_series_text(work, "basis").isin({OBS_BASIS, ""})).sum())
        sort_cols = [c for c in OBS_SORT if c in work.columns]
        if sort_cols:
            ordered = work[sort_cols].apply(lambda col: col.map(_text))
            expected = ordered.sort_values(sort_cols, kind="mergesort")
            if not ordered.reset_index(drop=True).equals(expected.reset_index(drop=True)):
                unsorted += 1
        bad_minute = ~ts.eq("") & ~ts.map(lambda v: bool(_ISO_MINUTE.match(v)))
        invented += int(bad_minute.sum())

    counts = {
        "observation_count": rows,
        "observation_months": months,
        "observation_basis": OBS_BASIS,
        "resolution": OBS_RESOLUTION,
        "pit_field": PIT_FIELD,
        "silent_duplicates": silent_dup,
        "flagged_duplicate_rows": flagged_dup,
        "invented_minutes": invented,
    }
    if blank_ts:
        return _fail("observations", "blank available_at", blank=blank_ts, **counts), counts
    if silent_dup:
        return _fail(
            "observations",
            "silent duplicate (market_id, available_at)",
            **counts,
        ), counts
    if unsorted:
        return _fail(
            "observations",
            "observations are not sorted by internal_game_id, market_id, available_at",
            unsorted_months=unsorted,
            **counts,
        ), counts
    if bad_basis:
        return _fail("observations", "non-canonical observation basis rows", bad_basis=bad_basis, **counts), counts
    if invented:
        return _fail(
            "observations",
            "available_at is not a 1-minute candle PIT (invented or sub-minute stamps)",
            **counts,
        ), counts
    if fill_flags:
        return _fail("observations", "illegal forward-fill / interpolation columns present", **counts), counts
    if unresolved:
        return _fail("observations", "observation identity does not resolve", unresolved=unresolved, **counts), counts
    manifest_rows = int(man.get("observation_rows") or 0)
    if manifest_rows and manifest_rows != rows:
        return _fail(
            "observations",
            f"manifest observation_rows {manifest_rows} != parquet {rows}",
            **counts,
        ), counts
    detail = "TRADABLE_YES_BID / available_at / 1_MINUTE_CANDLE"
    if flagged_dup:
        detail += f"; {flagged_dup} publisher-flagged identical source collisions retained"
    return _ok("observations", detail, **counts), counts


def _verify_settlements(root: Path, man: dict[str, Any], games: set[str]) -> tuple[CheckResult, dict[str, Any]]:
    path = root / "settlements" / "settlements.parquet"
    frame = _read_parquet(path)
    if frame.empty:
        return _fail("settlements", "settlement parquet missing"), {}
    n = int(len(frame))
    manifest_n = int(man.get("settlements") or 0)
    if manifest_n and manifest_n != n:
        return _fail("settlements", f"manifest settlements {manifest_n} != parquet {n}", settlement_count=n), {}
    mid = _series_text(frame, "market_id")
    if int(mid.eq("").sum()) != 0:
        return _fail("settlements", "blank market_id"), {}
    if int(mid.duplicated().sum()) != 0:
        return _fail("settlements", "duplicate settlement market_id", duplicates=int(mid.duplicated().sum())), {}
    source = _series_text(frame, "source")
    if int((~source.isin({"kalshi_rest", ""})).sum()) != 0:
        return _fail("settlements", "settlement source is not canonical Suite / kalshi_rest"), {}
    if "kalshi_rest" not in set(source.tolist()):
        return _fail("settlements", "settlement source kalshi_rest is absent"), {}
    status = _series_text(frame, "settlement_status")
    allowed = {"YES", "NO", "INVALID", "MISSING"}
    if int((~status.isin(allowed)).sum()) != 0:
        return _fail("settlements", "unknown settlement_status"), {}
    if "home_score" in frame.columns or "away_score" in frame.columns:
        return _fail("settlements", "settlement inferred from score"), {}
    if "yes_bid_close" in frame.columns or "last_close_e4" in frame.columns:
        return _fail("settlements", "settlement inferred from price"), {}
    gid = _series_text(frame, "internal_game_id")
    unresolved = int((~gid.isin(games) & gid.ne("")).sum()) if games else 0
    if unresolved:
        return _fail("settlements", "settlement identity does not resolve", unresolved=unresolved), {}
    if "source_result" in frame.columns:
        invalid = frame[status.eq("INVALID")]
        src_result = _series_text(invalid, "source_result").str.lower()
        if not invalid.empty and int(src_result.isin({"yes", "no"}).sum()) != 0:
            return _fail("settlements", "INVALID rewritten from YES/NO"), {}
    counts = {
        "settlement_count": n,
        "YES": int(status.eq("YES").sum()),
        "NO": int(status.eq("NO").sum()),
        "INVALID": int(status.eq("INVALID").sum()),
        "MISSING": int(status.eq("MISSING").sum()),
        "source": "kalshi_rest",
    }
    return _ok("settlements", "Suite / kalshi_rest authority; INVALID remains INVALID", **counts), counts


def _verify_pbp(root: Path, man: dict[str, Any], games: set[str]) -> tuple[CheckResult, dict[str, Any]]:
    if man.get("pbp_pit_aligned_to_candles") is not False:
        return _fail("pbp", "pbp_pit_aligned_to_candles must be false"), {}
    directory = root / "pbp"
    files = list_month_parquets(directory)
    rows = 0
    dup = 0
    unsorted = 0
    unresolved = 0
    join_cols: list[str] = []
    months: dict[str, int] = {}
    for path in files:
        frame = pd.read_parquet(path)
        found = sorted(_FORBIDDEN_PBP_JOIN_COLS & set(frame.columns))
        if found:
            join_cols.extend(found)
        n = int(len(frame))
        rows += n
        months[month_key(path)] = n
        gid = _series_text(frame, "internal_game_id")
        ev = _series_text(frame, "event_number")
        keys = gid + "\0" + ev
        if {"internal_game_id", "event_number"}.issubset(frame.columns):
            dup += int(keys.duplicated().sum())
        if games:
            unresolved += int((~gid.isin(games) & gid.ne("")).sum())
        sort_cols = [c for c in PBP_SORT if c in frame.columns]
        if sort_cols:
            ordered = frame[sort_cols].apply(lambda col: col.map(_text))
            expected = ordered.sort_values(sort_cols, kind="mergesort")
            if not ordered.reset_index(drop=True).equals(expected.reset_index(drop=True)):
                unsorted += 1
    if join_cols:
        return _fail("pbp", f"persisted PBP↔candle join columns: {sorted(set(join_cols))}"), {}
    if dup:
        return _fail("pbp", "duplicate PBP identity", duplicates=dup), {}
    if unsorted:
        return _fail("pbp", "PBP event ordering is not deterministic", unsorted_months=unsorted), {}
    if unresolved:
        return _fail("pbp", "PBP identity does not resolve", unresolved=unresolved), {}
    manifest_rows = int(man.get("pbp_rows") or 0)
    if manifest_rows and manifest_rows != rows:
        return _fail("pbp", f"manifest pbp_rows {manifest_rows} != parquet {rows}", pbp_count=rows), {}
    counts = {
        "pbp_count": rows,
        "pbp_months": months,
        "pbp_pit_aligned_to_candles": False,
    }
    return _ok("pbp", "SEQUENCE_ONLY; no candle PIT join", **counts), counts


def _verify_capabilities(cfg: RollerConfig | None, man: dict[str, Any]) -> tuple[CheckResult, dict[str, str]]:
    matrix = dict(_EXPECTED_MATRIX)
    if cfg is not None:
        catalog = get_catalog(cfg, sport=PHASE18_SPORT, season=DEFAULT_SEASON)
        matrix = catalog.capability_matrix()
        if matrix != _EXPECTED_MATRIX:
            return _fail("capabilities", f"capability matrix is not truthful: {matrix}"), matrix
        ready = catalog.resolve(sorted(READY_CAPABILITIES, key=lambda c: c.value))
        if ready.status is not ResearchStatus.READY:
            return _fail("capabilities", "READY capabilities did not resolve READY"), matrix
        l2 = catalog.resolve([CapabilityName.HISTORICAL_L2])
        tick = catalog.resolve([CapabilityName.HISTORICAL_TICK])
        align = catalog.resolve([CapabilityName.PBP_MARKET_PIT_ALIGNMENT])
        if l2.status is not ResearchStatus.DATA_REQUIRED:
            return _fail("capabilities", "HISTORICAL_L2 must stay DATA_REQUIRED"), matrix
        if tick.status is not ResearchStatus.DATA_REQUIRED:
            return _fail("capabilities", "HISTORICAL_TICK must stay DATA_REQUIRED"), matrix
        if align.status is not ResearchStatus.OPERATION_REQUIRED:
            return _fail("capabilities", "PBP_MARKET_PIT_ALIGNMENT must stay OPERATION_REQUIRED"), matrix
        compile_l2 = compile_research(_l2_question(), cfg)
        compile_tick = compile_research(_tick_question(), cfg)
        compile_align = compile_research(_pbp_align_question(), cfg)
        compile_ready = compile_research(verify_question(), cfg)
        if compile_l2.status is not ResearchStatus.DATA_REQUIRED:
            return _fail("capabilities", "L2 request must compile DATA_REQUIRED, not a candle fallback"), matrix
        if compile_tick.status is not ResearchStatus.DATA_REQUIRED:
            return _fail("capabilities", "tick request must compile DATA_REQUIRED, not a candle fallback"), matrix
        if compile_align.status is not ResearchStatus.OPERATION_REQUIRED:
            return _fail("capabilities", "PBP↔candle PIT request must compile OPERATION_REQUIRED"), matrix
        if compile_ready.status is not ResearchStatus.READY:
            return _fail("capabilities", f"supported candle question compiled {compile_ready.status.value}"), matrix
    else:
        if man.get("tick_data_available") is not False or man.get("orderbook_data_available") is not False:
            return _fail("capabilities", "manifest claims unavailable data is present"), matrix
        if man.get("pbp_pit_aligned_to_candles") is not False:
            return _fail("capabilities", "manifest claims PBP PIT alignment"), matrix
    # Static lock: DATA_REQUIRED / OPERATION_REQUIRED sets never become READY.
    for cap in DATA_REQUIRED_CAPABILITIES:
        if matrix.get(cap.value) == ResearchStatus.READY.value:
            return _fail("capabilities", f"{cap.value} converted to READY"), matrix
    for cap in OPERATION_REQUIRED_CAPABILITIES:
        if matrix.get(cap.value) == ResearchStatus.READY.value:
            return _fail("capabilities", f"{cap.value} converted to READY"), matrix
    return _ok("capabilities", "capability matrix is truthful"), matrix


def _verify_reproducibility(cfg: RollerConfig) -> tuple[CheckResult, dict[str, Any]]:
    question = verify_question()
    first = run_conditional_backtest(question, cfg)
    second = run_conditional_backtest(question, cfg)
    plan = compile_research(question, cfg)
    fields = {
        "plan_hash": first.plan_hash,
        "result_hash": first.result_hash,
        "population": first.population,
        "classification_counts": dict(sorted(first.classification_counts.items())),
        "row_identities": [list(r.identity()) for r in first.rows],
        "warehouse_version": first.warehouse_version,
        "observation_basis": first.observation_basis,
        "pit_field": first.pit_field,
    }
    second_fields = {
        "plan_hash": second.plan_hash,
        "result_hash": second.result_hash,
        "population": second.population,
        "classification_counts": dict(sorted(second.classification_counts.items())),
        "row_identities": [list(r.identity()) for r in second.rows],
        "warehouse_version": second.warehouse_version,
        "observation_basis": second.observation_basis,
        "pit_field": second.pit_field,
    }
    if first.plan_hash != plan.plan_hash:
        return _fail("reproducibility", "backtest plan_hash != compile_research plan_hash"), fields
    if fields != second_fields:
        return _fail("reproducibility", "second run differed"), fields
    if first.observation_basis != OBS_BASIS or first.pit_field != PIT_FIELD:
        return _fail("reproducibility", "observation basis / PIT field drifted"), fields
    payload = {
        **fields,
        "compiler_version": plan.compiler_version,
        "status": first.status.value,
        "runs": 2,
    }
    return _ok("reproducibility", "identical plan_hash / result_hash / row identities", **payload), payload


def run_nba_warehouse_verify(
    cfg: RollerConfig | None = None,
    *,
    root: Path | None = None,
    season: str = DEFAULT_SEASON,
    include_research: bool = True,
) -> VerifyReport:
    """Verify a published NBA warehouse. Read-only. Fail closed."""
    if root is None:
        if cfg is None:
            cfg = RollerConfig()
        root = warehouse_root(cfg, PHASE18_SPORT, season)
    root = Path(root)
    checks: list[CheckResult] = []

    layout = _verify_layout(root)
    checks.append(layout)
    man_check, man, manifest_fp = _verify_manifest(root)
    checks.append(man_check)

    games_df = _read_parquet(root / "games" / "games.parquet", columns=["internal_game_id"])
    game_ids = {gid for gid in _series_text(games_df, "internal_game_id").tolist() if gid}
    ident_check, identity, markets = _verify_identity(root, season)
    checks.append(ident_check)
    obs_check, observations = _verify_observations(root, man, game_ids)
    checks.append(obs_check)
    settle_check, settlements = _verify_settlements(root, man, game_ids)
    checks.append(settle_check)
    pbp_check, pbp = _verify_pbp(root, man, game_ids)
    checks.append(pbp_check)
    cap_check, matrix = _verify_capabilities(cfg, man)
    checks.append(cap_check)

    ingest = _read_json(root / INGEST_RECORD_NAME)
    ingest_fp = _text(ingest.get("source_fingerprint"))
    reproducibility: dict[str, Any] = {}
    if include_research and cfg is not None and ident_check.status is VerifyStatus.PASS:
        repro_check, reproducibility = _verify_reproducibility(cfg)
        checks.append(repro_check)
    elif include_research and cfg is None:
        checks.append(_fail("reproducibility", "RollerConfig required for research reproducibility"))

    if man_check.status is VerifyStatus.PASS and ident_check.status is VerifyStatus.PASS:
        obs_files = list_month_parquets(root / "observations" / OBSERVATION_BASIS_DIR)
        settle = root / "settlements" / "settlements.parquet"
        games_p = root / "games" / "games.parquet"
        markets_p = root / "markets" / "markets.parquet"
        links_p = root / "game_market_links" / "links.parquet"
        file_fp = partition_fingerprint([p for p in (games_p, markets_p, links_p, settle, *obs_files) if p.is_file()])
        expected_games = int(man.get("games") or 0)
        if expected_games and expected_games != identity.get("game_count"):
            checks.append(
                _fail(
                    "fingerprints",
                    f"manifest games {expected_games} != parquet {identity.get('game_count')}",
                )
            )
        else:
            checks.append(_ok("fingerprints", "manifest counts match parquet", partition_fingerprint=file_fp))

    failures = tuple(c.detail for c in checks if c.status is VerifyStatus.FAIL)
    status = VerifyStatus.FAIL if failures else VerifyStatus.PASS
    warehouse_version = _text(man.get("updated_at")) or "nba_warehouse"
    return VerifyReport(
        status=status,
        season=season,
        warehouse_root=str(root),
        warehouse_version=warehouse_version,
        manifest_fingerprint=manifest_fp,
        ingest_fingerprint=ingest_fp,
        ingest_record_present=bool(ingest),
        identity=identity,
        markets=markets,
        observations=observations,
        settlements=settlements,
        pbp=pbp,
        capability_matrix=matrix,
        reproducibility=reproducibility,
        checks=checks,
        failures=failures,
    )


__all__ = [
    "VERIFY_VERSION",
    "VerifyReport",
    "VerifyStatus",
    "run_nba_warehouse_verify",
    "verify_question",
]
