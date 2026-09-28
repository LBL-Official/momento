"""78/67 Drevo and Positman keep a separate N from the 80/40 desks."""

from roller.dre.api import handle_stratum, handle_trade_breakdown
from roller.dre_first78.api import handle_experiments, handle_health, handle_positions
from roller.positman.service import sources as sources_80
from roller.positman_first78.service import sources as sources_78


def test_drevo_78_keeps_the_books_apart():
    health = handle_health()
    austin_n = health["upstream"]["position_stratification"]["n"]
    choosin_n = health["upstream"]["trade_breakdown"]["n"]
    assert austin_n == 569
    assert choosin_n not in (None, 569, 604, 936)
    assert health["upstream"]["position_stratification"]["universe"] == "choosin_nba_2q3q_first78_67"
    assert health["upstream"]["trade_breakdown"]["universe"] == "DERIVED_FOUR_FIRST78"
    assert health["objective"]["calculus"] == "NOT_IMPLEMENTED"


def test_drevo_80_handlers_stay_on_604_and_936():
    stratum = handle_stratum()
    trade = handle_trade_breakdown()
    assert stratum["book_n"] == 604
    assert trade["universe"] == "derived_four_936"
    assert trade["n"] == 936


def test_78_experiment_index_is_not_the_604_book():
    body = handle_experiments()
    assert body["status"] == "UNAVAILABLE"
    assert body["experiments"] == []


def test_78_position_list_is_the_austin_fit():
    body = handle_positions()
    assert body["book_n"] == 569
    assert body["universe"] == "choosin_nba_2q3q_first78_67"
    assert body["n"] == 569
    assert str(body["positions"][0]["trade_id"]).startswith("f78-")


def test_positman_78_plan_matches_the_austin_stamp():
    from roller.positman_first78.service import plan

    body = plan("f78-KXNBAGAME-25OCT10BOSTOR-BOS", record=False)
    assert body["match_status"] == "MATCHED"
    assert body["book"] == "FIRST78_67"
    assert body["identity"]["as_of"] == "2025-10-10T23:51:00Z"
    assert body["plan_status"] == "PLAN_UNRESOLVED"


def test_positman_sources_stay_on_their_own_books():
    old = sources_80()
    new = sources_78()
    assert "roller.ballhog_first78" not in old["note"]
    assert new["adapters"]["ballhog"] == "roller.ballhog_first78.api.handle_intent"
    assert new["adapters"]["tk_ultra"] == "roller.tk_ultra_first78.api.handle_assess_v0"
    assert new["adapters"]["drevo"] == "roller.dre_first78.api.handle_decision"
    assert new["book"] == "FIRST78_67"
