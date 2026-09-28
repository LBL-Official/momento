"""Phase 3 NBA GameMarketLink. No execute, compiler, or ticker-body guessing."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from roller.config import RollerConfig
from roller.warehouse.entities import LinkStatus, Market
from roller.warehouse.layout_v0 import LINK_METHOD_IDENTITY_TICKER, crosswalk_path
from roller.warehouse.market_link import (
    audit_link_frame,
    build_nba_market_links,
    classify_market_ticker,
    identity_ticker_index,
    linked_game_id,
    market_from_link_row,
    write_nba_market_links,
)

ROLLER_ROOT = Path(__file__).resolve().parents[1]
LIVE_IDENTITY = ROLLER_ROOT / "meta" / "game_identity.csv"
LIVE_MARKETS = ROLLER_ROOT / "data" / "nba" / "2025_2026" / "canonical" / "kalshi_markets.csv"


def _identity_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "internal_game_id": "NBA_20251010_BOS_TOR",
                "sport": "NBA",
                "season": "2025-2026",
                "event_ticker": "KXNBAGAME-25OCT10BOSTOR",
                "kalshi_market_yes_home": "KXNBAGAME-25OCT10BOSTOR-TOR",
                "kalshi_market_yes_away": "KXNBAGAME-25OCT10BOSTOR-BOS",
                "mapping_status": "MAPPED",
            },
            {
                "internal_game_id": "NBA_20260108_MIA_CHI",
                "sport": "NBA",
                "season": "2025-2026",
                "event_ticker": "KXNBAGAME-26JAN08MIACHI",
                "kalshi_market_yes_home": "KXNBAGAME-26JAN08MIACHI-CHI",
                "kalshi_market_yes_away": "KXNBAGAME-26JAN08MIACHI-MIA",
                "mapping_status": "UNMAPPED",
            },
        ]
    )


def test_one_game_many_markets_is_valid():
    index = identity_ticker_index(_identity_rows())
    home = classify_market_ticker(ticker="KXNBAGAME-25OCT10BOSTOR-TOR", index=index)
    away = classify_market_ticker(ticker="KXNBAGAME-25OCT10BOSTOR-BOS", index=index)
    assert home.status is LinkStatus.LINKED
    assert away.status is LinkStatus.LINKED
    assert home.internal_game_id == away.internal_game_id == "NBA_20251010_BOS_TOR"
    assert home.link_method == LINK_METHOD_IDENTITY_TICKER
    assert home.ticker != home.internal_game_id


def test_unmapped_identity_ticker_is_still_linked():
    index = identity_ticker_index(_identity_rows())
    link = classify_market_ticker(ticker="KXNBAGAME-26JAN08MIACHI-CHI", index=index)
    assert link.status is LinkStatus.LINKED
    assert link.internal_game_id == "NBA_20260108_MIA_CHI"
    assert "UNMAPPED" in link.source_evidence


def test_one_market_one_canonical_game():
    index = identity_ticker_index(_identity_rows())
    assert set(index.unique) == {
        "KXNBAGAME-25OCT10BOSTOR-TOR",
        "KXNBAGAME-25OCT10BOSTOR-BOS",
        "KXNBAGAME-26JAN08MIACHI-CHI",
        "KXNBAGAME-26JAN08MIACHI-MIA",
    }
    assert index.ambiguous == {}


def test_conflicting_source_tickers_are_ambiguous():
    rows = _identity_rows()
    extra = rows.iloc[[0]].copy()
    extra.loc[:, "internal_game_id"] = "NBA_20251010_NYK_BKN"
    index = identity_ticker_index(pd.concat([rows, extra], ignore_index=True))
    link = classify_market_ticker(ticker="KXNBAGAME-25OCT10BOSTOR-TOR", index=index)
    assert link.status is LinkStatus.AMBIGUOUS
    assert link.internal_game_id == ""


def test_missing_game_and_missing_market():
    index = identity_ticker_index(_identity_rows())
    missing_market = classify_market_ticker(ticker="KXNBAGAME-UNKNOWN-AAA", index=index)
    assert missing_market.status is LinkStatus.UNLINKED
    assert missing_market.internal_game_id == ""
    missing_ticker = classify_market_ticker(ticker="", index=index)
    assert missing_ticker.status is LinkStatus.INVALID


def test_malformed_and_ticker_is_not_internal_game_id():
    index = identity_ticker_index(_identity_rows())
    assert classify_market_ticker(ticker="NBA_20251010_BOS_TOR", index=index).status is LinkStatus.UNLINKED
    market = market_from_link_row(
        {
            "ticker": "KXNBAGAME-25OCT10BOSTOR-BOS",
            "internal_game_id": "NBA_20251010_BOS_TOR",
            "event_ticker": "KXNBAGAME-25OCT10BOSTOR",
        }
    )
    assert isinstance(market, Market)
    assert market.ticker == market.market_id
    assert market.ticker != market.internal_game_id
    with pytest.raises(ValueError, match="market_id"):
        Market(ticker="KX-A", market_id="KX-B")


def test_suite_only_ticker_is_unlinked():
    cfg = RollerConfig(ROLLER_ROOT)
    built = build_nba_market_links(
        cfg,
        identity=_identity_rows(),
        suite=pd.DataFrame([{"ticker": "KXNBAGAME-ORPHAN-AAA", "market_title": "orphan"}]),
        canonical=pd.DataFrame(columns=["ticker"]),
    )
    orphan = built.links.loc[built.links["ticker"] == "KXNBAGAME-ORPHAN-AAA"].iloc[0]
    assert orphan["link_status"] == LinkStatus.UNLINKED.value
    assert orphan["internal_game_id"] == ""


def test_duplicate_links_and_one_ticker_two_games_detected():
    good = pd.DataFrame(
        [
            {
                "ticker": "T1",
                "internal_game_id": "NBA_20251010_BOS_TOR",
                "link_status": "LINKED",
            },
            {
                "ticker": "T2",
                "internal_game_id": "NBA_20251010_BOS_TOR",
                "link_status": "LINKED",
            },
        ]
    )
    assert audit_link_frame(good)["one_ticker_many_games"] == 0
    dups = pd.concat([good, good.iloc[[0]]], ignore_index=True)
    assert audit_link_frame(dups)["duplicate_tickers"] == 1
    conflict = pd.DataFrame(
        [
            {"ticker": "T1", "internal_game_id": "NBA_A", "link_status": "LINKED"},
            {"ticker": "T1", "internal_game_id": "NBA_B", "link_status": "LINKED"},
        ]
    )
    assert audit_link_frame(conflict)["one_ticker_many_games"] == 1


def test_idempotent_rebuild(tmp_path: Path, roller_env: Path):
    cfg = RollerConfig(roller_env)
    identity = _identity_rows()
    first = build_nba_market_links(
        cfg, identity=identity, suite=pd.DataFrame(), canonical=pd.DataFrame()
    )
    second = build_nba_market_links(
        cfg, identity=identity, suite=pd.DataFrame(), canonical=pd.DataFrame()
    )
    assert first.links.equals(second.links)
    write_nba_market_links(cfg, first)
    write_nba_market_links(cfg, second)
    a = pd.read_parquet(crosswalk_path(cfg))
    write_nba_market_links(cfg, first)
    b = pd.read_parquet(crosswalk_path(cfg))
    assert a.equals(b)
    assert linked_game_id(a, "KXNBAGAME-25OCT10BOSTOR-BOS") == "NBA_20251010_BOS_TOR"
    assert linked_game_id(a, "KXNBAGAME-ORPHAN-AAA") == ""


@pytest.mark.skipif(not LIVE_IDENTITY.is_file(), reason="identity catalog absent")
@pytest.mark.skipif(not LIVE_MARKETS.is_file(), reason="NBA kalshi_markets absent")
def test_live_nba_crosswalk_invariants():
    cfg = RollerConfig(ROLLER_ROOT)
    built = build_nba_market_links(cfg)
    audit = audit_link_frame(built.links)
    assert audit["duplicate_tickers"] == 0
    assert audit["one_ticker_many_games"] == 0
    assert audit["ambiguous"] == 0
    assert audit["invalid"] == 0
    assert built.games_with_linked_markets == 1362
    assert audit["linked"] >= 2724
    mapped = pd.read_csv(LIVE_MARKETS, dtype=str, keep_default_na=False)
    for ticker, gid in zip(mapped["ticker"], mapped["internal_game_id"]):
        assert linked_game_id(built.links, ticker) == gid
    unmapped = built.links[built.links["source_evidence"].str.contains("UNMAPPED", na=False)]
    assert len(unmapped) == 20
    assert (unmapped["link_status"] == LinkStatus.LINKED.value).all()
