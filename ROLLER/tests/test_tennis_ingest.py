"""Tennis warehouse ingest: identity join, no invented clocks, no print-as-bid."""

from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path

from roller.config import RollerConfig
from roller.tennis.crosswalk import STATUS_MATCHED, STATUS_UNMATCHED
from roller.tennis.ingest import WINDOW_END, WINDOW_START, ingest_tennis
from roller.tennis.pbp import LICENSE_FIELDS, PBP_BASIS_SEQUENCE_ONLY, MATCH_INDEX_COLUMNS, POINT_COLUMNS

ZVEREV = "dc4002ad-fb32-4f36-b59f-7c7af1927c57"
KHACHANOV = "11111111-2222-3333-4444-555555555555"
MATCH_ID = "20260909-M-US_Open-SF-Alexander_Zverev-Karen_Khachanov"
ITF_ID = "20260909-M-ITF_Davis-RR-Some_Player-Other_Player"


def _write_jsonl_gz(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _matches_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(MATCH_INDEX_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)


def _points_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(POINT_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)


def _match_row(match_id: str, p1: str, p2: str, tournament: str, *, date="20260909") -> dict:
    return {
        "match_id": match_id,
        "Player 1": p1,
        "Player 2": p2,
        "Pl 1 hand": "R",
        "Pl 2 hand": "R",
        "Date": date,
        "Tournament": tournament,
        "Round": "SF",
        "Time": "11:10 AM",
        "Court": "Centre",
        "Surface": "Hard",
        "Umpire": "",
        "Best of": "5",
        "Final TB?": "A",
        "Charted by": "test",
    }


def _point(match_id: str) -> dict:
    return {
        "match_id": match_id,
        "Pt": "1",
        "Set1": "0",
        "Set2": "0",
        "Gm1": "0",
        "Gm2": "0",
        "Pts": "0-0",
        "Gm#": "1",
        "TbSet": "5",
        "Svr": "1",
        "1st": "4*",
        "2nd": "",
        "Notes": "",
        "PtWinner": "1",
    }


def _warehouse(tmp: Path) -> Path:
    wh = tmp / "warehouse"
    event = {
        "event_ticker": "KXATPMATCH-26SEP09ZVEKHA",
        "series_ticker": "KXATPMATCH",
        "title": "Zverev vs Khachanov",
        "sub_title": "Zverev vs Khachanov (Sep 09)",
        "product_metadata": {"competition": "US Open Men Singles", "competition_scope": "Game"},
    }
    future = {
        "event_ticker": "KXATPMATCH-26SEP12FUTURE",
        "series_ticker": "KXATPMATCH",
        "title": "Future vs Player",
        "product_metadata": {"competition": "US Open Men Singles"},
    }
    m1 = {
        "ticker": "KXATPMATCH-26SEP09ZVEKHA-ZVE",
        "event_ticker": "KXATPMATCH-26SEP09ZVEKHA",
        "yes_sub_title": "Alexander Zverev",
        "custom_strike": {"tennis_competitor": ZVEREV},
        "occurrence_datetime": "2026-09-09T17:00:00Z",
        "open_time": "2026-09-08T20:00:00Z",
        "close_time": "2026-09-09T20:00:00Z",
        "expected_expiration_time": "2026-09-09T21:00:00Z",
        "expiration_time": "2026-09-23T15:00:00Z",
        "settlement_ts": "2026-09-09T20:01:00Z",
        "settlement_value_dollars": "1.0000",
        "result": "yes",
        "status": "finalized",
    }
    m2 = {
        **m1,
        "ticker": "KXATPMATCH-26SEP09ZVEKHA-KHA",
        "yes_sub_title": "Karen Khachanov",
        "custom_strike": {"tennis_competitor": KHACHANOV},
        "result": "no",
        "settlement_value_dollars": "0.0000",
    }
    m_scalar = {
        **m1,
        "ticker": "KXATPMATCH-26SEP09ZVEKHA-SCAL",
        "yes_sub_title": "Alexander Zverev",
        "result": "scalar",
        "settlement_value_dollars": "0.4400",
    }
    m_future = {
        "ticker": "KXATPMATCH-26SEP12FUTURE-FUT",
        "event_ticker": "KXATPMATCH-26SEP12FUTURE",
        "yes_sub_title": "Future",
        "custom_strike": {"tennis_competitor": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"},
        "occurrence_datetime": "2026-09-12T17:00:00Z",
        "result": "yes",
    }
    _write_jsonl_gz(wh / "raw/kalshi/atp/events/events.jsonl.gz", [event, future])
    _write_jsonl_gz(
        wh / "raw/kalshi/atp/markets/markets.jsonl.gz",
        [m1, m2, m_scalar, m_future],
    )
    _write_jsonl_gz(wh / "raw/kalshi/wta/events/events.jsonl.gz", [])
    _write_jsonl_gz(wh / "raw/kalshi/wta/markets/markets.jsonl.gz", [])

    candle = {
        "received_at": "2026-09-09T17:01:00Z",
        "source": "historical_rest",
        "endpoint": "candlesticks",
        "ticker": m1["ticker"],
        "payload": {
            "ticker": m1["ticker"],
            "candlesticks": [
                {
                    "end_period_ts": 1788973260,
                    "volume": "2.00",
                    "yes_bid": {"open": "0.7900", "high": "0.8000", "low": "0.7900", "close": "0.8000"},
                    "yes_ask": {"open": "0.8100", "high": "0.8200", "low": "0.8100", "close": "0.8100"},
                    "price": {"open": None, "high": None, "low": None, "close": None},
                }
            ],
        },
    }
    _write_jsonl_gz(
        wh / f"raw/kalshi/atp/candlesticks/ticker={m1['ticker']}/candles.jsonl.gz",
        [candle],
    )
    trade = {
        "ticker": m1["ticker"],
        "created_time": "2026-09-09T17:00:30Z",
        "yes_price_dollars": "0.8000",
        "count_fp": "1.00",
        "trade_id": "t1",
        "taker_outcome_side": "yes",
    }
    _write_jsonl_gz(
        wh / f"raw/kalshi/atp/trades/ticker={m1['ticker']}/page-0001.jsonl.gz",
        [trade],
    )
    jobs = [
        {"ticker": m1["ticker"], "dataset_type": "candles", "status": "COMPLETE"},
        {"ticker": m1["ticker"], "dataset_type": "trades", "status": "COMPLETE"},
        {"ticker": "INCOMPLETE-TICKER", "dataset_type": "candles", "status": "DOWNLOADING"},
    ]
    man = wh / "manifests/atp/atp_ingestion_manifest.json"
    man.parent.mkdir(parents=True, exist_ok=True)
    man.write_text(json.dumps({"jobs": jobs}), encoding="utf-8")
    (wh / "manifests/wta").mkdir(parents=True, exist_ok=True)
    (wh / "manifests/wta/wta_ingestion_manifest.json").write_text(json.dumps({"jobs": []}), encoding="utf-8")

    mcp = wh / "raw/mcp"
    _matches_csv(
        mcp / "charting-m-matches.csv",
        [
            _match_row(MATCH_ID, "Alexander Zverev", "Karen Khachanov", "US Open"),
            _match_row(ITF_ID, "Some Player", "Other Player", "ITF Davis Cup"),
        ],
    )
    _matches_csv(mcp / "charting-w-matches.csv", [])
    _points_csv(
        mcp / "charting-m-points-2020s.csv",
        [_point(MATCH_ID), _point(ITF_ID)],
    )
    _points_csv(mcp / "charting-w-points-2020s.csv", [])
    return wh


def test_ingest_links_kalshi_to_mcp_without_inventing_clocks(tmp_path: Path):
    wh = _warehouse(tmp_path)
    dest = tmp_path / "canonical"
    cfg = RollerConfig()
    manifest = ingest_tennis(cfg=cfg, warehouse=wh, dest=dest)
    assert manifest["counts"]["games"] == 1
    games = (dest / "games.csv").read_text(encoding="utf-8")
    assert "KXATPMATCH-26SEP09ZVEKHA" in games
    assert "KXATPMATCH-26SEP12FUTURE" not in games
    assert "SEQUENCE_ONLY" in games
    assert "11:10 AM" not in games

    markets = list(csv.DictReader((dest / "kalshi_markets.csv").open(encoding="utf-8")))
    by_ticker = {row["ticker"]: row for row in markets}
    assert by_ticker["KXATPMATCH-26SEP09ZVEKHA-ZVE"]["result"] == "yes"
    assert by_ticker["KXATPMATCH-26SEP09ZVEKHA-KHA"]["result"] == "no"
    assert by_ticker["KXATPMATCH-26SEP09ZVEKHA-ZVE"]["team_side"] == "1"
    assert by_ticker["KXATPMATCH-26SEP09ZVEKHA-SCAL"]["team_side"] == "1"
    assert by_ticker["KXATPMATCH-26SEP09ZVEKHA-KHA"]["team_side"] == "2"
    assert by_ticker["KXATPMATCH-26SEP09ZVEKHA-SCAL"]["result"] == ""
    assert by_ticker["KXATPMATCH-26SEP09ZVEKHA-SCAL"]["kalshi_yes_settled"] == ""

    pbp_files = list((dest / "pbp").glob("*.csv"))
    assert pbp_files
    pbp = list(csv.DictReader(pbp_files[0].open(encoding="utf-8")))
    linked = [row for row in pbp if row["internal_game_id"] == "KXATPMATCH-26SEP09ZVEKHA"]
    unmatched = [row for row in pbp if row["source_match_id"] == ITF_ID]
    assert linked
    assert all(row["event_timestamp"] == "" for row in pbp)
    assert all(row["pbp_basis"] == PBP_BASIS_SEQUENCE_ONLY for row in pbp)
    assert all(row["pit_joinable"] == "0" for row in pbp)
    assert unmatched
    assert all(row["internal_game_id"] == "" for row in unmatched)
    assert all(row["crosswalk_status"] == STATUS_UNMATCHED for row in unmatched)

    candles = list(csv.DictReader(next((dest / "kalshi_candles").glob("*.csv")).open(encoding="utf-8")))
    assert candles
    assert candles[0]["yes_bid_close"] == "8000"
    assert candles[0]["internal_game_id"] == "KXATPMATCH-26SEP09ZVEKHA"
    last = list(csv.DictReader(next((dest / "kalshi_last_trade").glob("*.csv")).open(encoding="utf-8")))
    assert last
    assert last[0]["last_close_e4"] == "8000"
    assert "yes_bid_close" not in last[0] or last[0].get("yes_bid_close") in (None, "")

    xw = list(csv.DictReader((dest / "crosswalk.csv").open(encoding="utf-8")))
    statuses = {row["source_match_id"]: row["crosswalk_status"] for row in xw}
    assert statuses[MATCH_ID] == STATUS_MATCHED
    assert statuses[ITF_ID] == STATUS_UNMATCHED
    assert manifest["coverage"]["mcp_matches_in_window"] == 2
    assert manifest["dataset_version"]
    for key, value in LICENSE_FIELDS.items():
        assert manifest["license"][key] == value
    assert WINDOW_START.isoformat() <= "2026-09-09" <= WINDOW_END.isoformat()


def test_compile_uses_warehouse_when_present():
    from roller.research_query.availability import tennis_warehouse_ready
    from roller.research_query.compiler import compile_draft
    from roller.research_query.models import BASIS_TRADABLE, ExecutionPath, ResearchStatus
    from tests.test_tennis_execute import _draft

    compiled = compile_draft(_draft())
    assert compiled.question.basis() == BASIS_TRADABLE
    if tennis_warehouse_ready():
        assert compiled.status == ResearchStatus.READY
        assert compiled.execution_path == ExecutionPath.GENERIC_QUERY
    else:
        assert compiled.status == ResearchStatus.DATA_REQUIRED
        assert compiled.execution_path == ExecutionPath.NONE
