"""Landing trades/candles: copy venue fields only. Never invent yes_bid."""

from pathlib import Path

from roller.mlb.ingest import (
    collect_landing_candles,
    collect_landing_settlement,
    collect_landing_trades,
    collect_suite_candles_1m,
    merge_crosswalk,
    merge_market_metadata,
    official_from_pbp_envelope,
    official_market_result,
)
from roller.mlb.last_print import dollars_to_cents, dollars_to_e4, trade_yes_cents


def test_dollars_to_cents_is_exact_only():
    assert dollars_to_cents("0.5300") == 53
    assert dollars_to_cents("0.80") == 80
    assert dollars_to_cents("1") == 100
    assert dollars_to_cents("0.8010") is None
    assert dollars_to_cents("") is None
    assert dollars_to_e4("0.5300") == 5300


def test_trade_yes_cents_prefers_cents_then_dollars():
    assert trade_yes_cents({"yes_price_cents": 80}) == 80
    assert trade_yes_cents({"yes_price_dollars": "0.8000"}) == 80
    assert trade_yes_cents({"yes_price_dollars": "0.8010"}) is None


def test_collect_landing_trades_and_candles(tmp_path, monkeypatch):
    repo = tmp_path
    trades_dir = repo / "Backtesting Suite/Foundation/Ingest/landing/kalshi_historical_trades/date=2026-06-18"
    candles_dir = repo / "Backtesting Suite/Foundation/Ingest/landing/kalshi_historical_candles/date=2026-06-18"
    trades_dir.mkdir(parents=True)
    candles_dir.mkdir(parents=True)
    ticker = "KXMLBGAME-26JUN18NYYBOS-NYY"
    (trades_dir / f"ticker={ticker}.trades.json").write_text(
        """{"trades_status":"OBSERVED_HISTORICAL","ticker":"%s","trades":[
        {"ticker":"%s","created_time":"2026-06-18T23:01:10Z","yes_price_dollars":"0.8000"},
        {"ticker":"%s","created_time":"2026-06-18T23:01:40Z","yes_price_dollars":"0.8100"}
        ]}"""
        % (ticker, ticker, ticker),
        encoding="utf-8",
    )
    (candles_dir / f"ticker={ticker}.candles.json").write_text(
        """{"candles_status":"OBSERVED_HISTORICAL","ticker":"%s","candlesticks":[
        {"end_period_ts":1781798460,"volume":"12.00","yes_bid":{"open":"0.7900","high":"0.8100","low":"0.7900","close":"0.8000"},"yes_ask":{"open":"0.8000","high":"0.8200","low":"0.8000","close":"0.8100"}},
        {"end_period_ts":1781798520,"volume":"0.00","yes_bid":{"open":null,"high":null,"low":null,"close":null}}
        ]}"""
        % ticker,
        encoding="utf-8",
    )
    monkeypatch.chdir(repo)
    from roller.mlb import ingest as ing

    trades = ing.collect_landing_trades(repo)
    assert len(trades) == 2
    assert trade_yes_cents(trades[0]) == 80
    candles = ing.collect_landing_candles(
        repo,
        ticker_meta={ticker: {"internal_game_id": "MLB_1", "team_side": "away"}},
        ingested_at="2026-09-11T00:00:00Z",
        pipeline_version="t",
    )
    assert len(candles) == 1
    assert candles[0]["yes_bid_close"] == "8000"
    assert candles[0]["yes_bid_open"] == "7900"
    assert candles[0]["volume"] == "12"
    assert candles[0]["internal_game_id"] == "MLB_1"


