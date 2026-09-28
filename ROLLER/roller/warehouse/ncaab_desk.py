"""NCAAB warehouse desk projectors (Phases 2–8, 17, 20).

Does not remint NCAAB_{YYYYMMDD}_{AWAY}_{HOME}.
Does not write the NBA crosswalk.
Does not call Confirm & Run execute / compiler / load_dataset.
Does not widen canonicalize MAPPING_MAPPED.
LAST_TRADE_PRINT is not applicable. Settlement is Kalshi result only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from roller.config import RollerConfig
from roller.ingest.games import load_sport_games
from roller.ingest.kalshi import candles_root, iter_candle_frames
from roller.io_csv import read_csv, read_csv_optional, sha256_file, write_json
from roller.research_query.models import (
    EntryCondition,
    EntryOp,
    ExitOutcome,
    PathCondition,
    PathOp,
    PriceField,
    ResearchQuestion,
    TerminalOutcome,
    TouchOrdinal,
    Universe,
)
from roller.timeutil import now_utc_iso
from roller.warehouse.desk import DEFAULT_SEASON
from roller.warehouse.entities import (
    ObservationBasis,
    Settlement,
    SettlementResult,
    kalshi_result_to_settlement,
)
from roller.warehouse.identity import (
    IDENTITY_ARTIFACT_COLUMNS,
    IDENTITY_RULE_VERSION,
    audit_phase2_disk,
    extend_identity_artifact,
    identity_artifact_path,
    source_system_for,
)
from roller.warehouse.layout import (
    GAME_SORT,
    LINK_SORT,
    MARKET_SORT,
    OBS_FINGERPRINT_COLS,
    OBS_SORT,
    PBP_FINGERPRINT_COLS,
    PBP_SORT,
    SETTLE_SORT,
    fingerprint_frame,
    orderbook_partition_exists,
    project_games,
    warehouse_root,
    write_sorted_parquet,
)
from roller.warehouse.layout_v0 import (
    LINK_RULE_VERSION,
    orderbook_capability_path,
    warehouse_v0_readme_path,
    warehouse_v0_root,
)
from roller.warehouse.market_link import (
    CROSSWALK_COLUMNS,
    MarketLinkBuild,
    audit_link_frame,
    build_market_links,
    write_market_links,
)
from roller.warehouse.observations import (
    ObservationBuild,
    _update_stats as _update_tradable_stats,
    project_observation_frame,
)
from roller.warehouse.partitioning import list_month_csvs, list_month_parquets, month_key, month_parquet
from roller.warehouse.pbp_events import PBP_COLUMNS, PbpBuild, project_pbp_frame, source_game_index
from roller.warehouse.settlement import (
    SETTLEMENT_COLUMNS,
    SettlementBuild,
    assert_not_inferred_settlement_source,
    coverage_report,
)

NCAAB_SPORT = "NCAAB"
NBA_CROSSWALK_SHA256 = "521fa0af3c674935518a42f8de499b548b94b71f6a20e45f305f2f5aaab982d8"
WAREHOUSE_V0_README = """# warehouse_v0 (provisional)

NCAAB Phase 3–7 projection. Not a Confirm & Run source.
Phase 8 publishes data/ncaab/2025_2026/derived/warehouse/.
TRADABLE_YES_BID only. LAST_TRADE_PRINT is not applicable.
"""

NCAAB_WAREHOUSE_README = """# NCAAB warehouse (Phase 8 physical layout)

Not a Confirm & Run source. Execution of the new desk reads this parquet tree.

