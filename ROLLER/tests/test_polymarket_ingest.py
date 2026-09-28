"""Polymarket last-trade ingest + identity link. No network. No Kalshi substitution."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from roller.canonical.polymarket_candles import (
    CANDLE_COLUMNS,
    ingest_polymarket_sport,
    points_to_rows,
)
from roller.canonical.polymarket_match import match_events
from roller.ingest.polymarket import identity_slugs
from roller.config import RollerConfig
from roller.identity import MAPPING_MAPPED, MAPPING_UNMAPPED
from roller.maintenance.update import update_sport
from roller.research.quality import quality
from roller.research_query.capabilities import unsupported_operations
from roller.research_query.compiler import compile_draft
from roller.research_query.entry_engine import last_trade_sequence
from roller.research_query.execute import execute_question
from roller.research_query.models import (
    BASIS_LAST_TRADE,
    BASIS_TRADABLE,
    EVENT_DEFINITION,
    EVENT_DEFINITION_LAST_TRADE,
    EntryCondition,
    ExecutionPath,
    PriceField,
    ResearchQuestion,
    ResearchStatus,
    TerminalOutcome,
    TouchOrdinal,
    Universe,
)


def _event(
    *,
    eid="100",
    slug="nba-lal-bos-2025-12-20",
    event_date="2025-12-20",
    start="2025-12-20T19:00:00Z",
    away_abbr="lal",
    home_abbr="bos",
    away_name="Lakers",
    home_name="Celtics",
    tokens=("tok-away", "tok-home"),
    outcomes=None,
):
    outcomes = outcomes or [away_name, home_name]
    return {
        "id": eid,
        "slug": slug,
        "eventDate": event_date,
        "startTime": start,
        "gameId": 1,
        "teams": [
            {"abbreviation": away_abbr, "name": away_name, "alias": away_name, "ordering": "away"},
            {"abbreviation": home_abbr, "name": home_name, "alias": home_name, "ordering": "home"},
        ],
        "markets": [
            {
                "sportsMarketType": "moneyline",
                "outcomes": json.dumps(outcomes),
                "clobTokenIds": json.dumps(list(tokens)),
            }
        ],
    }


def _identity_row(**overrides):
    row = {
        "internal_game_id": "NBA_20251220_LAL_BOS",
        "sport": "NBA",
        "season": "2025-2026",
        "game_date": "2025-12-20",
        "home_team_id": "BOS",
        "away_team_id": "LAL",
        "kalshi_market_yes_home": "KX-BOS",
        "kalshi_market_yes_away": "KX-LAL",
        "scheduled_start": "2025-12-20T19:00:00Z",
        "mapping_status": "MAPPED",
    }
    row.update(overrides)
    return row


def test_identity_slug_uses_away_home_date():
    assert identity_slugs("NBA", "2025-10-10", "BOS", "TOR") == ["nba-bos-tor-2025-10-10"]
    assert "cbb-uconn-mich-2026-04-06" in identity_slugs("NCAAB", "2026-04-06", "CONN", "MICH")


def test_match_unique_date_pair():
    cfg = RollerConfig()
    ident = pd.DataFrame([_identity_row()])
    df = match_events(cfg, "NBA", "2025-2026", [_event()], ident)
    assert len(df) == 1
    rec = df.iloc[0].to_dict()
    assert rec["mapping_status"] == MAPPING_MAPPED
    assert rec["internal_game_id"] == "NBA_20251220_LAL_BOS"
    assert rec["token_yes_home"] == "tok-home"
    assert rec["token_yes_away"] == "tok-away"
    assert rec["kalshi_market_yes_home"] == "KX-BOS"


def test_unknown_team_unmapped():
    cfg = RollerConfig()
    ident = pd.DataFrame([_identity_row()])
    ev = _event(away_abbr="zzz", home_abbr="yyy", away_name="Nope", home_name="AlsoNope")
    rec = match_events(cfg, "NBA", "2025-2026", [ev], ident).iloc[0].to_dict()
    assert rec["mapping_status"] == MAPPING_UNMAPPED
    assert rec["internal_game_id"] == ""


def test_rematch_uses_start_time():
    cfg = RollerConfig()
    ident = pd.DataFrame(
        [
            _identity_row(
                internal_game_id="NBA_20251225_LAL_BOS",
                game_date="2025-12-25",
                scheduled_start="2025-12-25T17:00:00Z",
            ),
            _identity_row(
                internal_game_id="NBA_20251225_LAL_BOS_2",
                game_date="2025-12-25",
                scheduled_start="2025-12-25T21:00:00Z",
            ),
        ]
    )
    ev = _event(event_date="2025-12-25", start="2025-12-25T21:05:00Z", slug="nba-lal-bos-2025-12-25")
    rec = match_events(cfg, "NBA", "2025-2026", [ev], ident).iloc[0].to_dict()
    assert rec["internal_game_id"] == "NBA_20251225_LAL_BOS_2"
    assert rec["mapping_method"] == "eventDate+team_pair+startTime"


def test_match_uses_market_game_start_when_event_start_missing():
    cfg = RollerConfig()
    ident = pd.DataFrame([_identity_row()])
    ev = _event(start=None)
    ev["markets"][0]["gameStartTime"] = "2025-12-20 19:00:00+00"
    rec = match_events(cfg, "NBA", "2025-2026", [ev], ident).iloc[0].to_dict()
    assert rec["mapping_status"] == MAPPING_MAPPED
    assert rec["polymarket_start_time"] == "2025-12-20T19:00:00Z"


def test_last_price_is_not_bid_ask_or_tradable():
    rows = points_to_rows(
        [{"t": 1766261610, "p": 0.55}],
        {
            "internal_game_id": "NBA_20251220_LAL_BOS",
            "token_id": "tok",
            "ticker": "slug-BOS",
            "team_side": "home",
            "kalshi_ticker": "KX-BOS",
        },
        ingested_at="2026-01-01T00:00:00Z",
        pipeline_version="test",
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["last_close_e4"] == "5500"
    assert row["market_data_type"] == "PRICE_HISTORY_LAST"
    assert row["tradable_cross"] == "0"
    assert "yes_bid_close" not in row
    assert not quality(row.get("yes_bid_close"), row.get("yes_ask_close"), row.get("volume"), False)


def test_ingest_writes_linked_warehouse_and_canonical(roller_env: Path):
    cfg = RollerConfig(roller_env)
    update_sport(cfg, "NBA", "2025-2026", include_pbp=False, include_candles=True)
    calls: list[str] = []

    def http_get(url: str):
        calls.append(url)
        if "prices-history" in url:
            return {"history": [{"t": 1766261610, "p": 0.61}, {"t": 1766261670, "p": 0.62}]}
        raise AssertionError(f"unexpected URL {url}")

    ev = _event()
    report = ingest_polymarket_sport(
        cfg,
        "NBA",
        "2025-2026",
        discover=False,
        download=True,
        canonicalize=True,
        http_get=http_get,
        events=[ev],
    )
    assert report["mapped"] == 1
    assert report["candles"] == 4  # 2 points × 2 tokens
    candles = pd.concat(
        [
            pd.read_csv(p, dtype=str, keep_default_na=False)
            for p in (roller_env / "data" / "nba" / "2025_2026" / "canonical" / "polymarket_candles").glob("*.csv")
        ],
        ignore_index=True,
    )
    assert set(candles["internal_game_id"]) == {"NBA_20251220_LAL_BOS"}
    assert (candles["market_data_type"] == "PRICE_HISTORY_LAST").all()
    assert "yes_bid_close" not in candles.columns
    for col in CANDLE_COLUMNS:
        assert col in candles.columns
    markets = pd.read_csv(
        roller_env / "data" / "nba" / "2025_2026" / "canonical" / "polymarket_markets.csv",
        dtype=str,
        keep_default_na=False,
    )
    assert set(markets["internal_game_id"]) == {"NBA_20251220_LAL_BOS"}
    assert set(markets["kalshi_ticker"]) == {
        "KXNBAGAME-25DEC20LALBOS-BOS",
        "KXNBAGAME-25DEC20LALBOS-LAL",
    }
    assert all("prices-history" in u for u in calls)


def test_polymarket_without_dataset_stays_data_required(roller_env: Path, monkeypatch):
    monkeypatch.setenv("ROLLER_ROOT", str(roller_env))
    from roller.research_query import season_mapping

    season_mapping._seasons_block.cache_clear()
    draft = {
        "universe": {
            "sports": ["basketball"],
            "leagues": ["NBA"],
            "seasons": ["2025-26"],
            "markets": ["polymarket"],
            "marketData": ["candles"],
        },
        "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 80, "period": "Q3"}],
        "exitConditions": [{"id": "t", "kind": "terminal", "family": "both"}],
    }
    c = compile_draft(draft, cfg=RollerConfig(roller_env))
    assert c.status is ResearchStatus.DATA_REQUIRED
    assert any("Kalshi" in r for r in c.reasons)


def _pm_draft(**universe_overrides):
    universe = {
        "sports": ["basketball"],
        "leagues": ["NBA"],
        "seasons": ["2025-26"],
        "markets": ["polymarket"],
        "marketData": ["candles"],
    }
    universe.update(universe_overrides)
    return {
        "universe": universe,
        "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 80}],
        "exitConditions": [{"id": "t", "kind": "terminal", "family": "both"}],
    }


def _ingested_env(roller_env: Path, history=None) -> RollerConfig:
    cfg = RollerConfig(roller_env)
    update_sport(cfg, "NBA", "2025-2026", include_pbp=False, include_candles=True)
    hist = history or [{"t": 1766261610, "p": 0.61}, {"t": 1766261670, "p": 0.81}]
    ingest_polymarket_sport(
        cfg,
        "NBA",
        "2025-2026",
        discover=False,
        download=True,
        canonicalize=True,
        http_get=lambda url: {"history": hist},
        events=[_event()],
    )
    return cfg


def test_polymarket_runs_on_last_trade_basis_never_as_tradable_tob(roller_env: Path):
    """Behavioral change: a Polymarket question compiles and runs.

    It was previously blanket-OPERATION_REQUIRED, which made linked data
    unusable. It now runs on an explicit LAST_TRADE_PRINT basis. It still may
    never claim a tradable quote, Kalshi substitution, or a FIRST80 lock.
    """
    cfg = _ingested_env(roller_env)
    c = compile_draft(_pm_draft(), cfg=cfg)
    assert c.status is ResearchStatus.READY
    assert c.execution_path is ExecutionPath.GENERIC_QUERY
    # Never a frozen Kalshi reference.
    assert c.reference_match is None
    assert "polymarket_1m_last_trade" in c.available
    assert "tradable_yes_bid_close_cross" not in c.available
    entry = c.question.entry_conditions[0]
    assert entry.price_field == PriceField.LAST_TRADE_CLOSE.value
    assert entry.event_definition == EVENT_DEFINITION_LAST_TRADE
    assert c.question.basis() == BASIS_LAST_TRADE

    out = execute_question({"draft": _pm_draft()}, cfg=cfg)
    assert out["execution_status"] == "COMPLETE"
    prov = out["provenance"]
    assert prov["price_field"] == "last_close_e4"
    assert prov["price_basis"] == BASIS_LAST_TRADE
    assert prov["market_data"] == "polymarket_1m_last_trade"
    assert prov["market_data_type"] == "PRICE_HISTORY_LAST"
    assert prov["price_rule"] == "last_trade_close_cross"
    assert prov["path"] == "generic_query"
    assert "yes_bid" not in str(prov)
    assert any("LAST TRADE ≠ TRADABLE QUOTE" in c2 for c2 in out["caveats"])
    for row in out["population"]["trades"]:
        assert row["price_basis"] == BASIS_LAST_TRADE


def test_polymarket_reports_no_pnl_or_ev(roller_env: Path):
    cfg = _ingested_env(roller_env)
    out = execute_question({"draft": _pm_draft()}, cfg=cfg)
    assert out["execution_status"] == "COMPLETE"
    names = {m["name"] for m in out["measurements"]}
    # A print is not an executable price, so no money measurement is emitted.
    for banned in (
        "model_a_8040_ev_cents",
        "observed_hyp_ev_cents",
        "max_drawdown_cents",
        "risk_of_ruin",
    ):
        assert banned not in names
    assert "path_rate" in names
    for row in out["population"]["trades"]:
        assert row["hyp_pnl_cents"] is None


def test_polymarket_terminal_comes_from_kalshi_settlement(roller_env: Path):
    cfg = _ingested_env(roller_env)
    out = execute_question({"draft": _pm_draft()}, cfg=cfg)
    assert out["provenance"]["terminal_source"] == "kalshi_settlement"


def test_cross_venue_has_no_joint_basis(roller_env: Path):
    cfg = _ingested_env(roller_env)
    c = compile_draft(_pm_draft(markets=["kalshi", "polymarket"]), cfg=cfg)
    assert c.status is ResearchStatus.OPERATION_REQUIRED
    assert "cross_venue_joint_basis" in c.unavailable
    assert any("not defined" in r for r in c.reasons)
    out = execute_question(
        {"draft": _pm_draft(markets=["kalshi", "polymarket"])}, cfg=cfg
    )
    assert out["execution_status"] == "OPERATION_REQUIRED"
    assert out["summary"]["population_n"] is None


def test_polymarket_period_filter_without_pbp_fails_closed(roller_env: Path):
    cfg = _ingested_env(roller_env)
    draft = _pm_draft()
    draft["entryConditions"][0]["period"] = "Q3"
    c = compile_draft(draft, cfg=cfg)
    assert c.status is ResearchStatus.DATA_REQUIRED
    assert any("PBP" in r for r in c.reasons)


def test_kalshi_basis_is_unchanged_by_polymarket_support(roller_env: Path):
    cfg = _ingested_env(roller_env)
    c = compile_draft(_pm_draft(markets=["kalshi"]), cfg=cfg)
    entry = c.question.entry_conditions[0]
    assert entry.price_field == PriceField.YES_BID_CLOSE.value
    assert entry.event_definition == EVENT_DEFINITION
    assert c.question.basis() == BASIS_TRADABLE
    assert "tradable_yes_bid_close_cross" in c.available


def test_last_trade_bars_have_no_quote_and_no_forward_fill():
    rows = [
        {
            "ticker": "pm",
            "internal_game_id": "g",
            "available_at": "2025-12-20T19:00:00Z",
            "last_close_e4": "6100",
            "is_valid": "1",
        },
        # Minute 19:01 has no print at all and must not be synthesized.
        {
            "ticker": "pm",
            "internal_game_id": "g",
            "available_at": "2025-12-20T19:02:00Z",
            "last_close_e4": "8100",
            "is_valid": "1",
        },
        {
            "ticker": "pm",
            "internal_game_id": "g",
            "available_at": "2025-12-20T19:03:00Z",
            "last_close_e4": "",
            "is_valid": "1",
        },
    ]
    bars, skipped = last_trade_sequence(rows)
    assert [b.bid for b in bars] == [6100, 8100]
    assert skipped == 1
    assert all(b.ask is None for b in bars)
    assert all(b.basis == BASIS_LAST_TRADE for b in bars)
    assert all(not b.tradable for b in bars)


def test_last_trade_field_cannot_carry_a_tradable_definition():
    cond = EntryCondition(
        id="e1",
        ordinal=TouchOrdinal.FIRST_TOUCH,
        price_e4=8000,
        price_field=PriceField.LAST_TRADE_CLOSE.value,
        event_definition=EVENT_DEFINITION,
    )
    q = ResearchQuestion(
        universe=Universe(("basketball",), ("NBA",), ("2025-26",), ("polymarket",), ("candles",)),
        entry_conditions=(cond,),
        path_conditions=(),
        terminal=TerminalOutcome.BOTH,
    )
    reasons = unsupported_operations(q)
    assert any("does not match price field" in r for r in reasons)