def test_merge_crosswalk_keeps_mapped_and_adds_landing_only():
    merged = merge_crosswalk(
        [{"game_pk": "1", "event_ticker": "EV-1", "official_date": "2026-06-18", "mapping": "MAPPED"}],
        [{"game_pk": "2", "event_ticker": "EV-2", "official_date": "2026-06-19", "mapping": "MAPPED"}],
        [{"game_pk": "3", "official_date": "2026-06-20", "event_ticker": "", "mapping": "UNMATCHED", "pbp_path": "/x"}],
    )
    pks = {r["game_pk"]: r for r in merged}
    assert pks["1"]["event_ticker"] == "EV-1"
    assert pks["2"]["event_ticker"] == "EV-2"
    assert pks["3"]["mapping"] == "UNMATCHED"
    assert pks["3"]["event_ticker"] == ""


def test_collect_landing_skips_unavailable_and_null_close(tmp_path, monkeypatch):
    repo = tmp_path
    candles_dir = repo / "Backtesting Suite/Foundation/Ingest/landing/kalshi_historical_candles/date=2026-06-18"
    candles_dir.mkdir(parents=True)
    bad = "KXMLBGAME-26JUN18NYYBOS-BOS"
    (candles_dir / f"ticker={bad}.candles.json").write_text(
        """{"candles_status":"UNAVAILABLE","ticker":"%s","candlesticks":[]}""" % bad,
        encoding="utf-8",
    )
    null_close = "KXMLBGAME-26JUN18NYYBOS-NYY"
    (candles_dir / f"ticker={null_close}.candles.json").write_text(
        """{"candles_status":"OBSERVED_HISTORICAL","ticker":"%s","candlesticks":[
        {"end_period_ts":1781798460,"volume":"9.00","yes_bid":{"open":"0.7900","high":"0.7900","low":"0.7900","close":null}}
        ]}"""
        % null_close,
        encoding="utf-8",
    )
    monkeypatch.chdir(repo)
    from roller.mlb import ingest as ing

    rows = ing.collect_landing_candles(
        repo,
        ticker_meta={},
        ingested_at="t",
        pipeline_version="t",
    )
    assert rows == []


def test_landing_volume_is_not_print_count(tmp_path, monkeypatch):
    repo = tmp_path
    candles_dir = repo / "Backtesting Suite/Foundation/Ingest/landing/kalshi_historical_candles/date=2026-06-18"
    candles_dir.mkdir(parents=True)
    ticker = "KXMLBGAME-26JUN18NYYBOS-NYY"
    (candles_dir / f"ticker={ticker}.candles.json").write_text(
        """{"candles_status":"OBSERVED_HISTORICAL","ticker":"%s","candlesticks":[
        {"end_period_ts":1781798460,"volume":"0.00","yes_bid":{"open":"0.7900","high":"0.8000","low":"0.7900","close":"0.8000"},"yes_ask":{"close":"0.8100"}}
        ]}"""
        % ticker,
        encoding="utf-8",
    )
    monkeypatch.chdir(repo)
    from roller.mlb import ingest as ing

    rows = ing.collect_landing_candles(
        repo,
        ticker_meta={ticker: {"internal_game_id": "G", "team_side": "away"}},
        ingested_at="t",
        pipeline_version="t",
    )
    assert len(rows) == 1
    assert rows[0]["volume"] == "0"
    assert rows[0]["yes_bid_close"] == "8000"


