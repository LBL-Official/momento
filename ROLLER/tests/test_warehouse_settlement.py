"""Phase 6 NBA settlement. Official Kalshi result only. No score or price inference."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from roller.config import RollerConfig
from roller.warehouse.entities import SettlementResult
from roller.warehouse.layout_v0 import settlements_parquet_path
from roller.warehouse.settlement import (
    SettlementConflictError,
    assert_not_inferred_settlement_source,
    build_nba_settlements,
    coverage_report,
    project_settlement_frame,
    refuse_price_derived_settlement,
    refuse_score_derived_settlement,
    write_nba_settlements,
)

ROLLER_ROOT = Path(__file__).resolve().parents[1]
LIVE_XWALK = ROLLER_ROOT / "meta" / "game_market_crosswalk.parquet"


def _crosswalk() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": "KX-YES",
                "internal_game_id": "NBA_20251010_BOS_TOR",
                "link_status": "LINKED",
            },
            {
                "ticker": "KX-NO",
                "internal_game_id": "NBA_20251010_BOS_TOR",
                "link_status": "LINKED",
            },
            {
                "ticker": "KX-MISSING",
                "internal_game_id": "NBA_20260108_MIA_CHI",
                "link_status": "LINKED",
            },
        ]
    )


def _suite_row(ticker: str, result: str, value=None, **kwargs) -> dict:
    row = {
        "ticker": ticker,
        "market_id": f"mid-{ticker}",
        "result": result,
        "settlement_value_e4": value,
        "settlement_time": "2025-10-10T23:58:58Z",
        "close_time": "2025-10-10T23:50:00Z",
        "expiration_time": "2025-10-11T00:00:00Z",
        "source": "kalshi_rest",
    }
    row.update(kwargs)
    return row


def test_yes_no_missing_invalid():
    suite = pd.DataFrame(
        [
            _suite_row("KX-YES", "yes", 10000),
            _suite_row("KX-NO", "no", 0),
            _suite_row("KX-SCALAR", "scalar", 5600),
        ]
    )
    xwalk = pd.concat(
        [
            _crosswalk(),
            pd.DataFrame([{"ticker": "KX-SCALAR", "internal_game_id": "NBA_X", "link_status": "LINKED"}]),
        ],
        ignore_index=True,
    )
    out, extras = project_settlement_frame(suite, xwalk, source_path="markets.parquet", source_hash="abc")
    by = {r.ticker: r for r in out.itertuples(index=False)}
    assert by["KX-YES"].settlement_status == SettlementResult.YES.value
    assert by["KX-YES"].settlement_value_e4 == "10000"
    assert by["KX-YES"].internal_game_id == "NBA_20251010_BOS_TOR"
    assert by["KX-YES"].market_id == "KX-YES"
    assert by["KX-YES"].source == "kalshi_rest"
    assert by["KX-YES"].source_result == "yes"
    assert "markets.parquet" in by["KX-YES"].provenance
    assert by["KX-NO"].settlement_status == SettlementResult.NO.value
    assert by["KX-NO"].settlement_value_e4 == "0"
    assert by["KX-MISSING"].settlement_status == SettlementResult.MISSING.value
    assert by["KX-MISSING"].settlement_value_e4 == ""
    assert extras["missing_rows"] == 1
    assert by["KX-SCALAR"].settlement_status == SettlementResult.INVALID.value
    assert by["KX-SCALAR"].source_result == "scalar"
    assert by["KX-SCALAR"].settlement_value_e4 == "5600"


def test_duplicate_same_classification_kept_once():
    suite = pd.DataFrame(
        [
            _suite_row("KX-YES", "yes", 10000),
            _suite_row("KX-YES", "yes", 10000),
        ]
    )
    out, extras = project_settlement_frame(suite, _crosswalk())
    yes = out[out["ticker"] == "KX-YES"]
    assert len(yes) == 1
    assert extras["duplicate_source_rows"] == 1


def test_conflicting_settlement_fails_closed():
    suite = pd.DataFrame(
        [
            _suite_row("KX-YES", "yes", 10000),
            _suite_row("KX-YES", "no", 0),
        ]
    )
    with pytest.raises(SettlementConflictError, match="KX-YES"):
        project_settlement_frame(suite, _crosswalk())


def test_unknown_market_is_unlinked_not_guessed():
    suite = pd.DataFrame([_suite_row("KX-ORPHAN", "yes", 10000)])
    out, extras = project_settlement_frame(suite, _crosswalk())
    orphan = out[out["ticker"] == "KX-ORPHAN"].iloc[0]
    assert orphan["game_link_status"] == "UNLINKED"
    assert orphan["internal_game_id"] == ""
    assert orphan["settlement_status"] == SettlementResult.YES.value
    assert extras["unlinked_rows"] == 1


def test_malformed_blank_ticker_and_bad_value():
    with pytest.raises(ValueError, match="blank ticker"):
        project_settlement_frame(
            pd.DataFrame([_suite_row("", "yes", 10000)]),
            _crosswalk(),
        )
    with pytest.raises(ValueError, match="malformed settlement_value_e4"):
        project_settlement_frame(
            pd.DataFrame([_suite_row("KX-YES", "yes", "not-a-number")]),
            _crosswalk(),
        )


def test_missing_settlement_is_not_no():
    out, _ = project_settlement_frame(pd.DataFrame(), _crosswalk())
    missing = out[out["ticker"] == "KX-MISSING"].iloc[0]
    assert missing["settlement_status"] == SettlementResult.MISSING.value
    assert missing["settlement_status"] != SettlementResult.NO.value
    assert missing["source_result"] == ""


def test_no_score_or_price_derived_settlement():
    with pytest.raises(ValueError, match="score"):
        refuse_score_derived_settlement()
    with pytest.raises(ValueError, match="price"):
        refuse_price_derived_settlement()
    with pytest.raises(ValueError, match="score"):
        assert_not_inferred_settlement_source(["home_win", "final_home_score"])
    with pytest.raises(ValueError, match="price"):
        assert_not_inferred_settlement_source(["yes_bid_close", "volume"])
    # Suite metadata may include last_price_e4; result remains the authority.
    assert_not_inferred_settlement_source(["ticker", "result", "last_price_e4", "yes_bid_e4"])


def test_market_identity_preserved_and_game_via_crosswalk():
    suite = pd.DataFrame([_suite_row("KX-YES", "yes", 10000)])
    out, _ = project_settlement_frame(suite, _crosswalk())
    row = out[out["ticker"] == "KX-YES"].iloc[0]
    assert row["market_id"] == row["ticker"] == "KX-YES"
    assert row["internal_game_id"] == "NBA_20251010_BOS_TOR"
    assert row["internal_game_id"] != row["market_id"]


def test_idempotent_rebuild(tmp_path: Path, roller_env: Path):
    cfg = RollerConfig(roller_env)
    suite = pd.DataFrame(
        [
            _suite_row("KX-YES", "yes", 10000),
            _suite_row("KX-NO", "no", 0),
        ]
    )
    first = build_nba_settlements(cfg, suite=suite, crosswalk=_crosswalk())
    second = build_nba_settlements(cfg, suite=suite, crosswalk=_crosswalk())
    assert first.settlements.equals(second.settlements)
    write_nba_settlements(cfg, first)
    a = pd.read_parquet(settlements_parquet_path(cfg))
    write_nba_settlements(cfg, second)
    b = pd.read_parquet(settlements_parquet_path(cfg))
    assert a.equals(b)
    assert list(a["market_id"]) == sorted(a["market_id"])
    cov = coverage_report(first.settlements, observation_tickers={"KX-YES"}, observation_games={"NBA_20251010_BOS_TOR"})
    assert cov["yes"] == 1
    assert cov["no"] == 1
    assert cov["missing"] == 1
    assert cov["games_market_obs_settlement"] == 1


@pytest.mark.skipif(not LIVE_XWALK.is_file(), reason="NBA crosswalk absent")
def test_live_nba_settlement_invariants():
    cfg = RollerConfig(ROLLER_ROOT)
    built = build_nba_settlements(cfg)
    assert built.duplicate_source_rows == 0
    assert built.status_counts.get("MISSING", 0) == 0
    assert built.settlements["market_id"].is_unique
    assert (built.settlements["market_id"] == built.settlements["ticker"]).all()
    assert built.suite_tickers == 2724
    assert built.crosswalk_tickers == 2724
    assert int(len(built.settlements)) == 2724
    assert built.status_counts[SettlementResult.YES.value] == 1359
    assert built.status_counts[SettlementResult.NO.value] == 1359
    assert built.status_counts[SettlementResult.INVALID.value] == 6
    assert (built.settlements["source"] == "kalshi_rest").all()
    assert not built.settlements["provenance"].eq("").any()
    scalars = built.settlements[built.settlements["settlement_status"] == "INVALID"]
    assert set(scalars["source_result"]) == {"scalar"}
    assert built.settlements["internal_game_id"].ne("").all()
    assert (built.settlements["game_link_status"] == "LINKED").all()
