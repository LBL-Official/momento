"""Integrity + leakage + ingest column contract."""

from datetime import datetime, timezone

from roller.mlb.ingest import GAMES_COLUMNS, MARKET_COLUMNS
from roller.mlb.last_print import LAST_TRADE_COLUMNS, aggregate_last_prints
from roller.mlb.leakage import audit_population
from roller.mlb.pbp import PBP_COLUMNS
from roller.mlb.validate import validate_warehouse


def test_ingest_column_contracts():
    assert "kalshi_market_yes_home" in GAMES_COLUMNS
    assert "last_close_e4" in LAST_TRADE_COLUMNS
    assert "yes_bid_close" not in LAST_TRADE_COLUMNS
    assert "inning" in PBP_COLUMNS
    assert "batting_team" in PBP_COLUMNS
    assert "result" in MARKET_COLUMNS


def test_integrity_catches_bad_outs_and_duplicates():
    games = [{"internal_game_id": "G1"}]
    pbp = [
        {
            "internal_game_id": "G1",
            "event_number": "1",
            "inning": "7",
            "half": "top",
            "outs": "3",
            "balls": "0",
            "strikes": "0",
            "batting_team": "away",
            "home_score": "1",
            "away_score": "0",
            "event_timestamp": "2026-06-18T23:00:00Z",
        },
        {
            "internal_game_id": "G1",
            "event_number": "1",
            "inning": "7",
            "half": "top",
            "outs": "1",
            "balls": "0",
            "strikes": "0",
            "batting_team": "away",
            "home_score": "1",
            "away_score": "0",
            "event_timestamp": "2026-06-18T23:01:00Z",
        },
    ]
    rep = validate_warehouse(games=games, pbp=pbp, markets=[{"ticker": "A", "internal_game_id": "G1"}])
    assert not rep["ok"]
    assert rep["pbp"]["issue_count"] >= 1


def test_leakage_excludes_future_pbp():
    events = [
        {
            "event_number": 1,
            "event_timestamp": "2026-06-18T23:10:00Z",
            "inning": 7,
            "half": "top",
            "outs": 1,
            "balls": 0,
            "strikes": 0,
            "runner_on_1": "0",
            "runner_on_2": "0",
            "runner_on_3": "0",
            "batting_team": "away",
            "home_score": 1,
            "away_score": 1,
        },
        {
            "event_number": 2,
            "event_timestamp": "2026-06-18T23:40:00Z",
            "inning": 9,
            "half": "bottom",
            "outs": 2,
            "balls": 3,
            "strikes": 2,
            "runner_on_1": "1",
            "runner_on_2": "1",
            "runner_on_3": "1",
            "batting_team": "home",
            "home_score": 8,
            "away_score": 1,
        },
    ]
    out = audit_population(
        [
            {
                "events": events,
                "entry_ts": datetime(2026, 6, 18, 23, 12, tzinfo=timezone.utc),
                "team_side": "away",
                "forbidden": {"inning": 9, "home_score": 8, "runners": "loaded"},
            }
        ]
    )
    assert out["ok"]
    rows = aggregate_last_prints(
        [
            {"ticker": "T", "exchange_timestamp": "2026-06-18T23:00:00Z", "yes_price_cents": 80},
            {"ticker": "T", "exchange_timestamp": "2026-06-18T23:02:00Z", "yes_price_cents": 81},
        ],
        ingested_at="t",
        pipeline_version="t",
    )
    assert "2026-06-18T23:01:00Z" not in {r["candle_timestamp"] for r in rows}


def test_warehouse_integrity_and_no_invented_yes_bid():
    from pathlib import Path

    import pandas as pd

    from roller.config import RollerConfig
    from roller.research_query.availability import baseball_warehouse_ready

    cfg = RollerConfig()
    if not baseball_warehouse_ready(cfg):
        return
    root = Path(cfg.dataset_path("MLB", "2025-2026", "pbp"))
    games = pd.read_csv(cfg.dataset_path("MLB", "2025-2026", "games")).to_dict("records")
    markets = pd.read_csv(cfg.dataset_path("MLB", "2025-2026", "kalshi_markets")).to_dict("records")
    pbp = pd.concat([pd.read_csv(p) for p in sorted(root.glob("*.csv"))], ignore_index=True).to_dict(
        "records"
    )
    rep = validate_warehouse(games=games, pbp=pbp, markets=markets)
    assert rep["pbp"]["ok"], rep["pbp"]["issues"][:5]
    last_dir = Path(cfg.dataset_path("MLB", "2025-2026", "kalshi_last_trade"))
    last = pd.concat([pd.read_csv(p) for p in sorted(last_dir.glob("*.csv"))], ignore_index=True)
    assert "yes_bid_close" not in last.columns
    assert last["last_close_e4"].notna().all()