observation_bases: TRADABLE_YES_BID
observation_resolution: 1_MINUTE
tick_data_available: false
orderbook_data_available: false
candle_pit_field: available_at
pbp_pit_aligned_to_candles: false
LAST_TRADE_PRINT is not applicable
"""

PHASE20_QUESTION = ResearchQuestion(
    universe=Universe(
        sports=("NCAAB",),
        leagues=("NCAAB",),
        seasons=("2025-2026",),
        markets=("kalshi",),
        market_data=("candles",),
        date_from="2025-11-03",
        date_to="2025-11-30",
    ),
    entry_conditions=(
        EntryCondition(
            id="ncaab_desk_cross_65",
            ordinal=TouchOrdinal.FIRST_TOUCH,
            price_e4=6500,
            operation=EntryOp.CROSS,
            price_field=PriceField.YES_BID_CLOSE.value,
        ),
    ),
    path_conditions=(
        PathCondition(id="win", op=PathOp.REACH, price_e4=8500, outcome=ExitOutcome.WIN),
        PathCondition(id="loss", op=PathOp.REACH, price_e4=4000, outcome=ExitOutcome.LOSS),
    ),
    terminal=TerminalOutcome.BOTH,
    requested_dimensions=("HOLD_TO_SETTLEMENT",),
)


def ncaab_crosswalk_path(cfg: RollerConfig) -> Path:
    return cfg.root / "meta" / "game_market_crosswalk_ncaab.parquet"


def ncaab_crosswalk_manifest_path(cfg: RollerConfig) -> Path:
    return cfg.root / "meta" / "game_market_crosswalk_ncaab.manifest.json"


def load_ncaab_crosswalk(cfg: RollerConfig) -> pd.DataFrame:
    path = ncaab_crosswalk_path(cfg)
    if not path.is_file():
        return pd.DataFrame(columns=CROSSWALK_COLUMNS)
    return pd.read_parquet(path)


def verify_ncaab_identity(cfg: RollerConfig, *, write: bool = True) -> dict[str, Any]:
    """Copy missing games.csv IDs onto the identity artifact. Do not remint."""
    before = audit_phase2_disk(cfg)
    gap = before.games_vs_identity["NCAAB"].games_only
    extended = extend_identity_artifact(cfg, sports=("NCAAB",), write=write)
    after = audit_phase2_disk(cfg)
    vs = after.games_vs_identity["NCAAB"]
    if vs.games_only != 0:
        raise ValueError(f"NCAAB identity still missing {vs.games_only} games.csv rows")
    if vs.source_mismatch != 0:
        raise ValueError("NCAAB identity source_game_id mismatch vs games.csv")
    return {
        "sport": NCAAB_SPORT,
        "gap_before": gap,
        "appended": extended.appended,
        "skipped_existing": extended.skipped_existing,
        "conflicts": extended.conflicts,
        "games_only_after": vs.games_only,
        "identity_ncaab_rows": after.identity_artifact_by_sport.get(NCAAB_SPORT, 0),
        "games_csv_rows": after.sports[NCAAB_SPORT].total_games,
        "reminted": False,
        "identity_rule_version": IDENTITY_RULE_VERSION,
    }


def build_ncaab_market_links(
    cfg: RollerConfig,
    *,
    season: str = DEFAULT_SEASON,
    identity: pd.DataFrame | None = None,
    suite: pd.DataFrame | None = None,
    canonical: pd.DataFrame | None = None,
) -> MarketLinkBuild:
    return build_market_links(
        cfg,
        sport=NCAAB_SPORT,
        season=season,
        identity=identity,
        suite=suite,
        canonical=canonical,
    )


def write_ncaab_market_links(cfg: RollerConfig, built: MarketLinkBuild) -> dict[str, Any]:
    return write_market_links(cfg, built, sport=NCAAB_SPORT)


def build_and_write_ncaab_market_links(cfg: RollerConfig, *, season: str = DEFAULT_SEASON) -> dict[str, Any]:
    built = build_ncaab_market_links(cfg, season=season)
    return write_ncaab_market_links(cfg, built)


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _iso(value: object) -> str:
    text = _text(value)
    if text.endswith("+00:00"):
        return text.replace("+00:00", "Z")
    return text


def _iso_series(series: pd.Series) -> pd.Series:
    ts = pd.to_datetime(series, utc=True, errors="coerce")
    out = pd.Series("", index=series.index, dtype=object)
    ok = ts.notna()
    out.loc[ok] = ts.loc[ok].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return out


def _e4_series(series: pd.Series) -> pd.Series:
    num = pd.to_numeric(series, errors="coerce")
    out = pd.Series("", index=series.index, dtype=object)
    ok = num.notna()
    out.loc[ok] = num.loc[ok].astype("int64").astype(str)
    return out


def suite_candles_to_raw(frame: pd.DataFrame) -> pd.DataFrame:
    """Map Suite yes_bid_*_e4 parquet onto observation CSV columns. Never from a print."""
    if frame is None or frame.empty or "yes_bid_close_e4" not in frame.columns:
        return pd.DataFrame()
    if "ticker" not in frame.columns:
        return pd.DataFrame()
    ts_src = frame["end_time"] if "end_time" in frame.columns else frame.get("end_period_ts")
    if ts_src is None:
        return pd.DataFrame()
    available_at = _iso_series(ts_src)
    close = _e4_series(frame["yes_bid_close_e4"])
    keep = close.ne("") & available_at.ne("") & frame["ticker"].map(_text).ne("")
    if not bool(keep.any()):
        return pd.DataFrame()
    work = frame.loc[keep].copy()
    available_at = available_at.loc[keep]
    vol = ""
    if "volume" in work.columns:
        vol = _e4_series(work["volume"])
    elif "volume_hundredths" in work.columns:
        vol = _e4_series(work["volume_hundredths"])
    out = pd.DataFrame(
        {
            "internal_game_id": "",
            "ticker": work["ticker"].map(_text),
            "available_at": available_at,
            "event_timestamp": available_at,
            "candle_timestamp": available_at,
            "ingested_at": "",
            "yes_bid_open": _e4_series(work["yes_bid_open_e4"]) if "yes_bid_open_e4" in work.columns else "",
            "yes_bid_high": _e4_series(work["yes_bid_high_e4"]) if "yes_bid_high_e4" in work.columns else "",
            "yes_bid_low": _e4_series(work["yes_bid_low_e4"]) if "yes_bid_low_e4" in work.columns else "",
            "yes_bid_close": close.loc[keep],
            "yes_ask_open": _e4_series(work["yes_ask_open_e4"]) if "yes_ask_open_e4" in work.columns else "",
            "yes_ask_high": _e4_series(work["yes_ask_high_e4"]) if "yes_ask_high_e4" in work.columns else "",
            "yes_ask_low": _e4_series(work["yes_ask_low_e4"]) if "yes_ask_low_e4" in work.columns else "",
            "yes_ask_close": _e4_series(work["yes_ask_close_e4"]) if "yes_ask_close_e4" in work.columns else "",
            "volume": vol,
            "source_dataset": "warehouse_candles_1m",
        }
    )
    return out.reset_index(drop=True)


def _union_by_key(canonical: pd.DataFrame, suite_raw: pd.DataFrame) -> pd.DataFrame:
    if suite_raw is None or suite_raw.empty:
        return canonical if canonical is not None else pd.DataFrame()
    if canonical is None or canonical.empty:
        return suite_raw
    left = canonical.copy()
    left["ticker"] = left["ticker"].map(_text)
    if "available_at" not in left.columns:
        left["available_at"] = left.get("event_timestamp", "")
    left["available_at"] = left["available_at"].map(_text)
    right = suite_raw.copy()
    right["ticker"] = right["ticker"].map(_text)
    right["available_at"] = right["available_at"].map(_text)
    left["_k"] = left["ticker"] + "\0" + left["available_at"]
    right["_k"] = right["ticker"] + "\0" + right["available_at"]
    extra = right.loc[~right["_k"].isin(set(left["_k"]))].drop(columns=["_k"])
    left = left.drop(columns=["_k"])
    if extra.empty:
        return left
    return pd.concat([left, extra], ignore_index=True)


def project_ncaab_tradable_observations(
    cfg: RollerConfig,
    *,
    season: str = DEFAULT_SEASON,
    crosswalk: pd.DataFrame | None = None,
    write: bool = True,
) -> tuple[ObservationBuild, dict[str, Any]]:
    if crosswalk is None:
        crosswalk = load_ncaab_crosswalk(cfg)
    if crosswalk.empty:
        raise ValueError("NCAAB GameMarketLink crosswalk is empty; run Phase 3 first")
    src_dir = cfg.dataset_path(NCAAB_SPORT, season, "kalshi_candles")
    out_dir = warehouse_v0_root(cfg, NCAAB_SPORT, season) / "observations" / "basis=tradable_yes_bid"
    stats = ObservationBuild()
    tickers: set[str] = set()
    linked_tickers: set[str] = set()
    unlinked_tickers: set[str] = set()
    games: set[str] = set()
    suite_months: dict[str, pd.DataFrame] = {}
    try:
        _, _, wh = load_sport_games(cfg, NCAAB_SPORT, season)
        if candles_root(wh, "ncaab").is_dir():
            for month, frame in iter_candle_frames(wh, "ncaab"):
                suite_months[month] = suite_candles_to_raw(frame)
    except (KeyError, FileNotFoundError, OSError):
        suite_months = {}
    months = sorted(set(month_key(p) for p in list_month_csvs(src_dir)) | set(suite_months))
    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        readme = warehouse_v0_readme_path(cfg, NCAAB_SPORT, season)
        if not readme.is_file():
            readme.write_text(WAREHOUSE_V0_README, encoding="utf-8")
    for month in months:
        canon_path = src_dir / f"month={month}.csv"
        canonical = read_csv(canon_path) if canon_path.is_file() else pd.DataFrame()
        raw = _union_by_key(canonical, suite_months.get(month, pd.DataFrame()))
        if raw.empty:
            continue
        projected = project_observation_frame(raw, crosswalk)
        _update_tradable_stats(stats, projected, month)
        tickers.update(projected["ticker"].astype(str))
        linked_tickers.update(projected.loc[projected["game_link_status"] == "LINKED", "ticker"].astype(str))
        unlinked_tickers.update(projected.loc[projected["game_link_status"] == "UNLINKED", "ticker"].astype(str))
        games.update(g for g in projected["internal_game_id"].astype(str) if g)
        if write:
            projected.to_parquet(month_parquet(out_dir, month), index=False)
    stats.tickers = len(tickers)
    stats.linked_tickers = len(linked_tickers)
    stats.unlinked_tickers = len(unlinked_tickers)
    stats.games_with_observations = len(games)
    stats.markets_with_observations = stats.tickers
    report = {
        "sport": NCAAB_SPORT,
        "basis": ObservationBasis.TRADABLE_YES_BID.value,
        "rows": stats.rows,
        "linked_rows": stats.linked_rows,
        "unlinked_rows": stats.unlinked_rows,
        "conflict_rows": stats.conflict_rows,
        "duplicate_keys": stats.duplicate_keys,
        "tickers": stats.tickers,
        "linked_tickers": stats.linked_tickers,
        "unlinked_tickers": stats.unlinked_tickers,
        "games_with_observations": stats.games_with_observations,
        "months": stats.months,
        "date_min": stats.date_min,
        "date_max": stats.date_max,
        "output_dir": str(out_dir),
        "updated_at": now_utc_iso(),
        "canonical_widened": False,
    }
    if write:
        write_json(out_dir / "manifest.json", report)
    return stats, report


def project_ncaab_pbp(
    cfg: RollerConfig,
    *,
    season: str = DEFAULT_SEASON,
    identity: pd.DataFrame | None = None,
    write: bool = True,
) -> tuple[PbpBuild, dict[str, Any]]:
    if identity is None:
        identity = read_csv_optional(identity_artifact_path(cfg))
    index = source_game_index(identity, sport=NCAAB_SPORT)
    src_dir = cfg.dataset_path(NCAAB_SPORT, season, "pbp")
    out_dir = warehouse_v0_root(cfg, NCAAB_SPORT, season) / "pbp"
    stats = PbpBuild()
    games: set[str] = set()
    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        readme = warehouse_v0_readme_path(cfg, NCAAB_SPORT, season)
        if not readme.is_file():
            readme.write_text(WAREHOUSE_V0_README, encoding="utf-8")
    for path in list_month_csvs(src_dir):
        month = month_key(path)
        raw = read_csv(path)
        projected = project_pbp_frame(raw, index)
        for col in PBP_COLUMNS:
            if col not in projected.columns:
                projected[col] = ""
        projected = projected[PBP_COLUMNS]
        stats.months[month] = int(len(projected))
        stats.rows += int(len(projected))
        stats.linked_rows += int((projected["game_link_status"] == "LINKED").sum())
        stats.conflict_rows += int((projected["game_link_status"] == "CONFLICT").sum())
        stats.unlinked_rows += int((projected["game_link_status"] == "UNLINKED").sum())
        stats.blank_event_timestamp += int(projected["event_timestamp"].astype(str).str.strip().eq("").sum())
        games.update(g for g in projected["internal_game_id"].astype(str) if g)
        if not projected.empty:
            times = projected["event_timestamp"].astype(str)
            nonempty = times[times.str.strip() != ""]
            if not nonempty.empty:
                lo, hi = nonempty.min(), nonempty.max()
                if not stats.date_min or lo < stats.date_min:
                    stats.date_min = lo
                if not stats.date_max or hi > stats.date_max:
                    stats.date_max = hi
        if write:
            projected.to_parquet(month_parquet(out_dir, month), index=False)
    stats.games_with_pbp = len(games)
    report = {
        "sport": NCAAB_SPORT,
        "rows": stats.rows,
        "linked_rows": stats.linked_rows,
        "conflict_rows": stats.conflict_rows,
        "unlinked_rows": stats.unlinked_rows,
        "blank_event_timestamp": stats.blank_event_timestamp,
        "games_with_pbp": stats.games_with_pbp,
        "months": stats.months,
        "date_min": stats.date_min,
        "date_max": stats.date_max,
        "output_dir": str(out_dir),
        "updated_at": now_utc_iso(),
        "pit_join_performed": False,
        "timestamps_invented": False,
        "pbp_pit_aligned_to_candles": False,
    }
    if write:
        write_json(out_dir / "manifest.json", report)
    return stats, report


def build_ncaab_settlements(
    cfg: RollerConfig,
    *,
    season: str = DEFAULT_SEASON,
    markets: pd.DataFrame | None = None,
    crosswalk: pd.DataFrame | None = None,
) -> SettlementBuild:
    source_hash = ""
    source_path = ""
    if markets is None:
        try:
            _, _, wh = load_sport_games(cfg, NCAAB_SPORT, season)
            from roller.canonical.markets import markets_parquet

            src = markets_parquet(wh, cfg.season_meta(NCAAB_SPORT, season)["warehouse_sport"])
            source_path = str(src)
            source_hash = sha256_file(src) if src.is_file() else ""
            markets = pd.read_parquet(src) if src.is_file() else pd.DataFrame()
        except (KeyError, FileNotFoundError, OSError):
            src = cfg.dataset_path(NCAAB_SPORT, season, "kalshi_markets")
            source_path = str(src)
            source_hash = sha256_file(src) if src.is_file() else ""
            markets = read_csv(src) if src.is_file() else pd.DataFrame()
    if crosswalk is None:
        crosswalk = load_ncaab_crosswalk(cfg)
        if crosswalk.empty:
            raise ValueError("NCAAB GameMarketLink crosswalk is empty; run Phase 3 first")
    assert_not_inferred_settlement_source(
        list(markets.columns) if markets is not None and not markets.empty else ["result"]
    )
    links: dict[str, tuple[str, str]] = {}
    for rec in crosswalk.to_dict("records"):
        ticker = _text(rec.get("ticker") or rec.get("market_id"))
        if ticker:
            links[ticker] = (_text(rec.get("internal_game_id")), _text(rec.get("link_status")))
    by_ticker: dict[str, list[dict[str, Any]]] = {}
    if markets is not None and not markets.empty and "ticker" in markets.columns:
        for rec in markets.to_dict("records"):
            ticker = _text(rec.get("ticker"))
            if not ticker:
                raise ValueError("malformed settlement: blank ticker")
            by_ticker.setdefault(ticker, []).append(rec)
    rows: list[dict[str, str]] = []
    extras = {"duplicate_source_rows": 0, "unlinked_rows": 0, "missing_rows": 0}
    provenance = f"suite:markets.parquet:{source_hash[:16] or 'nohash'}:result"
    for ticker in sorted(set(by_ticker) | set(links)):
        sources = by_ticker.get(ticker, [])
        gid, link_status = links.get(ticker, ("", "UNLINKED"))
        if not sources:
            extras["missing_rows"] += 1
            status = SettlementResult.MISSING
            source_result = ""
            value = ""
            settled_at = ""
        else:
            keys = {kalshi_result_to_settlement(rec.get("result")).value for rec in sources}
            if len(keys) > 1:
                raise ValueError(f"conflicting Kalshi settlements for {ticker}: {sorted(keys)}")
            if len(sources) > 1:
                extras["duplicate_source_rows"] += len(sources) - 1
            rec = sources[0]
            status = kalshi_result_to_settlement(rec.get("result"))
            source_result = _text(rec.get("result")).lower()
            value = "" if status is SettlementResult.MISSING else _text(rec.get("settlement_value_e4"))
            settled_at = _iso(rec.get("settlement_time") or rec.get("close_time") or rec.get("expiration_time"))
            Settlement(
                ticker=ticker,
                result=status,
                settlement_value_e4=None if value == "" else int(value) if str(value).lstrip("-").isdigit() else None,
            )
        if link_status != "LINKED":
            extras["unlinked_rows"] += 1
            gid = ""
            link_status = link_status or "UNLINKED"
        rows.append(
            {
                "market_id": ticker,
                "ticker": ticker,
                "internal_game_id": gid,
                "game_link_status": link_status,
                "source": "kalshi_markets.result",
                "source_market_id": ticker,
                "source_result": source_result,
                "source_identifier": ticker,
                "settlement_status": status.value,
                "settlement_value_e4": value,
                "source_settled_at": settled_at,
                "result_available_at": settled_at,
                "settlement_time": settled_at,
                "close_time": "",
                "expiration_time": "",
                "provenance": provenance,
                "sport": NCAAB_SPORT,
                "season": season,
            }
        )
    frame = pd.DataFrame(rows, columns=SETTLEMENT_COLUMNS)
    if not frame.empty:
        frame = frame.sort_values(["market_id"], kind="mergesort").reset_index(drop=True)
    status_counts = {s.value: 0 for s in SettlementResult}
    for status in frame["settlement_status"].astype(str) if not frame.empty else []:
        status_counts[status] = status_counts.get(status, 0) + 1
    games = set()
    if not frame.empty:
        settled = frame[frame["settlement_status"].isin(["YES", "NO", "INVALID"])]
        games = {g for g in settled["internal_game_id"].astype(str) if g}
    return SettlementBuild(
        settlements=frame,
        status_counts=status_counts,
        suite_tickers=int(markets["ticker"].map(_text).astype(bool).sum())
        if markets is not None and not markets.empty and "ticker" in markets.columns
        else 0,
        crosswalk_tickers=0 if crosswalk.empty else int(crosswalk["ticker"].map(_text).nunique()),
        duplicate_source_rows=extras["duplicate_source_rows"],
        unlinked_rows=extras["unlinked_rows"],
        missing_rows=extras["missing_rows"],
        games_with_settlement=len(games),
        input_hashes={"suite_markets": source_hash},
        source_path=source_path,
    )


def write_ncaab_settlements(cfg: RollerConfig, built: SettlementBuild, *, season: str = DEFAULT_SEASON) -> dict[str, Any]:
    dest = warehouse_v0_root(cfg, NCAAB_SPORT, season) / "settlements.parquet"
    dest.parent.mkdir(parents=True, exist_ok=True)
    built.settlements.to_parquet(dest, index=False)
    readme = warehouse_v0_readme_path(cfg, NCAAB_SPORT, season)
    if not readme.is_file():
        readme.write_text(WAREHOUSE_V0_README, encoding="utf-8")
    manifest = {
        "artifact": "ncaab_settlements",
        "sport": NCAAB_SPORT,
        "row_count": int(len(built.settlements)),
        "status_counts": built.status_counts,
        "source_path": built.source_path,
        "input_hashes": built.input_hashes,
        "sha256": sha256_file(dest),
        "updated_at": now_utc_iso(),
    }
    write_json(dest.with_suffix(".manifest.json"), manifest)
    return manifest


def declare_ncaab_orderbook_capability(cfg: RollerConfig, *, season: str = DEFAULT_SEASON) -> dict[str, Any]:
    snap_dir = cfg.dataset_path(NCAAB_SPORT, season, "games").parent / "kalshi_orderbook_snapshots"
    snapshot_rows = 0
    if snap_dir.is_dir():
        for path in list_month_csvs(snap_dir):
            frame = read_csv(path)
            snapshot_rows += int(len(frame))
    cap = {
        "sport": NCAAB_SPORT,
        "availability": "SOURCE_UNAVAILABLE",
        "historical_l2": "SOURCE_UNAVAILABLE",
        "snapshot_rows": snapshot_rows,
        "snapshot_note": "Canonical orderbook is a stub. Not historical L2 and not fills.",
        "depth": "NONE",
        "top_of_book": "NONE",
        "market_data_basis": "ONE_MINUTE_CANDLE",
        "updated_at": now_utc_iso(),
    }
    dest = orderbook_capability_path(cfg, NCAAB_SPORT, season)
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_json(dest, cap)
    readme = warehouse_v0_readme_path(cfg, NCAAB_SPORT, season)
    if not readme.is_file():
        readme.write_text(WAREHOUSE_V0_README, encoding="utf-8")
    return cap


def assert_ncaab_layout_contract(root: Path) -> None:
    tradable = root / "observations" / "basis=tradable_yes_bid"
    if not tradable.is_dir():
        raise ValueError("NCAAB warehouse must contain observations/basis=tradable_yes_bid")
    last_trade = root / "observations" / "basis=last_trade_print"
    if last_trade.is_dir() and any(last_trade.glob("*.parquet")):
        raise ValueError("NCAAB warehouse must not invent a last-trade partition")
    if orderbook_partition_exists(root):
        raise ValueError("NCAAB selected warehouse must not contain an orderbook parquet partition")


def _copy_month_dir(src: Path, dest: Path, *, sort_cols: list[str], fingerprint_cols: list[str]) -> dict[str, int]:
    dest.mkdir(parents=True, exist_ok=True)
    months: dict[str, int] = {}
    for path in list_month_parquets(src):
        month = month_key(path)
        frame = pd.read_parquet(path)
        write_sorted_parquet(frame, month_parquet(dest, month), sort_cols=sort_cols)
        written = pd.read_parquet(month_parquet(dest, month))
        fp, n = fingerprint_frame(frame, [c for c in fingerprint_cols if c in frame.columns])
        fp2, n2 = fingerprint_frame(written, [c for c in fingerprint_cols if c in written.columns])
        if fp != fp2 or n != n2:
            raise ValueError(f"fingerprint mismatch month {month} in {src}")
        months[month] = n
    return months


def write_ncaab_warehouse(cfg: RollerConfig, *, season: str = DEFAULT_SEASON) -> dict[str, Any]:
    dest = warehouse_root(cfg, NCAAB_SPORT, season)
    dest.mkdir(parents=True, exist_ok=True)
    identity = read_csv_optional(identity_artifact_path(cfg), IDENTITY_ARTIFACT_COLUMNS)
    games = project_games(identity, sport=NCAAB_SPORT)
    write_sorted_parquet(games, dest / "games" / "games.parquet", sort_cols=GAME_SORT)

    v0 = warehouse_v0_root(cfg, NCAAB_SPORT, season)
    markets_src = v0 / "markets.parquet"
    markets = pd.read_parquet(markets_src) if markets_src.is_file() else pd.DataFrame()
    write_sorted_parquet(markets, dest / "markets" / "markets.parquet", sort_cols=MARKET_SORT)

    links = load_ncaab_crosswalk(cfg)
    write_sorted_parquet(links, dest / "game_market_links" / "links.parquet", sort_cols=LINK_SORT)

    settle_src = v0 / "settlements.parquet"
    settles = pd.read_parquet(settle_src) if settle_src.is_file() else pd.DataFrame()
    write_sorted_parquet(settles, dest / "settlements" / "settlements.parquet", sort_cols=SETTLE_SORT)

    candle_months = _copy_month_dir(
        v0 / "observations" / "basis=tradable_yes_bid",
        dest / "observations" / "basis=tradable_yes_bid",
        sort_cols=OBS_SORT,
        fingerprint_cols=OBS_FINGERPRINT_COLS,
    )
    pbp_months = _copy_month_dir(
        v0 / "pbp",
        dest / "pbp",
        sort_cols=PBP_SORT,
        fingerprint_cols=list(PBP_FINGERPRINT_COLS),
    )
    assert_ncaab_layout_contract(dest)
    (dest / "README.md").write_text(NCAAB_WAREHOUSE_README, encoding="utf-8")
    manifest = {
        "artifact": "ncaab_warehouse",
        "sport": NCAAB_SPORT,
        "season": season,
        "observation_bases": ["TRADABLE_YES_BID"],
        "observation_resolution": "1_MINUTE",
        "tick_data_available": False,
        "orderbook_data_available": False,
        "candle_pit_available": True,
        "candle_pit_field": "available_at",
        "pbp_pit_aligned_to_candles": False,
        "source_system": source_system_for(NCAAB_SPORT),
        "identity_rule_version": IDENTITY_RULE_VERSION,
        "link_rule_version": LINK_RULE_VERSION,
        "games": int(len(games)),
        "markets": int(len(markets)),
        "links": int(len(links)),
        "settlements": int(len(settles)),
        "tradable_months": candle_months,
        "tradable_rows": int(sum(candle_months.values())),
        "observation_rows": int(sum(candle_months.values())),
        "pbp_months": pbp_months,
        "pbp_rows": int(sum(pbp_months.values())),
        "warehouse_root": str(dest),
        "updated_at": now_utc_iso(),
    }
    write_json(dest / "manifest.json", manifest)
    return manifest


def ingest_ncaab_warehouse(cfg: RollerConfig, *, season: str = DEFAULT_SEASON) -> dict[str, Any]:
    """Phase 17: identity copy → link → Suite∪canonical candles → PBP → settlement → layout."""
    identity = verify_ncaab_identity(cfg, write=True)
    links = build_and_write_ncaab_market_links(cfg, season=season)
    crosswalk = load_ncaab_crosswalk(cfg)
    _, candle_rep = project_ncaab_tradable_observations(cfg, season=season, crosswalk=crosswalk, write=True)
    _, pbp_rep = project_ncaab_pbp(cfg, season=season, write=True)
    settlements = build_ncaab_settlements(cfg, season=season, crosswalk=crosswalk)
    settle_rep = write_ncaab_settlements(cfg, settlements, season=season)
    orderbook = declare_ncaab_orderbook_capability(cfg, season=season)
    warehouse = write_ncaab_warehouse(cfg, season=season)
    return {
        "sport": NCAAB_SPORT,
        "identity": identity,
        "links": links,
        "tradable": candle_rep,
        "pbp": pbp_rep,
        "settlements": settle_rep,
        "orderbook": orderbook,
        "warehouse": warehouse,
        "link_audit": audit_link_frame(crosswalk),
        "settlement_coverage": coverage_report(settlements.settlements),
        "nba_crosswalk_sha256_expected": NBA_CROSSWALK_SHA256,
    }


def verify_ncaab_desk(cfg: RollerConfig, *, season: str = DEFAULT_SEASON) -> dict[str, Any]:
    """Phase 18 layout + catalog + compile. Does not rewrite 721."""
    dest = warehouse_root(cfg, NCAAB_SPORT, season)
    assert_ncaab_layout_contract(dest)
    from roller.warehouse.coverage import get_catalog
    from roller.warehouse.layout_v0 import crosswalk_path
    from roller.warehouse.research_compiler import compile_research

    nba_xwalk = crosswalk_path(cfg)
    ncaab_xwalk = ncaab_crosswalk_path(cfg)
    if ncaab_xwalk.resolve() == nba_xwalk.resolve():
        raise ValueError("NCAAB GameMarketLink must not share the NBA crosswalk path")
    nba_hash = sha256_file(nba_xwalk) if nba_xwalk.is_file() else ""
    if nba_hash and nba_hash != NBA_CROSSWALK_SHA256:
        raise ValueError(f"NBA crosswalk hash changed: {nba_hash}")
    catalog = get_catalog(cfg, sport=NCAAB_SPORT, season=season)
    plan = compile_research(PHASE20_QUESTION, cfg)
    return {
        "sport": NCAAB_SPORT,
        "warehouse_root": str(dest),
        "tradable_yes_bid_count": catalog.observations.get("tradable_yes_bid_count"),
        "last_trade_print_count": catalog.observations.get("last_trade_print_count"),
        "phase20_status": plan.status.value,
        "phase20_basis": plan.observation_basis,
        "ncaab_crosswalk": str(ncaab_xwalk),
        "nba_crosswalk": str(nba_xwalk),
        "nba_crosswalk_sha256": nba_hash,
        "orderbook_partition": False,
        "identity_rule_version": IDENTITY_RULE_VERSION,
        "golden_721_rewritten": False,
    }


def phase20_question() -> ResearchQuestion:
    return PHASE20_QUESTION
