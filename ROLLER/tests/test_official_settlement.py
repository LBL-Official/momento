"""Official W overlay. Does not invent settlement from path or box score."""

from __future__ import annotations

from roller.research_query.models import TerminalOutcome
from roller.research_query.official_settlement import (
    _complement,
    _from_flag,
    merge_official_settlement,
    needs_official_settlement,
)
from tests.test_research_query_engine import _q, _series, _snap_quarter
from roller.research_query.compiler import compile_draft
from roller.research_query.execute import _settled_yes, evaluate_ticker
from roller.research_query.models import TouchOrdinal


def test_needs_overlay_only_when_terminal_selected():
    both = _q(TouchOrdinal.FIRST_TOUCH, 8000, "Q3", terminal=TerminalOutcome.BOTH)
    assert needs_official_settlement(both) is False
    draft = {
        "universe": {
            "sports": ["basketball"],
            "leagues": ["NBA"],
            "markets": ["kalshi"],
            "marketData": ["candles"],
        },
        "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 80, "period": "Q3"}],
        "exitConditions": [
            {"id": "h-win", "kind": "terminal", "family": "hold_expiration_win", "outcome": "win"},
        ],
    }
    q = compile_draft(draft).question
    assert q.win_hold is True
    assert needs_official_settlement(q) is True


def test_settled_yes_reads_official_w_fields():
    assert _settled_yes({"expiration_result_yes": True}) is True
    assert _settled_yes({"W": False}) is False
    assert _settled_yes({"result": "yes"}) is True
    assert _settled_yes({}) is None
    assert _settled_yes({"home_win": True, "final_winner": "BOS"}) is None


def test_complement_inverts_binary_event_side():
    overlay = {
        "KXNBAGAME-25OCT22NOPMEM-NOP": {"result": "no", "source": "candidates:nba"},
    }
    rec = _complement("KXNBAGAME-25OCT22NOPMEM-MEM", overlay)
    assert rec is not None
    assert rec["result"] == "yes"
    assert rec["source"].startswith("official_complement:")


def test_prefixed_union_ticker_resolves_official_w(monkeypatch):
    from roller.research_query import official_settlement as osmod

    monkeypatch.setattr(
        osmod,
        "load_official_settlement",
        lambda: {"KXNBAGAME-25OCT22NOPMEM-NOP": {"result": "no", "source": "candidates:nba"}},
    )
    osmod._CACHE = {
        "KXNBAGAME-25OCT22NOPMEM-NOP": {"result": "no", "source": "candidates:nba"},
    }
    out, status = merge_official_settlement(
        {},
        tickers=["NBA:KXNBAGAME-25OCT22NOPMEM-MEM"],
    )
    assert out["NBA:KXNBAGAME-25OCT22NOPMEM-MEM"]["result"] == "yes"
    assert status["n_complement"] == 1
    assert status["overlay_applied"] is True
    assert status["terminal_source"] == "official_first80_expiration_result_yes"
    osmod._CACHE = None


def test_merge_keeps_canonical_result():
    markets = {"T-A": {"result": "no"}}
    out, status = merge_official_settlement(markets, tickers=["T-A"])
    assert out["T-A"]["result"] == "no"
    assert status["n_kept_canonical"] == 1
    assert status["n_direct"] == 0
    assert status["overlay_applied"] is False
    assert status["terminal_source"] == "kalshi_markets.result"
    assert status["canonical_kalshi_markets"] == "USED"


def test_mlb_canonical_is_not_labeled_first80():
    ticker = "KXMLBGAME-26JUN18NYYBOS-NYY"
    out, status = merge_official_settlement(
        {ticker: {"result": "yes", "internal_game_id": "MLB_20260618_NYY_BOS_1"}},
        tickers=[ticker, "KXMLBGAME-26JUN19MISS-MISS"],
    )
    assert out[ticker]["result"] == "yes"
    assert "KXMLBGAME-26JUN19MISS-MISS" not in out
    assert status["n_kept_canonical"] == 1
    assert status["n_direct"] == 0
    assert status["n_complement"] == 0
    assert status["overlay_applied"] is False
    assert status["terminal_source"] == "kalshi_markets.result"
    assert "first80" not in status["terminal_source"]


def test_from_flag_ignores_box_score_strings():
    assert _from_flag("BOS", "x") is None
    assert _from_flag("home", "x") is None


def test_hold_win_uses_official_w_not_path():
    from roller.research_query import execute as ex

    q = compile_draft(
        {
            "universe": {
                "sports": ["basketball"],
                "leagues": ["NBA"],
                "markets": ["kalshi"],
                "marketData": ["candles"],
            },
            "entryConditions": [
                {"id": "e1", "family": "first_touch", "priceCents": 80, "period": "Q3"}
            ],
            "exitConditions": [
                {"id": "p-loss", "kind": "path", "family": "reach", "priceCents": 35, "outcome": "loss"},
                {"id": "h-win", "kind": "terminal", "family": "hold_expiration_win", "outcome": "win"},
            ],
        }
    ).question
    candles = _series([7000, 8000, 8200], ticker="T-HOLD")
    row, _ = evaluate_ticker(
        candles,
        q,
        market={"expiration_result_yes": True},
        snap_fn=_snap_quarter("Q3"),
    )
    assert row is not None
    assert row["terminal_yes"] is True
    assert row["exit_outcome"] == "WIN_EXIT"
    assert row["win_exit"] is True
    missing, _ = evaluate_ticker(
        candles,
        q,
        market=None,
        snap_fn=_snap_quarter("Q3"),
    )
    assert missing is not None
    assert missing["exit_outcome"] is None
    assert missing["terminal_yes"] is None
    assert ex._settled_yes({"home_win": 1}) is None
