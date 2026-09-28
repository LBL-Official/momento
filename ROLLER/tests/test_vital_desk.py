"""Vital desk snapshot is compose-only. It does not observe Kalshi or invent cash."""

from __future__ import annotations

from roller.vital.api import handle_desk
from roller.vital.errors import VitalError
from roller.vital.versions import BOT_ID, CODE_VERSION


def test_list_surface_has_both_books_and_no_observe(tmp_path):
    body = handle_desk(BOT_ID, "list", root=tmp_path)
    assert body["surface"] == "list"
    assert body["observe_included"] is False
    assert body["selected_id"] == BOT_ID
    assert body["health"]["code_version"] == CODE_VERSION
    assert body["header"]["PRODUCTION"]["environment"] == "PRODUCTION"
    assert body["header"]["DEMO"]["environment"] == "DEMO"
    assert "sports shard 3" in body["header"]["DEMO"]["shard_label"]
    assert body["surfaces"] == {}
    assert body["focus"]["bot"]["bot_id"] == BOT_ID
    assert body["focus"]["status"]["lifecycle"]
    assert body["focus"]["controls"]["fail_closed"] is True
    assert body["focus"]["controls"]["enabled"] is False
    assert body["focus"]["integration"]["proof_id"] == "LIVE_SERVICE_INTEGRATION"
    assert body["focus"]["integration"]["collapsed_to_running"] is False
    assert body["n"] >= 1


def test_full_surface_loads_mlb_ledger_without_observe(tmp_path):
    body = handle_desk("mlb-bot-one", "full", root=tmp_path)
    assert body["selected_id"] == BOT_ID
    assert body["observe_included"] is False
    assert "parameters" in body["surfaces"]
    assert "execution" in body["surfaces"]
    assert "diagnose" in body["surfaces"]
    assert body["surfaces"]["orders"] is not None
    assert body["focus"]["controls"]["fail_closed"] is True


def test_unknown_surface_and_bot_fail_closed(tmp_path):
    try:
        handle_desk(BOT_ID, "tape", root=tmp_path)
    except VitalError as exc:
        assert exc.code == "REJECTED"
    else:
        raise AssertionError("expected REJECTED")
    try:
        handle_desk("not-a-bot", "list", root=tmp_path)
    except VitalError as exc:
        assert exc.code == "BOT_NOT_FOUND"
    else:
        raise AssertionError("expected BOT_NOT_FOUND")
