"""MLB warehouse is ROLLER-native. Last trade ≠ yes bid. Candle path ≠ fill.

Uses the real 2025-2026 canonical slice when present. Date-windowed execute
must not require a full-season last-trade load.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from roller.admin import load_dataset
from roller.config import RollerConfig
from roller.io_csv import partition_months
from roller.mlb.ingest import CANDLE_COLUMNS, LAST_TRADE_COLUMNS, collect_landing_last_prints
from roller.mlb.leakage import audit_snap
from roller.research.quality import quality
from roller.research_query.availability import baseball_warehouse_ready, data_gaps
from roller.research_query.compiler import compile_draft
from roller.research_query.execute import execute_compiled
from roller.research_query.market_path import candles_quality_ready
from roller.research_query.models import BASIS_LAST_TRADE, BASIS_TRADABLE, ResearchStatus

REPO = Path("/Users/user/Desktop/Momento")
DAY = "2026-06-18"


def _ready(cfg: RollerConfig) -> bool:
    return baseball_warehouse_ready(cfg)


@pytest.fixture(scope="module")
def cfg() -> RollerConfig:
    return RollerConfig()


def test_partition_months_pads_adjacent_only():
    months = partition_months(DAY, DAY)
    assert months == {"2026-05", "2026-06", "2026-07"}
    assert partition_months(None, None) is None


def test_warehouse_is_roller_canonical(cfg: RollerConfig):
    if not _ready(cfg):
        pytest.skip("MLB canonical warehouse not ingested yet")
    games = Path(cfg.dataset_path("MLB", "2025-2026", "games"))
    markets = Path(cfg.dataset_path("MLB", "2025-2026", "kalshi_markets"))
    last = Path(cfg.dataset_path("MLB", "2025-2026", "kalshi_last_trade"))
    pbp = Path(cfg.dataset_path("MLB", "2025-2026", "pbp"))
    candles = Path(cfg.dataset_path("MLB", "2025-2026", "kalshi_candles"))
    assert games.is_file() and markets.is_file()
    assert last.is_dir() and any(last.glob("month=*.csv"))
    assert pbp.is_dir() and any(pbp.glob("month=*.csv"))
    assert candles.is_dir()
    manifest = Path(cfg.dataset_path("MLB", "2025-2026", "pbp")).parent / "dataset_version.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["sport"] == "MLB"
    assert "LAST TRADE" in " ".join(data.get("notes") or [])
    last_cols = set(pd.read_csv(next(last.glob("month=2026-06.csv")), nrows=0).columns)
    assert last_cols == set(LAST_TRADE_COLUMNS)
    assert "yes_bid_close" not in last_cols
    candle_file = next(candles.glob("month=*.csv"), None)
    if candle_file is not None:
        candle_cols = set(pd.read_csv(candle_file, nrows=0).columns)
        assert candle_cols == set(CANDLE_COLUMNS)
        assert "last_close_e4" not in candle_cols


def test_date_window_does_not_load_full_season(cfg: RollerConfig):
    if not _ready(cfg):
        pytest.skip("MLB canonical warehouse not ingested yet")
    from roller.admin import load_dataset

    june = load_dataset(cfg, "MLB", "2025-2026", "kalshi_last_trade", date_from=DAY, date_to=DAY)
    assert not june.empty
    months = sorted({str(ts)[:7] for ts in june["candle_timestamp"]})
    assert set(months) <= {"2026-05", "2026-06", "2026-07"}
    assert "2026-06" in set(months)
    assert len(june) < 2_000_000


def test_landing_sidecar_recomputes_warehouse_minute(cfg: RollerConfig):
    if not _ready(cfg):
        pytest.skip("MLB canonical warehouse not ingested yet")
    landing = (
        REPO
        / "Backtesting Suite/Foundation/Ingest/landing/kalshi_historical_trades"
        / f"date={DAY}"
    )
    files = sorted(landing.glob("ticker=*.trades.json")) if landing.is_dir() else []
    if not files:
        pytest.skip(f"no landing trades for {DAY}")
    rows, n = collect_landing_last_prints(
        REPO,
        dates={DAY},
        ingested_at="t",
        pipeline_version="t",
    )
    assert n >= 1
    assert rows
    by_key = {(r["ticker"], r["candle_timestamp"]): r for r in rows}
    warehouse = pd.read_csv(cfg.dataset_path("MLB", "2025-2026", "kalshi_last_trade") / "month=2026-06.csv")
    hits = 0
    for (ticker, ts), rec in by_key.items():
        match = warehouse[(warehouse["ticker"] == ticker) & (warehouse["candle_timestamp"] == ts)]
        if match.empty:
            continue
        hits += 1
        assert str(match.iloc[0]["last_close_e4"]) == rec["last_close_e4"]
        assert str(match.iloc[0]["market_data_type"]) == "LAST_TRADE_PRINT"
        if hits >= 25:
            break
    assert hits >= 1


def test_last_trade_is_not_yes_bid_on_overlap(cfg: RollerConfig):
    if not _ready(cfg):
        pytest.skip("MLB canonical warehouse not ingested yet")
    last_path = cfg.dataset_path("MLB", "2025-2026", "kalshi_last_trade") / "month=2026-06.csv"
    candle_path = cfg.dataset_path("MLB", "2025-2026", "kalshi_candles") / "month=2026-06.csv"
    if not last_path.is_file() or not candle_path.is_file():
        pytest.skip("June last-trade or candle partition missing")
    last = pd.read_csv(last_path, usecols=["ticker", "candle_timestamp", "last_close_e4"])
    candles = pd.read_csv(candle_path, usecols=["ticker", "candle_timestamp", "yes_bid_close"])
    merged = last.merge(candles, on=["ticker", "candle_timestamp"], how="inner")
    if merged.empty:
        pytest.skip("no overlapping June ticker+minute")
    differed = merged[merged["last_close_e4"].astype(str) != merged["yes_bid_close"].astype(str)]
    assert len(differed) >= 1


def test_quality_still_rejects_empty_volume_and_crossed():
    assert quality(8000, 8100, 0, False) is False
    assert quality(8000, 8100, 4, False) is True
    assert quality(8200, 8100, 4, False) is False
    assert quality(8000, 9200, 4, False) is False
    assert quality(8000, 8100, 0, True) is True


def test_l2_is_not_a_warehouse_path(cfg: RollerConfig):
    compiled = compile_draft(
        {
            "universe": {
                "sports": ["baseball"],
                "leagues": ["MLB"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["l2"],
            },
            "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 80}],
            "exitConditions": [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 90}],
        },
        cfg=cfg,
    )
    assert compiled.status is ResearchStatus.DATA_REQUIRED
    blob = " ".join(compiled.reasons).lower()
    assert "warehouse" in blob or "l2" in blob or "market data" in blob


def test_june18_last_trade_backtest(cfg: RollerConfig):
    if not _ready(cfg):
        pytest.skip("MLB canonical warehouse not ingested yet")
    compiled = compile_draft(
        {
            "universe": {
                "sports": ["baseball"],
                "leagues": ["MLB"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["last_trade"],
                "dateFrom": DAY,
                "dateTo": DAY,
            },
            "entryConditions": [{"id": "e1", "family": "cross", "priceCents": 80, "direction": "up"}],
            "exitConditions": [
                {"id": "p1", "kind": "path", "family": "reach", "priceCents": 90, "outcome": "win"},
                {"id": "hold", "kind": "terminal", "family": "hold_expiration_win", "outcome": "win"},
            ],
        },
        cfg=cfg,
    )
    assert compiled.status in {ResearchStatus.READY, ResearchStatus.READY_WITH_LIMITATIONS}
    assert compiled.question.basis() == BASIS_LAST_TRADE
    out = execute_compiled(compiled, cfg=cfg)
    assert out["execution_status"] == "COMPLETE"
    assert out["observation_basis"] == BASIS_LAST_TRADE
    assert out["mlb"]["funnel"]["games"] >= 1
    n = out["summary"]["population_n"]
    assert n is not None and n >= 1
    assert "LAST-TRADE PRINT OBSERVED" in (out["summary"]["population_description"] or "")
    caveats = " ".join(out.get("caveats") or [])
    assert "LAST TRADE ≠ YES BID" in caveats
    trades = out["population"]["trades"]
    assert trades
    first = trades[0]
    entry_ts = datetime.fromisoformat(str(first["entry_ts"]).replace("Z", "+00:00"))
    gid = first.get("internal_game_id") or first.get("game_id")
    pbp = load_dataset(cfg, "MLB", "2025-2026", "pbp", date_from=DAY, date_to=DAY)
    if gid and not pbp.empty:
        events = pbp[pbp["internal_game_id"] == gid].to_dict("records")
        if events:
            audit = audit_snap(events, entry_ts)
            assert audit["ok"]
            if not audit["exclude"] and audit.get("snap"):
                feat = datetime.fromisoformat(str(audit["snap"]["event_timestamp"]).replace("Z", "+00:00"))
                assert feat <= entry_ts
    markets = pd.read_csv(cfg.dataset_path("MLB", "2025-2026", "kalshi_markets"))
    ticker = first.get("ticker")
    if ticker and ticker in set(markets["ticker"].astype(str)):
        result = str(markets.loc[markets["ticker"].astype(str) == ticker, "result"].iloc[0]).lower()
        assert result in {"yes", "no", ""}


def test_june18_candle_backtest_uses_frozen_quality(cfg: RollerConfig):
    if not _ready(cfg):
        pytest.skip("MLB canonical warehouse not ingested yet")
    if not candles_quality_ready(cfg, "MLB", "2025-2026"):
        compiled = compile_draft(
            {
                "universe": {
                    "sports": ["baseball"],
                    "leagues": ["MLB"],
                    "seasons": ["2025-26"],
                    "markets": ["kalshi"],
                    "marketData": ["candles"],
                    "dateFrom": DAY,
                    "dateTo": DAY,
                },
                "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 80}],
                "exitConditions": [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 90}],
            },
            cfg=cfg,
        )
        assert compiled.status is ResearchStatus.DATA_REQUIRED
        return
    compiled = compile_draft(
        {
            "universe": {
                "sports": ["baseball"],
                "leagues": ["MLB"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["candles"],
                "dateFrom": DAY,
                "dateTo": DAY,
            },
            "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 80}],
            "exitConditions": [
                {"id": "p1", "kind": "path", "family": "reach", "priceCents": 90, "outcome": "win"},
                {"id": "hold", "kind": "terminal", "family": "hold_expiration_win", "outcome": "win"},
            ],
        },
        cfg=cfg,
    )
    assert compiled.status in {ResearchStatus.READY, ResearchStatus.READY_WITH_LIMITATIONS}
    assert compiled.question.basis() == BASIS_TRADABLE
    assert not data_gaps(compiled.question, cfg=cfg) or compiled.status is ResearchStatus.READY_WITH_LIMITATIONS
    out = execute_compiled(compiled, cfg=cfg)
    assert out["execution_status"] in {"COMPLETE", "DATA_REQUIRED"}
    if out["execution_status"] == "COMPLETE":
        assert out["observation_basis"] == BASIS_TRADABLE
        assert "CANDLE" in " ".join(out.get("caveats") or []).upper() or out["summary"]["population_n"] is not None


def test_missing_minutes_are_absent_not_forward_filled(cfg: RollerConfig):
    if not _ready(cfg):
        pytest.skip("MLB canonical warehouse not ingested yet")
    path = cfg.dataset_path("MLB", "2025-2026", "kalshi_last_trade") / "month=2026-06.csv"
    if not path.is_file():
        pytest.skip("June last-trade partition missing")
    frame = pd.read_csv(path, usecols=["ticker", "candle_timestamp"])
    ticker = frame["ticker"].value_counts().index[0]
    ts = sorted(frame.loc[frame["ticker"] == ticker, "candle_timestamp"].astype(str))
    assert ts
    stamps = [datetime.fromisoformat(x.replace("Z", "+00:00")) for x in ts]
    gaps = [
        (b - a).total_seconds()
        for a, b in zip(stamps, stamps[1:])
        if (b - a).total_seconds() > 60
    ]
    assert gaps, "expected at least one missing minute on a real tape"


def test_first80_still_has_no_mlb_adapter():
    import roller.research.first80 as first80

    text = Path(first80.__file__).read_text(encoding="utf-8")
    assert "KXMLBGAME" not in text
    assert "yes_batting" not in text
