"""Phase 17 warehouse ingest. Fixture trees only. Never write the live warehouse."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from roller.config import RollerConfig
from roller.io_csv import write_csv
from roller.warehouse.auto_ingest import (
    IngestStatus,
    discover_nba_sources,
    run_nba_warehouse_ingest,
    source_fingerprint,
)
from roller.warehouse.coverage import get_catalog
from roller.warehouse.identity import IDENTITY_ARTIFACT_COLUMNS
from roller.warehouse.layout import warehouse_root
from roller.warehouse.research_compiler import compile_research
from roller.research_query.models import (
    EntryCondition,
    EntryOp,
    ResearchQuestion,
    TerminalOutcome,
    TouchOrdinal,
    Universe,
)

SRC = Path(__file__).resolve().parents[1]
LIVE_WAREHOUSE = SRC / "data" / "nba" / "2025_2026" / "derived" / "warehouse"

GID = "NBA_20251010_BOS_TOR"
HOME = "KXNBAGAME-25OCT10BOSTOR-TOR"
AWAY = "KXNBAGAME-25OCT10BOSTOR-BOS"
EVENT = "KXNBAGAME-25OCT10BOSTOR"
SRC_ID = "0012500044"


def _copy_root(tmp_path: Path) -> Path:
    root = tmp_path / "ROLLER"
    data = tmp_path / "Data"
    shutil.copytree(SRC / "config", root / "config")
    shutil.copy(SRC / "roller.json", root / "roller.json")
    (root / "meta").mkdir()
    (root / "config" / "sources.json").write_text(
        json.dumps({"warehouse_root": str(data), "fetch_clis": {}, "pbp_ingest": {}}) + "\n"
    )
    return root


def _identity_row(**kwargs) -> dict[str, str]:
    row = {
        "internal_game_id": GID,
        "sport": "NBA",
        "season": "2025-2026",
        "game_date": "2025-10-10",
        "home_team_id": "TOR",
        "away_team_id": "BOS",
        "home_team_name": "Toronto",
        "away_team_name": "Boston",
        "source_game_id": SRC_ID,
        "warehouse_game_id": "wh-1",
        "event_ticker": EVENT,
        "kalshi_market_yes_home": HOME,
        "kalshi_market_yes_away": AWAY,
        "mapping_status": "MAPPED",
        "mapping_confidence": "HIGH",
        "created_at": "2026-09-13T00:00:00Z",
        "updated_at": "2026-09-13T00:00:00Z",
    }
    row.update(kwargs)
    return row


def _game_row(**kwargs) -> dict[str, str]:
    row = {
        "internal_game_id": GID,
        "sport": "NBA",
        "season": "2025-2026",
        "league": "NBA",
        "game_date": "2025-10-10",
        "home_team_id": "TOR",
        "away_team_id": "BOS",
        "home_team_name": "Toronto",
        "away_team_name": "Boston",
        "source_game_id": SRC_ID,
        "warehouse_game_id": "wh-1",
        "event_ticker": EVENT,
        "kalshi_market_yes_home": HOME,
        "kalshi_market_yes_away": AWAY,
    }
    row.update(kwargs)
    return row


def _candle(ticker: str, ts: str, close: str) -> dict[str, str]:
    return {
        "internal_game_id": GID,
        "ticker": ticker,
        "available_at": ts,
        "event_timestamp": ts,
        "candle_timestamp": ts,
        "ingested_at": "2026-09-13T00:00:00Z",
        "yes_bid_open": close,
        "yes_bid_high": close,
        "yes_bid_low": close,
        "yes_bid_close": close,
        "yes_ask_open": "7000",
        "yes_ask_high": "7000",
        "yes_ask_low": "7000",
        "yes_ask_close": "7000",
        "volume": "0",
        "source_dataset": "warehouse_candles_1m",
    }


def _pbp(n: str, ts: str, period: str = "1") -> dict[str, str]:
    return {
        "internal_game_id": GID,
        "source_game_id": SRC_ID,
        "event_number": n,
        "event_timestamp": ts,
        "time_actual": ts,
        "available_at": ts,
        "period": period,
        "clock": "PT12M00.00S",
        "home_score": "0",
        "away_score": "0",
        "event_type": "period",
        "source_dataset": "pbp",
    }


def _suite_row(ticker: str, result: str, value: int) -> dict:
    return {
        "ticker": ticker,
        "market_id": ticker,
        "result": result,
        "settlement_value_e4": value,
        "settlement_time": "2025-10-10T23:58:58Z",
        "close_time": "2025-10-10T23:50:00Z",
        "expiration_time": "2025-10-11T00:00:00Z",
        "source": "kalshi_rest",
        "event_id": EVENT,
    }


def _write_fixture(
    root: Path,
    *,
    identity_rows: list[dict] | None = None,
    games: list[dict] | None = None,
    candles: list[dict] | None = None,
    pbp: list[dict] | None = None,
    suite: list[dict] | None = None,
    markets: list[dict] | None = None,
    write_candles: bool = True,
    write_pbp: bool = True,
    write_identity: bool = True,
) -> Path:
    cfg_probe = RollerConfig(root)
    games_path = cfg_probe.dataset_path("NBA", "2025-2026", "games")
    candles_dir = cfg_probe.dataset_path("NBA", "2025-2026", "kalshi_candles")
    pbp_dir = cfg_probe.dataset_path("NBA", "2025-2026", "pbp")
    markets_path = cfg_probe.dataset_path("NBA", "2025-2026", "kalshi_markets")
    games_path.parent.mkdir(parents=True, exist_ok=True)
    candles_dir.mkdir(parents=True, exist_ok=True)
    pbp_dir.mkdir(parents=True, exist_ok=True)
    if games is None:
        write_csv(games_path, pd.DataFrame([_game_row()]))
    elif games:
        write_csv(games_path, pd.DataFrame(games))
    if write_identity:
        write_csv(
            root / "meta" / "game_identity.csv",
            pd.DataFrame([_identity_row()] if identity_rows is None else identity_rows),
            IDENTITY_ARTIFACT_COLUMNS,
        )
    if write_candles:
        write_csv(
            candles_dir / "month=2025-10.csv",
            pd.DataFrame(
                [
                    _candle(AWAY, "2025-10-10T08:18:00Z", "4600"),
                    _candle(AWAY, "2025-10-10T08:19:00Z", "6300"),
                ]
                if candles is None
                else candles
            ),
        )
    if write_pbp:
        write_csv(
            pbp_dir / "month=2025-10.csv",
            pd.DataFrame(
                [_pbp("1", "2025-10-10T23:12:27Z"), _pbp("2", "2025-10-10T23:13:00Z")] if pbp is None else pbp
            ),
        )
    write_csv(
        markets_path,
        pd.DataFrame(
            markets
            or [
                {"ticker": AWAY, "event_ticker": EVENT, "internal_game_id": GID, "result": "yes"},
                {"ticker": HOME, "event_ticker": EVENT, "internal_game_id": GID, "result": "no"},
            ]
        ),
    )
    suite_path = (
        Path(json.loads((root / "config" / "sources.json").read_text())["warehouse_root"])
        / "NBA"
        / "2025-2026"
        / "warehouse"
        / "normalized"
        / "nba"
        / "markets"
        / "markets.parquet"
    )
    suite_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            _suite_row(AWAY, "yes", 10000),
            _suite_row(HOME, "no", 0),
        ]
        if suite is None
        else suite
    ).to_parquet(suite_path, index=False)
    return root


def _assert_not_live(result) -> None:
    published = Path(result.published_root).resolve()
    assert published != LIVE_WAREHOUSE.resolve()
    assert LIVE_WAREHOUSE.resolve() not in published.parents
    assert published != LIVE_WAREHOUSE.resolve()


def test_discover_existing_and_missing(tmp_path: Path):
    root = _write_fixture(_copy_root(tmp_path))
    cfg = RollerConfig(root)
    sources = discover_nba_sources(cfg)
    kinds = {s.kind for s in sources}
    assert "canonical_games" in kinds
    assert "identity" in kinds
    assert "suite_markets" in kinds
    assert any(s.kind == "candles_month" and s.present for s in sources)
    assert any(s.kind == "pbp_month" and s.present for s in sources)
    assert all(s.sha256 for s in sources if s.present)
    empty = _copy_root(tmp_path / "empty")
    missing = discover_nba_sources(RollerConfig(empty))
    assert any(s.kind == "canonical_games" and not s.present for s in missing)


def test_idempotent_unchanged_source(tmp_path: Path):
    cfg = RollerConfig(_write_fixture(_copy_root(tmp_path)))
    first = run_nba_warehouse_ingest(cfg)
    assert first.status is IngestStatus.PUBLISHED
    _assert_not_live(first)
    fps = dict(first.output_fingerprints)
    second = run_nba_warehouse_ingest(cfg)
    assert second.status is IngestStatus.UNCHANGED
    assert second.source_fingerprint == first.source_fingerprint
    assert second.output_fingerprints == fps
    games = pd.read_parquet(warehouse_root(cfg) / "games" / "games.parquet")
    assert list(games["internal_game_id"]) == [GID]
    assert len(games) == 1


def test_new_game_and_existing_game(tmp_path: Path):
    root = _write_fixture(_copy_root(tmp_path))
    cfg = RollerConfig(root)
    first = run_nba_warehouse_ingest(cfg)
    assert first.status is IngestStatus.PUBLISHED
    extra = _identity_row(
        internal_game_id="NBA_20251011_NYK_BOS",
        game_date="2025-10-11",
        home_team_id="BOS",
        away_team_id="NYK",
        source_game_id="0012500099",
        event_ticker="KXNBAGAME-25OCT11NYKBOS",
        kalshi_market_yes_home="KXNBAGAME-25OCT11NYKBOS-BOS",
        kalshi_market_yes_away="KXNBAGAME-25OCT11NYKBOS-NYK",
    )
    ident = pd.read_csv(root / "meta" / "game_identity.csv", dtype=str).fillna("")
    write_csv(root / "meta" / "game_identity.csv", pd.concat([ident, pd.DataFrame([extra])], ignore_index=True), IDENTITY_ARTIFACT_COLUMNS)
    games = pd.read_csv(cfg.dataset_path("NBA", "2025-2026", "games"), dtype=str).fillna("")
    write_csv(
        cfg.dataset_path("NBA", "2025-2026", "games"),
        pd.concat([games, pd.DataFrame([_game_row(
            internal_game_id=extra["internal_game_id"],
            game_date=extra["game_date"],
            home_team_id="BOS",
            away_team_id="NYK",
            source_game_id=extra["source_game_id"],
            event_ticker=extra["event_ticker"],
            kalshi_market_yes_home=extra["kalshi_market_yes_home"],
            kalshi_market_yes_away=extra["kalshi_market_yes_away"],
        )])], ignore_index=True),
    )
    second = run_nba_warehouse_ingest(cfg)
    assert second.status is IngestStatus.PUBLISHED
    out = pd.read_parquet(warehouse_root(cfg) / "games" / "games.parquet")
    assert set(out["internal_game_id"]) == {GID, extra["internal_game_id"]}
    third = run_nba_warehouse_ingest(cfg)
    assert third.status is IngestStatus.UNCHANGED


def test_new_and_existing_market_and_observations(tmp_path: Path):
    cfg = RollerConfig(_write_fixture(_copy_root(tmp_path)))
    first = run_nba_warehouse_ingest(cfg)
    assert first.status is IngestStatus.PUBLISHED
    obs = pd.read_parquet(warehouse_root(cfg) / "observations" / "basis=tradable_yes_bid" / "month=2025-10.parquet")
    assert len(obs) == 2
    assert set(obs["ticker"]) == {AWAY}
    candles = cfg.dataset_path("NBA", "2025-2026", "kalshi_candles") / "month=2025-10.csv"
    frame = pd.read_csv(candles, dtype=str).fillna("")
    extra = pd.DataFrame([_candle(HOME, "2025-10-10T08:18:00Z", "5400")])
    write_csv(candles, pd.concat([frame, extra], ignore_index=True))
    second = run_nba_warehouse_ingest(cfg)
    assert second.status is IngestStatus.PUBLISHED
    obs2 = pd.read_parquet(warehouse_root(cfg) / "observations" / "basis=tradable_yes_bid" / "month=2025-10.parquet")
    assert len(obs2) == 3
    assert {HOME, AWAY} <= set(obs2["ticker"])


def test_missing_observations_and_new_pbp_and_settlement(tmp_path: Path):
    root = _write_fixture(_copy_root(tmp_path), write_candles=False, write_pbp=False, suite=[])
    cfg = RollerConfig(root)
    first = run_nba_warehouse_ingest(cfg)
    assert first.status is IngestStatus.PUBLISHED
    obs_dir = warehouse_root(cfg) / "observations" / "basis=tradable_yes_bid"
    assert list(obs_dir.glob("month=*.parquet")) == []
    pbp_dir = cfg.dataset_path("NBA", "2025-2026", "pbp")
    write_csv(pbp_dir / "month=2025-10.csv", pd.DataFrame([_pbp("1", "2025-10-10T23:12:27Z")]))
    suite_path = Path(cfg.warehouse_root) / "NBA" / "2025-2026" / "warehouse" / "normalized" / "nba" / "markets" / "markets.parquet"
    pd.DataFrame([_suite_row(AWAY, "yes", 10000), _suite_row(HOME, "no", 0)]).to_parquet(suite_path, index=False)
    second = run_nba_warehouse_ingest(cfg)
    assert second.status is IngestStatus.PUBLISHED
    pbp = pd.read_parquet(warehouse_root(cfg) / "pbp" / "month=2025-10.parquet")
    assert len(pbp) == 1
    settle = pd.read_parquet(warehouse_root(cfg) / "settlements" / "settlements.parquet")
    assert set(settle["settlement_status"]) >= {"YES", "NO"}


def test_duplicate_protection(tmp_path: Path):
    ident = [_identity_row(), _identity_row()]
    cfg = RollerConfig(_write_fixture(_copy_root(tmp_path), identity_rows=ident, games=[_game_row(), _game_row()]))
    result = run_nba_warehouse_ingest(cfg)
    assert result.status is IngestStatus.FAILED
    assert "duplicate" in result.reason.lower()
    assert not (warehouse_root(cfg) / "manifest.json").is_file()


def test_malformed_missing_ambiguous_failure(tmp_path: Path):
    cfg = RollerConfig(_write_fixture(_copy_root(tmp_path), write_identity=False, games=[]))
    missing = run_nba_warehouse_ingest(cfg)
    assert missing.status is IngestStatus.FAILED
    assert any(tok in missing.reason.lower() for tok in ("missing", "empty", "no columns"))

    root = _write_fixture(
        _copy_root(tmp_path / "price"),
        candles=[_candle(AWAY, "2025-10-10T08:18:00Z", "not-a-price")],
    )
    bad_price = run_nba_warehouse_ingest(RollerConfig(root))
    assert bad_price.status is IngestStatus.FAILED
    assert "price" in bad_price.reason.lower() or "malformed" in bad_price.reason.lower()

    root = _write_fixture(
        _copy_root(tmp_path / "ts"),
        candles=[_candle(AWAY, "", "4600")],
    )
    bad_ts = run_nba_warehouse_ingest(RollerConfig(root))
    assert bad_ts.status is IngestStatus.FAILED
    assert "timestamp" in bad_ts.reason.lower()

    amb = [
        _identity_row(),
        _identity_row(
            internal_game_id="NBA_20251010_ORL_PHI",
            home_team_id="PHI",
            away_team_id="ORL",
            source_game_id="0012500070",
            event_ticker="KXNBAGAME-25OCT10ORLPHI",
            kalshi_market_yes_home=HOME,
            kalshi_market_yes_away=AWAY,
        ),
    ]
    root = _write_fixture(_copy_root(tmp_path / "amb"), identity_rows=amb)
    amb_result = run_nba_warehouse_ingest(RollerConfig(root))
    assert amb_result.status is IngestStatus.FAILED
    assert "ambiguous" in amb_result.reason.lower()

    root = _write_fixture(
        _copy_root(tmp_path / "settle"),
        suite=[_suite_row(AWAY, "yes", 10000), _suite_row(AWAY, "no", 0)],
    )
    conflict = run_nba_warehouse_ingest(RollerConfig(root))
    assert conflict.status is IngestStatus.FAILED


def test_interrupted_publish_leaves_published_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg = RollerConfig(_write_fixture(_copy_root(tmp_path)))
    first = run_nba_warehouse_ingest(cfg)
    assert first.status is IngestStatus.PUBLISHED
    published = warehouse_root(cfg)
    before = (published / "manifest.json").read_text(encoding="utf-8")

    def boom(*_a, **_k):
        raise RuntimeError("interrupted publish")

    monkeypatch.setattr("roller.warehouse.auto_ingest.write_nba_warehouse", boom)
    candles = cfg.dataset_path("NBA", "2025-2026", "kalshi_candles") / "month=2025-10.csv"
    frame = pd.read_csv(candles, dtype=str).fillna("")
    write_csv(candles, pd.concat([frame, pd.DataFrame([_candle(AWAY, "2025-10-10T08:20:00Z", "6400")])], ignore_index=True))
    failed = run_nba_warehouse_ingest(cfg)
    assert failed.status is IngestStatus.FAILED
    assert "interrupted" in failed.reason.lower()
    assert (published / "manifest.json").read_text(encoding="utf-8") == before
    assert not published.with_name(published.name + ".staging").exists()


def test_provenance_and_capability_trio(tmp_path: Path):
    cfg = RollerConfig(_write_fixture(_copy_root(tmp_path)))
    result = run_nba_warehouse_ingest(cfg)
    assert result.status is IngestStatus.PUBLISHED
    record = json.loads((warehouse_root(cfg) / "ingest_run.json").read_text(encoding="utf-8"))
    assert record["source_hashes"]
    assert record["source_fingerprint"] == result.source_fingerprint
    assert record["transform_versions"]["identity"]
    assert record["output_fingerprints"]
    assert record["pbp_pit_aligned_to_candles"] is False
    assert record["acquire_time"]
    man = json.loads((warehouse_root(cfg) / "manifest.json").read_text(encoding="utf-8"))
    assert man["tick_data_available"] is False
    assert man["orderbook_data_available"] is False
    assert man["candle_pit_available"] is True
    catalog = get_catalog(cfg)
    q = ResearchQuestion(
        universe=Universe(
            sports=("NBA",),
            leagues=("NBA",),
            seasons=("2025-2026",),
            markets=("kalshi",),
            market_data=("candles",),
            date_from="2025-10-10",
            date_to="2025-10-10",
        ),
        entry_conditions=(
            EntryCondition(id="e1", ordinal=TouchOrdinal.FIRST_TOUCH, price_e4=6300, operation=EntryOp.CROSS),
        ),
        path_conditions=(),
        terminal=TerminalOutcome.BOTH,
    )
    ready = compile_research(q, cfg)
    assert ready.status.value == "READY"
    tick = ResearchQuestion(
        universe=Universe(
            sports=("NBA",),
            leagues=("NBA",),
            seasons=("2025-2026",),
            markets=("kalshi",),
            market_data=("tick",),
            date_from="2025-10-10",
            date_to="2025-10-10",
        ),
        entry_conditions=q.entry_conditions,
        path_conditions=(),
        terminal=TerminalOutcome.BOTH,
    )
    data_required = compile_research(tick, cfg)
    assert data_required.status.value == "DATA_REQUIRED"
    pit = ResearchQuestion(
        universe=Universe(
            sports=("NBA",),
            leagues=("NBA",),
            seasons=("2025-2026",),
            markets=("kalshi",),
            market_data=("candles",),
            game_data=("pbp",),
            date_from="2025-10-10",
            date_to="2025-10-10",
        ),
        entry_conditions=q.entry_conditions,
        path_conditions=(),
        requested_dimensions=("PBP_MARKET_PIT_ALIGNMENT",),
        terminal=TerminalOutcome.BOTH,
    )
    op_required = compile_research(pit, cfg)
    assert op_required.status.value == "OPERATION_REQUIRED"
    assert catalog.public_coverage()["orderbook"]["availability"] == "SOURCE_UNAVAILABLE"


def test_source_fingerprint_changes_when_file_changes(tmp_path: Path):
    root = _write_fixture(_copy_root(tmp_path))
    cfg = RollerConfig(root)
    a = source_fingerprint(discover_nba_sources(cfg))
    games = cfg.dataset_path("NBA", "2025-2026", "games")
    games.write_text(games.read_text() + "\n", encoding="utf-8")
    b = source_fingerprint(discover_nba_sources(cfg))
    assert a != b
