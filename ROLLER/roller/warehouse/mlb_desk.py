"""MLB warehouse desk projectors (Phases 2–8, 17, 20).

Does not remint game_pk. Does not write the NBA crosswalk.
Does not call Confirm & Run execute / compiler / load_dataset.
LAST_TRADE_PRINT ≠ TRADABLE_YES_BID. Settlement is Kalshi result only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from roller.config import RollerConfig
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
    LAST_TRADE_COLS,
    YES_BID_COLS,
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

MLB_SPORT = "MLB"
WAREHOUSE_V0_README = """# warehouse_v0 (provisional)

MLB Phase 3–7 projection. Not a Confirm & Run source.
Phase 8 publishes data/mlb/2025_2026/derived/warehouse/.
LAST_TRADE_PRINT ≠ TRADABLE_YES_BID.
"""

LAST_TRADE_OBS_COLUMNS = [
    "ticker",
    "market_id",
    "internal_game_id",
    "source_internal_game_id",
    "game_link_status",
    "basis",
    "available_at",
    "event_timestamp",
    "candle_timestamp",
    "ingested_at",
    *LAST_TRADE_COLS,
    "volume",
    "print_count",
    "source",
    "duplicate_key",
]

MLB_PBP_COLUMNS = list(PBP_COLUMNS) + ["inning", "half", "outs", "balls", "strikes"]

MLB_WAREHOUSE_README = """# MLB warehouse (Phase 8 physical layout)

Not a Confirm & Run source. Execution of the new desk reads this parquet tree.

