"""MLB dated universes stay clipped. 2025 last-trade is not a 2026 window.

Does not rewrite First Touch / last-trade / Base TE / settlement semantics.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from roller.admin import load_dataset
from roller.config import RollerConfig
from roller.research_query.availability import baseball_warehouse_ready
from roller.research_query.compiler import compile_draft
from roller.research_query.execute import (
    _game_date_token,
    _in_date_window,
    _ticker_game_date,
    execute_question,
)
from roller.research_query.hashing import normalize_state_filters, te_scope_funnel_label
from roller.research_query.season_dates import (
    MIN_FULL_SEASON_DAYS,
    bounds_for_season,
    collapse_full_season_dates,
)
from tests.test_mlb_generic_query_is_tennis_import import EXACT_MLB_DRAFT

WINDOW_FROM = "2026-04-01"
WINDOW_TO = "2026-09-08"


def _bar(*, ticker: str, gid: str, day: str, last: int) -> dict:
    ts = f"{day}T23:00:00Z"
    return {
        "available_at": ts,
        "candle_timestamp": ts,
        "last_close_e4": last,
        "ticker": ticker,
        "internal_game_id": gid,
        "team_side": "away",
        "is_valid": "1",
    }


def _pbp(gid: str, day: str) -> list[dict]:
    return [
        {
            "event_number": 1,
            "event_timestamp": f"{day}T22:59:00Z",
            "inning": 4,
            "half": "top",
            "outs": 0,
            "balls": 0,
            "strikes": 0,
            "runner_on_1": "0",
            "runner_on_2": "0",
            "runner_on_3": "0",
            "batting_team": "away",
            "home_score": 0,
            "away_score": 1,
        }
    ]


def test_ticker_and_gid_game_dates():
    assert _ticker_game_date("KXMLBGAME-25APR16ATHCWS-ATH") == "2025-04-16"
    assert _ticker_game_date("KXMLBGAME-26JUN18NYYBOS-NYY") == "2026-06-18"
    assert _game_date_token({"internal_game_id": "MLB_20250416_ATH_CWS_1"}) == "2025-04-16"
    assert _game_date_token({"ticker": "KXMLBGAME-25APR16ATHCWS-ATH"}) == "2025-04-16"


def test_game_day_outside_window_not_rescued_by_later_timestamp():
    rec = {
        "internal_game_id": "MLB_20250416_ATH_CWS_1",
        "ticker": "KXMLBGAME-25APR16ATHCWS-ATH",
        "available_at": "2026-09-11T15:02:15Z",
        "ingested_at": "2026-09-11T15:02:15Z",
    }
    assert _in_date_window(rec, WINDOW_FROM, WINDOW_TO) is False
    rec_ok = {
        "internal_game_id": "MLB_20260618_NYY_BOS_1",
        "ticker": "KXMLBGAME-26JUN18NYYBOS-NYY",
        "available_at": "2026-06-18T23:00:00Z",
    }
    assert _in_date_window(rec_ok, WINDOW_FROM, WINDOW_TO) is True


def test_exact_draft_keeps_custom_date_window():
    compiled = compile_draft(EXACT_MLB_DRAFT)
    u = compiled.question.universe
    assert u.date_from == WINDOW_FROM
    assert u.date_to == WINDOW_TO


def test_june_stub_does_not_unbind_mlb():
    assert collapse_full_season_dates(
        ("MLB",),
        ("2025-26",),
        "2026-06-18",
        "2026-06-30",
    ) == ("2026-06-18", "2026-06-30")


def test_nba_full_season_still_collapses():
    assert collapse_full_season_dates(
        ("NBA",),
        ("2025-26",),
        "2025-10-10",
        "2026-06-13",
    ) == (None, None)


def test_mlb_full_warehouse_bounds_may_collapse():
    lo, hi = bounds_for_season("MLB", "2025-26")
    assert lo == "2025-03-18"
    assert hi == "2026-09-04"
    assert (datetime.fromisoformat(hi) - datetime.fromisoformat(lo)).days >= MIN_FULL_SEASON_DAYS
    assert collapse_full_season_dates(("MLB",), ("2025-26",), lo, hi) == (None, None)


def test_custom_apr_sep_window_never_collapses():
    assert collapse_full_season_dates(
        ("MLB",),
        ("2025-26",),
        WINDOW_FROM,
        WINDOW_TO,
    ) == (WINDOW_FROM, WINDOW_TO)


def test_te_scope_label_uses_exact_lead_not_abs_none():
    requested = normalize_state_filters({"scoreSide": "leading", "exactDiffs": [1]})
    assert requested is not None
    assert requested.get("exact_diffs") == [1]
    assert requested.get("abs_diff") is None
    label = te_scope_funnel_label(requested)
    assert "leading" in label
    assert "exact 1" in label
    assert "None" not in label


def test_injected_2025_game_excluded_from_2026_window():
    out = execute_question(
        EXACT_MLB_DRAFT,
        ticker_payloads={
            "KXMLBGAME-25APR16ATHCWS-ATH": [
                _bar(
                    ticker="KXMLBGAME-25APR16ATHCWS-ATH",
                    gid="MLB_20250416_ATH_CWS_1",
                    day="2025-04-16",
                    last=7400,
                ),
                _bar(
                    ticker="KXMLBGAME-25APR16ATHCWS-ATH",
                    gid="MLB_20250416_ATH_CWS_1",
                    day="2025-04-16",
                    last=7500,
                ),
            ],
            "KXMLBGAME-26JUN18NYYBOS-NYY": [
                _bar(
                    ticker="KXMLBGAME-26JUN18NYYBOS-NYY",
                    gid="MLB_20260618_NYY_BOS_1",
                    day="2026-06-18",
                    last=7400,
                ),
                _bar(
                    ticker="KXMLBGAME-26JUN18NYYBOS-NYY",
                    gid="MLB_20260618_NYY_BOS_1",
                    day="2026-06-18",
                    last=7500,
                ),
            ],
        },
        pbp_by_game={
            "MLB_20250416_ATH_CWS_1": _pbp("MLB_20250416_ATH_CWS_1", "2025-04-16"),
            "MLB_20260618_NYY_BOS_1": _pbp("MLB_20260618_NYY_BOS_1", "2026-06-18"),
        },
        markets_by_ticker={
            "KXMLBGAME-25APR16ATHCWS-ATH": {
                "result": "yes",
                "internal_game_id": "MLB_20250416_ATH_CWS_1",
            },
            "KXMLBGAME-26JUN18NYYBOS-NYY": {
                "result": "yes",
                "internal_game_id": "MLB_20260618_NYY_BOS_1",
            },
        },
    )
    assert out["execution_status"] == "COMPLETE"
    trades = out["population"]["trades"]
    tickers = {t["ticker"] for t in trades}
    assert "KXMLBGAME-25APR16ATHCWS-ATH" not in tickers
    assert tickers == {"KXMLBGAME-26JUN18NYYBOS-NYY"}
    assert out["summary"]["population_n"] == 1
    te_scope = out["identity"]["te_scope"]
    assert te_scope["requested"]["exact_diffs"] == [1]
    funnel_labels = []
    for step in out.get("population", {}).get("funnel") or []:
        label = step.get("label") if isinstance(step, dict) else getattr(step, "label", "")
        funnel_labels.append(str(label))
    assert any("exact 1" in label for label in funnel_labels)


def test_warehouse_month_prune_excludes_2025_last_trade():
    cfg = RollerConfig()
    if not baseball_warehouse_ready(cfg):
        pytest.skip("MLB canonical warehouse not ingested yet")
    framed = load_dataset(
        cfg,
        "MLB",
        "2025-2026",
        "kalshi_last_trade",
        date_from=WINDOW_FROM,
        date_to=WINDOW_TO,
    )
    assert not framed.empty
    tickers = framed["ticker"].astype(str)
    assert not tickers.str.contains(r"KXMLBGAME-25", regex=True).any()
    months = sorted({str(ts)[:7] for ts in framed["candle_timestamp"]})
    assert all(m >= "2026-03" for m in months)