def test_collect_suite_candles_1m_requires_yes_bid(tmp_path):
    import pandas as pd

    root = tmp_path / "candles_1m" / "month=2026-08"
    root.mkdir(parents=True)
    ticker = "KXMLBGAME-26AUG07NYYBOS-NYY"
    pd.DataFrame(
        [
            {
                "ticker": ticker,
                "end_time": pd.Timestamp("2026-08-07T23:01:00Z"),
                "yes_bid_open_e4": 7900,
                "yes_bid_high_e4": 8100,
                "yes_bid_low_e4": 7900,
                "yes_bid_close_e4": 8000,
                "yes_ask_open_e4": 8100,
                "yes_ask_high_e4": 8200,
                "yes_ask_low_e4": 8000,
                "yes_ask_close_e4": 8100,
                "volume_hundredths": 12,
            },
            {
                "ticker": ticker,
                "end_time": pd.Timestamp("2026-08-07T23:02:00Z"),
                "yes_bid_open_e4": None,
                "yes_bid_high_e4": None,
                "yes_bid_low_e4": None,
                "yes_bid_close_e4": None,
                "yes_ask_open_e4": 8100,
                "yes_ask_high_e4": 8100,
                "yes_ask_low_e4": 8100,
                "yes_ask_close_e4": 8100,
                "volume_hundredths": 9,
            },
        ]
    ).to_parquet(root / f"{ticker}.parquet", index=False)
    rows = collect_suite_candles_1m(
        tmp_path,
        ticker_meta={ticker: {"internal_game_id": "MLB_1", "team_side": "away"}},
        ingested_at="t",
        pipeline_version="t",
        candles_root=tmp_path / "candles_1m",
    )
    assert len(rows) == 1
    assert rows[0]["yes_bid_close"] == "8000"
    assert rows[0]["yes_ask_close"] == "8100"
    assert rows[0]["volume"] == "12"
    assert rows[0]["source_dataset"] == "warehouse_candles_1m"
    assert rows[0]["internal_game_id"] == "MLB_1"


def test_official_from_pbp_envelope(tmp_path: Path):
    path = tmp_path / "gamePk=776135.envelope.json"
    path.write_text(
        """{"source_game_id":"776135","payload":{"gamePk":776135,"gameData":{
        "game":{"pk":776135},"datetime":{"officialDate":"2026-06-18"},
        "teams":{"home":{"abbreviation":"BOS"},"away":{"abbreviation":"NYY"}}
        }}}""",
        encoding="utf-8",
    )
    row = official_from_pbp_envelope(path)
    assert row is not None
    assert row["game_pk"] == "776135"
    assert row["home_abbreviation"] == "BOS"
    assert row["away_abbreviation"] == "NYY"
    assert row["event_ticker"] == ""


def test_landing_settlement_does_not_overwrite_existing_yes(tmp_path, monkeypatch):
    import pandas as pd

    repo = tmp_path
    dest = repo / "Backtesting Suite/Foundation/Ingest/landing/kalshi_market_settlement/date=2026-06-18"
    dest.mkdir(parents=True)
    (dest / "ticker=KXMLBGAME-26JUN18NYYBOS-NYY.json").write_text(
        """{"ticker":"KXMLBGAME-26JUN18NYYBOS-NYY","event_ticker":"KXMLBGAME-26JUN18NYYBOS",
        "result":"no","settlement_ts":"2026-06-19T01:00:00Z"}""",
        encoding="utf-8",
    )
    (dest / "ticker=KXMLBGAME-26JUN18NYYBOS-BOS.json").write_text(
        """{"ticker":"KXMLBGAME-26JUN18NYYBOS-BOS","event_ticker":"KXMLBGAME-26JUN18NYYBOS",
        "result":"yes","settlement_ts":"2026-06-19T01:00:00Z"}""",
        encoding="utf-8",
    )
    monkeypatch.chdir(repo)
    landing = collect_landing_settlement(repo)
    assert official_market_result("YES") == "yes"
    assert set(landing["ticker"]) == {
        "KXMLBGAME-26JUN18NYYBOS-NYY",
        "KXMLBGAME-26JUN18NYYBOS-BOS",
    }
    canonical = pd.DataFrame(
        [{"ticker": "KXMLBGAME-26JUN18NYYBOS-NYY", "result": "yes", "event_ticker": "KEEP"}]
    )
    merged = merge_market_metadata(canonical, landing)
    by = {r["ticker"]: r for r in merged.to_dict("records")}
    assert by["KXMLBGAME-26JUN18NYYBOS-NYY"]["result"] == "yes"
    assert by["KXMLBGAME-26JUN18NYYBOS-BOS"]["result"] == "yes"