observation_bases: LAST_TRADE_PRINT, TRADABLE_YES_BID
observation_resolution: 1_MINUTE
tick_data_available: false
orderbook_data_available: false
candle_pit_field: available_at
pbp_pit_aligned_to_candles: false
LAST_TRADE_PRINT ≠ TRADABLE_YES_BID
"""

PHASE20_QUESTION = ResearchQuestion(
    universe=Universe(
        sports=("MLB",),
        leagues=("MLB",),
        seasons=("2025-2026",),
        markets=("kalshi",),
        market_data=("candles",),
        date_from="2025-04-01",
        date_to="2025-04-30",
    ),
    entry_conditions=(
        EntryCondition(
            id="mlb_desk_cross_65",
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


def mlb_crosswalk_path(cfg: RollerConfig) -> Path:
    return cfg.root / "meta" / "game_market_crosswalk_mlb.parquet"


def mlb_crosswalk_manifest_path(cfg: RollerConfig) -> Path:
    return cfg.root / "meta" / "game_market_crosswalk_mlb.manifest.json"


def load_mlb_crosswalk(cfg: RollerConfig) -> pd.DataFrame:
    path = mlb_crosswalk_path(cfg)
    if not path.is_file():
        return pd.DataFrame(columns=CROSSWALK_COLUMNS)
    return pd.read_parquet(path)


def verify_mlb_identity(cfg: RollerConfig, *, write: bool = True) -> dict[str, Any]:
    """Copy missing games.csv IDs onto the identity artifact. Do not remint."""
    before = audit_phase2_disk(cfg)
    gap = before.games_vs_identity["MLB"].games_only
    extended = extend_identity_artifact(cfg, sports=("MLB",), write=write)
    after = audit_phase2_disk(cfg)
    vs = after.games_vs_identity["MLB"]
    if vs.games_only != 0:
        raise ValueError(f"MLB identity still missing {vs.games_only} games.csv rows")
    if vs.source_mismatch != 0:
        raise ValueError("MLB identity source_game_id mismatch vs games.csv")
    return {
        "sport": MLB_SPORT,
        "gap_before": gap,
        "appended": extended.appended,
        "skipped_existing": extended.skipped_existing,
        "conflicts": extended.conflicts,
        "games_only_after": vs.games_only,
        "identity_mlb_rows": after.identity_artifact_by_sport.get(MLB_SPORT, 0),
        "games_csv_rows": after.sports[MLB_SPORT].total_games,
        "reminted": False,
        "identity_rule_version": IDENTITY_RULE_VERSION,
    }


def build_mlb_market_links(
    cfg: RollerConfig,
    *,
    season: str = DEFAULT_SEASON,
    identity: pd.DataFrame | None = None,
    suite: pd.DataFrame | None = None,
    canonical: pd.DataFrame | None = None,
) -> MarketLinkBuild:
    return build_market_links(
        cfg,
        sport=MLB_SPORT,
        season=season,
        identity=identity,
        suite=suite,
        canonical=canonical,
    )


def write_mlb_market_links(cfg: RollerConfig, built: MarketLinkBuild) -> dict[str, Any]:
    return write_market_links(cfg, built, sport=MLB_SPORT)


def build_and_write_mlb_market_links(cfg: RollerConfig, *, season: str = DEFAULT_SEASON) -> dict[str, Any]:
    built = build_mlb_market_links(cfg, season=season)
    return write_mlb_market_links(cfg, built)


def assert_no_yes_bid_columns(columns: list[str] | tuple[str, ...], *, path: Path | None = None) -> None:
    present = [c for c in YES_BID_COLS if c in set(columns)]
    if present:
        where = f" in {path}" if path else ""
        raise ValueError(f"LAST_TRADE_PRINT must not carry yes-bid columns{where}: {present}")


def project_last_trade_frame(frame: pd.DataFrame, crosswalk: pd.DataFrame, *, path: Path | None = None) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=LAST_TRADE_OBS_COLUMNS)
    assert_no_yes_bid_columns(list(frame.columns), path=path)
    work = frame.copy()
    work["ticker"] = work["ticker"].map(lambda v: "" if v is None else str(v).strip())
    work["available_at"] = work["available_at"].map(lambda v: "" if v is None else str(v).strip())
    work["source_internal_game_id"] = work.get("internal_game_id", pd.Series("", index=work.index)).map(
        lambda v: "" if v is None else str(v).strip()
    )
    lookup = crosswalk.loc[:, ["ticker", "internal_game_id", "link_status"]].drop_duplicates("ticker")
    lookup = lookup.rename(columns={"internal_game_id": "link_gid", "link_status": "link_status"})
    merged = work.merge(lookup, on="ticker", how="left")
    link_gid = merged["link_gid"].map(lambda v: "" if v is None else str(v).strip()) if "link_gid" in merged.columns else pd.Series("", index=merged.index)
    link_status = merged["link_status"].map(lambda v: "" if v is None else str(v).strip()) if "link_status" in merged.columns else pd.Series("", index=merged.index)
    source_gid = merged["source_internal_game_id"].map(lambda v: "" if v is None else str(v).strip())
    status: list[str] = []
    resolved: list[str] = []
    for gid, src, st in zip(link_gid.tolist(), source_gid.tolist(), link_status.tolist()):
        if st == "AMBIGUOUS":
            status.append("AMBIGUOUS")
            resolved.append("")
        elif st == "LINKED" and gid and src and gid != src:
            status.append("CONFLICT")
            resolved.append("")
        elif st == "LINKED" and gid:
            status.append("LINKED")
            resolved.append(gid)
        else:
            status.append("UNLINKED")
            resolved.append("")
    merged["internal_game_id"] = resolved
    merged["game_link_status"] = status
    merged["market_id"] = merged["ticker"]
    merged["basis"] = ObservationBasis.LAST_TRADE_PRINT.value
    key = merged["ticker"] + "\0" + merged["available_at"] + "\0" + merged["basis"]
    merged["duplicate_key"] = key.duplicated(keep=False).map(lambda v: "1" if bool(v) else "0")
    merged["source"] = merged.get("source_dataset", pd.Series("warehouse_last_trade_1m", index=merged.index)).map(
        lambda v: "" if v is None else str(v).strip()
    )
    if "event_timestamp" not in merged.columns:
        merged["event_timestamp"] = merged["available_at"]
    if "candle_timestamp" not in merged.columns:
        merged["candle_timestamp"] = merged.get("event_timestamp", merged["available_at"])
    if "ingested_at" not in merged.columns:
        merged["ingested_at"] = ""
    if "volume" not in merged.columns:
        merged["volume"] = ""
    if "print_count" not in merged.columns:
        merged["print_count"] = ""
    for col in LAST_TRADE_COLS:
        if col not in merged.columns:
            merged[col] = ""
    out = merged[LAST_TRADE_OBS_COLUMNS].copy()
    return out.sort_values(["ticker", "available_at"], kind="mergesort").reset_index(drop=True)


def _project_month_observations(
    cfg: RollerConfig,
    *,
    dataset: str,
    basis: ObservationBasis,
    season: str,
    crosswalk: pd.DataFrame,
    write: bool,
) -> tuple[ObservationBuild, dict[str, Any]]:
    src_dir = cfg.dataset_path(MLB_SPORT, season, dataset)
    out_dir = warehouse_v0_root(cfg, MLB_SPORT, season) / "observations" / (
        "basis=last_trade_print" if basis is ObservationBasis.LAST_TRADE_PRINT else "basis=tradable_yes_bid"
    )
    stats = ObservationBuild()
    tickers: set[str] = set()
    linked_tickers: set[str] = set()
    unlinked_tickers: set[str] = set()
    games: set[str] = set()
    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        readme = warehouse_v0_readme_path(cfg, MLB_SPORT, season)
        if not readme.is_file():
            readme.write_text(WAREHOUSE_V0_README, encoding="utf-8")
    for path in list_month_csvs(src_dir):
        month = month_key(path)
        raw = read_csv(path)
        if basis is ObservationBasis.LAST_TRADE_PRINT:
            projected = project_last_trade_frame(raw, crosswalk, path=path)
            stats.months[month] = int(len(projected))
            stats.rows += int(len(projected))
            stats.linked_rows += int((projected["game_link_status"] == "LINKED").sum())
            stats.unlinked_rows += int((projected["game_link_status"] == "UNLINKED").sum())
            stats.conflict_rows += int((projected["game_link_status"] == "CONFLICT").sum())
            stats.duplicate_keys += int((projected["duplicate_key"] == "1").sum())
            if not projected.empty:
                times = projected["available_at"].astype(str)
                lo, hi = times.min(), times.max()
                if not stats.date_min or lo < stats.date_min:
                    stats.date_min = lo
                if not stats.date_max or hi > stats.date_max:
                    stats.date_max = hi
        else:
            projected = project_observation_frame(raw, crosswalk, path=path)
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
        "sport": MLB_SPORT,
        "basis": basis.value,
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
    }
    if write:
        write_json(out_dir / "manifest.json", report)
    return stats, report


def project_mlb_last_trade_observations(
    cfg: RollerConfig,
    *,
    season: str = DEFAULT_SEASON,
    crosswalk: pd.DataFrame | None = None,
    write: bool = True,
) -> tuple[ObservationBuild, dict[str, Any]]:
    if crosswalk is None:
        crosswalk = load_mlb_crosswalk(cfg)
    if crosswalk.empty:
        raise ValueError("MLB GameMarketLink crosswalk is empty; run Phase 3 first")
    return _project_month_observations(
        cfg,
        dataset="kalshi_last_trade",
        basis=ObservationBasis.LAST_TRADE_PRINT,
        season=season,
        crosswalk=crosswalk,
        write=write,
    )


def project_mlb_tradable_observations(
    cfg: RollerConfig,
    *,
    season: str = DEFAULT_SEASON,
    crosswalk: pd.DataFrame | None = None,
    write: bool = True,
) -> tuple[ObservationBuild, dict[str, Any]]:
    if crosswalk is None:
        crosswalk = load_mlb_crosswalk(cfg)
    if crosswalk.empty:
        raise ValueError("MLB GameMarketLink crosswalk is empty; run Phase 3 first")
    return _project_month_observations(
        cfg,
        dataset="kalshi_candles",
        basis=ObservationBasis.TRADABLE_YES_BID,
        season=season,
        crosswalk=crosswalk,
        write=write,
    )


def project_mlb_pbp(
    cfg: RollerConfig,
    *,
    season: str = DEFAULT_SEASON,
    identity: pd.DataFrame | None = None,
    write: bool = True,
) -> tuple[PbpBuild, dict[str, Any]]:
    if identity is None:
        identity = read_csv_optional(identity_artifact_path(cfg))
    index = source_game_index(identity, sport=MLB_SPORT)
    src_dir = cfg.dataset_path(MLB_SPORT, season, "pbp")
    out_dir = warehouse_v0_root(cfg, MLB_SPORT, season) / "pbp"
    stats = PbpBuild()
    games: set[str] = set()
    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        readme = warehouse_v0_readme_path(cfg, MLB_SPORT, season)
        if not readme.is_file():
            readme.write_text(WAREHOUSE_V0_README, encoding="utf-8")
    for path in list_month_csvs(src_dir):
        month = month_key(path)
        raw = read_csv(path)
        projected = project_pbp_frame(
            raw,
            index,
            extra_columns=("inning", "half", "outs", "balls", "strikes"),
        )
        for col in MLB_PBP_COLUMNS:
            if col not in projected.columns:
                projected[col] = ""
        projected = projected[MLB_PBP_COLUMNS]
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
        "sport": MLB_SPORT,
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


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _iso(value: object) -> str:
    text = _text(value)
    if text.endswith("+00:00"):
        return text.replace("+00:00", "Z")
    return text


def build_mlb_settlements(
    cfg: RollerConfig,
    *,
    season: str = DEFAULT_SEASON,
    markets: pd.DataFrame | None = None,
    crosswalk: pd.DataFrame | None = None,
) -> SettlementBuild:
    src = cfg.dataset_path(MLB_SPORT, season, "kalshi_markets")
    source_hash = sha256_file(src) if src.is_file() else ""
    if markets is None:
        markets = read_csv(src) if src.is_file() else pd.DataFrame()
    if crosswalk is None:
        crosswalk = load_mlb_crosswalk(cfg)
        if crosswalk.empty:
            raise ValueError("MLB GameMarketLink crosswalk is empty; run Phase 3 first")
    assert_not_inferred_settlement_source(list(markets.columns) if markets is not None and not markets.empty else ["result"])
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
    provenance = f"canonical:{src.name}:{source_hash[:16] or 'nohash'}:kalshi_markets.result"
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
            settled_at = _iso(rec.get("settled_time") or rec.get("close_time") or rec.get("expiration_time"))
            Settlement(ticker=ticker, result=status, settlement_value_e4=None if value == "" else int(value) if value else None)
        if link_status != "LINKED":
            extras["unlinked_rows"] += 1
            gid = ""
            link_status = link_status or "UNLINKED"
        result_at = settled_at
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
                "result_available_at": result_at,
                "settlement_time": settled_at,
                "close_time": "",
                "expiration_time": "",
                "provenance": provenance,
                "sport": MLB_SPORT,
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
        suite_tickers=int(markets["ticker"].map(_text).astype(bool).sum()) if markets is not None and not markets.empty and "ticker" in markets.columns else 0,
        crosswalk_tickers=0 if crosswalk.empty else int(crosswalk["ticker"].map(_text).nunique()),
        duplicate_source_rows=extras["duplicate_source_rows"],
        unlinked_rows=extras["unlinked_rows"],
        missing_rows=extras["missing_rows"],
        games_with_settlement=len(games),
        input_hashes={"kalshi_markets": source_hash},
        source_path=str(src),
    )


def write_mlb_settlements(cfg: RollerConfig, built: SettlementBuild, *, season: str = DEFAULT_SEASON) -> dict[str, Any]:
    dest = warehouse_v0_root(cfg, MLB_SPORT, season) / "settlements.parquet"
    dest.parent.mkdir(parents=True, exist_ok=True)
    built.settlements.to_parquet(dest, index=False)
    readme = warehouse_v0_readme_path(cfg, MLB_SPORT, season)
    if not readme.is_file():
        readme.write_text(WAREHOUSE_V0_README, encoding="utf-8")
    manifest = {
        "artifact": "mlb_settlements",
        "sport": MLB_SPORT,
        "row_count": int(len(built.settlements)),
        "status_counts": built.status_counts,
        "source_path": built.source_path,
        "input_hashes": built.input_hashes,
        "sha256": sha256_file(dest),
        "updated_at": now_utc_iso(),
    }
    write_json(dest.with_suffix(".manifest.json"), manifest)
    return manifest


def _mlb_canonical_dir(cfg: RollerConfig, season: str) -> Path:
    return cfg.dataset_path(MLB_SPORT, season, "games").parent


def declare_mlb_orderbook_capability(cfg: RollerConfig, *, season: str = DEFAULT_SEASON) -> dict[str, Any]:
    snap_dir = _mlb_canonical_dir(cfg, season) / "kalshi_orderbook_snapshots"
    snapshot_rows = 0
    blank_gid = 0
    if snap_dir.is_dir():
        for path in list_month_csvs(snap_dir):
            frame = read_csv(path)
            snapshot_rows += int(len(frame))
            if "internal_game_id" in frame.columns:
                blank_gid += int(frame["internal_game_id"].map(_text).eq("").sum())
            else:
                blank_gid += int(len(frame))
    cap = {
        "sport": MLB_SPORT,
        "availability": "SOURCE_UNAVAILABLE",
        "historical_l2": "SOURCE_UNAVAILABLE",
        "snapshot_rows": snapshot_rows,
        "snapshot_blank_internal_game_id": blank_gid,
        "snapshot_note": "Live Sep snapshots are not historical L2 and are not fills.",
        "depth": "NONE",
        "top_of_book": "NONE",
        "market_data_basis": "LAST_TRADE_PRINT+ONE_MINUTE_CANDLE",
        "updated_at": now_utc_iso(),
    }
    dest = orderbook_capability_path(cfg, MLB_SPORT, season)
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_json(dest, cap)
    readme = warehouse_v0_readme_path(cfg, MLB_SPORT, season)
    if not readme.is_file():
        readme.write_text(WAREHOUSE_V0_README, encoding="utf-8")
    return cap


def assert_mlb_layout_contract(root: Path) -> None:
    last_trade = root / "observations" / "basis=last_trade_print"
    tradable = root / "observations" / "basis=tradable_yes_bid"
    if not last_trade.is_dir():
        raise ValueError("MLB warehouse must contain observations/basis=last_trade_print")
    if not tradable.is_dir():
        raise ValueError("MLB warehouse must contain observations/basis=tradable_yes_bid")
    if orderbook_partition_exists(root):
        raise ValueError("MLB selected warehouse must not contain an orderbook parquet partition")


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


def write_mlb_warehouse(cfg: RollerConfig, *, season: str = DEFAULT_SEASON) -> dict[str, Any]:
    dest = warehouse_root(cfg, MLB_SPORT, season)
    dest.mkdir(parents=True, exist_ok=True)
    identity = read_csv_optional(identity_artifact_path(cfg), IDENTITY_ARTIFACT_COLUMNS)
    games = project_games(identity, sport=MLB_SPORT)
    write_sorted_parquet(games, dest / "games" / "games.parquet", sort_cols=GAME_SORT)

    v0 = warehouse_v0_root(cfg, MLB_SPORT, season)
    markets_src = v0 / "markets.parquet"
    markets = pd.read_parquet(markets_src) if markets_src.is_file() else pd.DataFrame()
    write_sorted_parquet(markets, dest / "markets" / "markets.parquet", sort_cols=MARKET_SORT)

    links = load_mlb_crosswalk(cfg)
    write_sorted_parquet(links, dest / "game_market_links" / "links.parquet", sort_cols=LINK_SORT)

    settle_src = v0 / "settlements.parquet"
    settles = pd.read_parquet(settle_src) if settle_src.is_file() else pd.DataFrame()
    write_sorted_parquet(settles, dest / "settlements" / "settlements.parquet", sort_cols=SETTLE_SORT)

    last_months = _copy_month_dir(
        v0 / "observations" / "basis=last_trade_print",
        dest / "observations" / "basis=last_trade_print",
        sort_cols=OBS_SORT,
        fingerprint_cols=["ticker", "internal_game_id", "available_at", "last_close_e4", "basis", "game_link_status"],
    )
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
        fingerprint_cols=list(PBP_FINGERPRINT_COLS) + ["inning", "half"],
    )
    assert_mlb_layout_contract(dest)
    (dest / "README.md").write_text(MLB_WAREHOUSE_README, encoding="utf-8")
    manifest = {
        "artifact": "mlb_warehouse",
        "sport": MLB_SPORT,
        "season": season,
        "observation_bases": ["LAST_TRADE_PRINT", "TRADABLE_YES_BID"],
        "observation_resolution": "1_MINUTE",
        "tick_data_available": False,
        "orderbook_data_available": False,
        "candle_pit_available": True,
        "candle_pit_field": "available_at",
        "pbp_pit_aligned_to_candles": False,
        "source_system": source_system_for(MLB_SPORT),
        "identity_rule_version": IDENTITY_RULE_VERSION,
        "link_rule_version": LINK_RULE_VERSION,
        "games": int(len(games)),
        "markets": int(len(markets)),
        "links": int(len(links)),
        "settlements": int(len(settles)),
        "last_trade_months": last_months,
        "last_trade_rows": int(sum(last_months.values())),
        "tradable_months": candle_months,
        "tradable_rows": int(sum(candle_months.values())),
        "pbp_months": pbp_months,
        "pbp_rows": int(sum(pbp_months.values())),
        "warehouse_root": str(dest),
        "updated_at": now_utc_iso(),
    }
    write_json(dest / "manifest.json", manifest)
    return manifest


def ingest_mlb_warehouse(cfg: RollerConfig, *, season: str = DEFAULT_SEASON) -> dict[str, Any]:
    """Phase 17: identity copy → link → dual observations → PBP → settlement → layout."""
    identity = verify_mlb_identity(cfg, write=True)
    links = build_and_write_mlb_market_links(cfg, season=season)
    crosswalk = load_mlb_crosswalk(cfg)
    _, last_rep = project_mlb_last_trade_observations(cfg, season=season, crosswalk=crosswalk, write=True)
    _, candle_rep = project_mlb_tradable_observations(cfg, season=season, crosswalk=crosswalk, write=True)
    _, pbp_rep = project_mlb_pbp(cfg, season=season, write=True)
    settlements = build_mlb_settlements(cfg, season=season, crosswalk=crosswalk)
    settle_rep = write_mlb_settlements(cfg, settlements, season=season)
    orderbook = declare_mlb_orderbook_capability(cfg, season=season)
    warehouse = write_mlb_warehouse(cfg, season=season)
    return {
        "sport": MLB_SPORT,
        "identity": identity,
        "links": links,
        "last_trade": last_rep,
        "tradable": candle_rep,
        "pbp": pbp_rep,
        "settlements": settle_rep,
        "orderbook": orderbook,
        "warehouse": warehouse,
        "link_audit": audit_link_frame(crosswalk),
        "settlement_coverage": coverage_report(settlements.settlements),
    }


def verify_mlb_desk(cfg: RollerConfig, *, season: str = DEFAULT_SEASON) -> dict[str, Any]:
    """Phase 18 layout + catalog + compile. Does not rewrite 554 / 1661."""
    dest = warehouse_root(cfg, MLB_SPORT, season)
    assert_mlb_layout_contract(dest)
    from roller.warehouse.coverage import get_catalog
    from roller.warehouse.layout_v0 import crosswalk_path
    from roller.warehouse.research_compiler import compile_research

    man = json.loads((dest / "manifest.json").read_text(encoding="utf-8")) if (dest / "manifest.json").is_file() else {}
    catalog = get_catalog(cfg, sport=MLB_SPORT, season=season)
    plan = compile_research(PHASE20_QUESTION, cfg)
    nba_xwalk = crosswalk_path(cfg)
    mlb_xwalk = mlb_crosswalk_path(cfg)
    if mlb_xwalk.resolve() == nba_xwalk.resolve():
        raise ValueError("MLB GameMarketLink must not share the NBA crosswalk path")
    last_months = sorted((man.get("last_trade_months") or {}).keys())
    candle_months = sorted((man.get("tradable_months") or {}).keys())
    missing_vs_candle = [m for m in candle_months if m not in set(last_months)]
    return {
        "sport": MLB_SPORT,
        "warehouse_root": str(dest),
        "last_trade_print_count": catalog.observations.get("last_trade_print_count"),
        "tradable_yes_bid_count": catalog.observations.get("tradable_yes_bid_count"),
        "phase20_status": plan.status.value,
        "phase20_basis": plan.observation_basis,
        "mlb_crosswalk": str(mlb_xwalk),
        "nba_crosswalk": str(nba_xwalk),
        "orderbook_partition": False,
        "missing_last_trade_vs_candle": missing_vs_candle,
        "last_trade_months_present": last_months,
        "identity_rule_version": IDENTITY_RULE_VERSION,
        "golden_554_1661_rewritten": False,
    }


def phase20_question() -> ResearchQuestion:
    return PHASE20_QUESTION
