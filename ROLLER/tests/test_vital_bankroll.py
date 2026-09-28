"""Vital bankroll page: account facts, desired allocation, session limits."""

from __future__ import annotations

import json

import pytest

from roller.vital.bankroll import (
    handle_allocation,
    handle_bankroll,
    handle_limits,
    unit_cents,
)
from roller.vital.errors import VitalError
from roller.vital.store import allocation_history_path, load_jsonl, seed_mlb_001
from roller.vital.versions import BOT_ID, CONTROL_CONFIRMATION, LIVE_CONFIRMATION


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("VITAL_ROOT", str(tmp_path))
    monkeypatch.setenv("JUMP_CATALOG_ROOT", str(tmp_path / "catalog"))
    monkeypatch.setenv("JUMP_BOTS_ROOT", str(tmp_path / "jump_bots"))
    monkeypatch.setenv("JUMP_SKIP_KALSHI", "1")
    monkeypatch.delenv("VITAL_AWS_CONTROL", raising=False)
    monkeypatch.setenv("VITAL_AWS_HOST_FETCH", "0")
    seed_mlb_001(root=tmp_path)


def _write_book(tmp_path, *, top=3931, mlb=1512, demo=None, demo_origin=None):
    catalog = tmp_path / "catalog"
    catalog.mkdir(parents=True, exist_ok=True)
    books = {
        "PRODUCTION": {
            "current_cents": mlb,
            "exchange_index": 3,
            "top_level_cents": top,
            "origin_cents": 5000,
            "source": "kalshi_balance_breakdown",
            "status": "CONFIRMED",
        }
    }
    if demo is not None:
        books["DEMO"] = {
            "current_cents": demo,
            "top_level_cents": demo,
            "origin_cents": demo_origin if demo_origin is not None else demo,
            "source": "kalshi_get_balance",
            "status": "CONFIRMED",
            "environment": "DEMO",
        }
    (catalog / "bankroll.json").write_text(
        json.dumps(
            {
                "books": books,
                "origin_bankroll_cents": 5000,
            }
        ),
        encoding="utf-8",
    )
    (catalog / "bankroll_history.jsonl").write_text(
        json.dumps(
            {
                "current_cents": top,
                "environment": "PRODUCTION",
                "exchange_index": 3,
                "observed_at": "2026-09-13T20:00:00Z",
                "source": "kalshi_balance_breakdown",
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_unit_cents_modes_are_integer():
    assert unit_cents(mode="FIXED_CENTS", amount_cents=331, allocation_bps=None, bankroll_cents=3931) == 331
    assert unit_cents(mode="PCT_CURRENT", amount_cents=None, allocation_bps=1250, bankroll_cents=3931) == 491
    assert unit_cents(mode="PCT_WEEKLY", amount_cents=None, allocation_bps=1250, bankroll_cents=5000) == 625
    assert unit_cents(mode="PCT_CURRENT", amount_cents=None, allocation_bps=1249, bankroll_cents=3931) == 490
    assert unit_cents(mode="PCT_CURRENT", amount_cents=None, allocation_bps=1251, bankroll_cents=3931) == 491


def test_bankroll_view_keeps_four_facts_separate(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    _write_book(tmp_path)
    body = handle_bankroll(root=tmp_path)
    account = body["account"]
    assert account["top_level_cents"]["status"] == "CONFIRMED"
    assert account["top_level_cents"]["value"] == 3931
    assert account["mlb_shard_cents"]["value"] == 1512
    assert account["factory_bankroll_cents"]["value"] == 5000
    assert account["factory_unit_cents"]["value"] == 625
    assert account["demo_not_mixed"] is True
    mlb = next(row for row in body["bots"] if row["bot_id"] == BOT_ID)
    assert mlb["allocation"]["observed"]["value"]["unit_cents"] == 625
    assert mlb["allocation"]["confirmed"]["value"]["unit_cents"] == 625
    assert mlb["limits"]["remaining"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert mlb["limits"]["one_bet_per_game"] is True
    assert body["honesty"]["desired_is_not_live_size"] is True
    assert body["kalshi_mcp"] is False
    assert body["seeded_from_mcp"] is False
    assert body["demo_account"]["top_level_cents"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert body["demo_account"]["top_level_cents"]["value"] is None
    assert body["demo_report"]["fill_result_is_not_account_pnl"] is True
    assert body["demo_report"]["live_ev"] == "UNAVAILABLE"
    assert body["demo_report"]["trade_n"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert body["demo_report"]["wins"]["value"] is None


def test_unread_demo_source_points_at_demo_kalshi(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.delenv("JUMP_SKIP_KALSHI", raising=False)
    monkeypatch.delenv("JUMP_KALSHI_SECRET_FILE_DEMO", raising=False)
    monkeypatch.setattr(
        "roller.jump.catalog.kalshi.default_demo_secret_file",
        lambda: tmp_path / "missing-demo.json",
    )
    body = handle_bankroll(root=tmp_path)
    source = body["demo_account"]["source"]
    assert source["status"] == "OBSERVATION_UNAVAILABLE"
    assert source["value"] is None
    assert "demo.kalshi.co" in (source.get("detail") or "")


def test_demo_secret_file_defaults_to_home_kalshi(monkeypatch, tmp_path):
    from roller.jump.catalog import kalshi as k

    monkeypatch.delenv("JUMP_KALSHI_SECRET_FILE_DEMO", raising=False)
    secret = tmp_path / "demo.json"
    secret.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(k, "default_demo_secret_file", lambda: secret)
    assert k._secret_file("DEMO") == secret
    monkeypatch.setenv("JUMP_KALSHI_SECRET_FILE_DEMO", str(tmp_path / "explicit.json"))
    assert k._secret_file("DEMO") is None


def test_unread_account_is_not_zero(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    body = handle_bankroll(root=tmp_path)
    assert body["account"]["top_level_cents"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert body["account"]["top_level_cents"]["value"] is None
    assert body["account"]["mlb_shard_cents"]["value"] is None
    assert body["demo_account"]["top_level_cents"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert body["demo_account"]["top_level_cents"]["value"] is None
    assert body["demo_account"]["origin_pnl_cents"]["value"] is None


def test_demo_book_stays_off_production(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    _write_book(tmp_path, demo=2000, demo_origin=2000)
    body = handle_bankroll(root=tmp_path)
    assert body["account"]["top_level_cents"]["value"] == 3931
    assert body["account"]["mlb_shard_cents"]["value"] == 1512
    assert body["demo_account"]["top_level_cents"]["value"] == 2000
    assert body["demo_account"]["origin_cents"]["value"] == 2000
    assert body["demo_account"]["origin_pnl_cents"]["value"] == 0
    assert body["demo_account"]["default_unit_cents"]["value"] == 100
    assert body["demo_report"]["trade_n"]["status"] == "CONFIRMED"
    assert body["demo_report"]["trade_n"]["value"] == 0


def test_demo_bots_default_to_one_dollar(monkeypatch, tmp_path):
    from roller.jump.bots.store import create_draft, demo_default_settings

    _isolate(monkeypatch, tmp_path)
    _write_book(tmp_path, demo=2000, demo_origin=2000)
    defaults = demo_default_settings(observed_bankroll=2000)
    assert defaults["sizing_mode"] == "FIXED_CENTS"
    assert defaults["amount_cents"] == 100
    assert defaults["bankroll_cents"] == 2000
    draft = create_draft(
        name="Demo dollar",
        iti={
            "folder": "x/x_ITI",
            "strategy_name": "x_ITI",
            "strategy_fingerprint": "a" * 64,
            "question": {"universe": {"sports": ["MLB"], "leagues": ["MLB"]}},
        },
        root=tmp_path / "jump_bots",
    )
    assert draft["settings"]["amount_cents"] == 100
    assert draft["settings"]["sizing_mode"] == "FIXED_CENTS"
    view = handle_bankroll(root=tmp_path)
    demo = next(row for row in view["bots"] if row["bot_id"] == draft["bot_id"])
    assert demo["environment"] == "DEMO"
    assert demo["allocation"]["desired"]["value"]["unit_cents"] == 100


def test_demo_pct_current_does_not_use_production_cash(monkeypatch, tmp_path):
    from roller.jump.bots.store import create_draft, save_bot, load_bot

    _isolate(monkeypatch, tmp_path)
    _write_book(tmp_path, demo=2000, demo_origin=2000)
    draft = create_draft(
        name="Pct demo",
        iti={
            "folder": "x/x_ITI",
            "strategy_name": "x_ITI",
            "strategy_fingerprint": "b" * 64,
            "question": {"universe": {"sports": ["MLB"], "leagues": ["MLB"]}},
        },
        root=tmp_path / "jump_bots",
    )
    bot = load_bot(draft["bot_id"], root=tmp_path / "jump_bots")
    bot["settings"] = {
        "sizing_mode": "PCT_CURRENT",
        "allocation_bps": 500,
        "bankroll_cents": 2000,
    }
    save_bot(bot, root=tmp_path / "jump_bots")
    view = handle_bankroll(root=tmp_path)
    demo = next(row for row in view["bots"] if row["bot_id"] == draft["bot_id"])
    assert demo["allocation"]["desired"]["value"]["unit_cents"] == 100
    assert demo["allocation"]["desired"]["value"]["unit_cents"] != 196


def test_pack_book_demo_origin_is_not_factory_fifty():
    from roller.jump.catalog.bankroll import pack_book

    first = pack_book({"environment": "DEMO", "current_cents": 2000, "source": "kalshi_get_balance"})
    assert first["origin_cents"] == 2000
    assert first["top_level_cents"] == 2000
    assert first["origin_cents"] != 5000
    later = pack_book(
        {"environment": "DEMO", "current_cents": 1850, "source": "kalshi_get_balance"},
        existing_book=first,
    )
    assert later["current_cents"] == 1850
    assert later["origin_cents"] == 2000


def test_observe_demo_skip_does_not_rewrite_production(monkeypatch, tmp_path):
    from roller.vital.api import handle_kalshi_observe

    _isolate(monkeypatch, tmp_path)
    _write_book(tmp_path)
    observed = handle_kalshi_observe(BOT_ID, {"environment": "DEMO"}, root=tmp_path)
    assert observed["environment"] == "DEMO"
    assert observed["read_only"] is True
    assert observed["submits"] is False
    assert observed["status"] == "OBSERVATION_UNAVAILABLE"
    view = handle_bankroll(root=tmp_path)
    assert view["account"]["top_level_cents"]["value"] == 3931


def test_observe_rejects_live_token(monkeypatch, tmp_path):
    from roller.vital.api import handle_kalshi_observe

    _isolate(monkeypatch, tmp_path)
    with pytest.raises(VitalError) as exc:
        handle_kalshi_observe(BOT_ID, {"environment": "DEMO", "confirmation": LIVE_CONFIRMATION}, root=tmp_path)
    assert exc.value.code == "REJECTED"


def test_post_allocation_stores_desired_not_live_size(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    _write_book(tmp_path)
    posted = handle_allocation(
        BOT_ID,
        {"mode": "FIXED_CENTS", "amount_cents": 331},
        root=tmp_path,
    )
    assert posted["http_200_not_live_size"] is True
    assert posted["apply_status"] == "APPLY_REQUIRED"
    assert posted["unit_cents"] == 331
    view = handle_bankroll(root=tmp_path)
    mlb = next(row for row in view["bots"] if row["bot_id"] == BOT_ID)
    assert mlb["allocation"]["desired"]["value"]["unit_cents"] == 331
    assert mlb["allocation"]["observed"]["value"]["unit_cents"] == 625
    assert mlb["allocation"]["apply_status"] == "APPLY_REQUIRED"
    history = load_jsonl(allocation_history_path(BOT_ID, root=tmp_path))
    assert history
    assert history[-1]["amount_cents"] == 331


def test_enable_live_trading_is_rejected(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    with pytest.raises(VitalError) as exc:
        handle_allocation(
            BOT_ID,
            {"mode": "FIXED_CENTS", "amount_cents": 331, "confirmation": LIVE_CONFIRMATION},
            root=tmp_path,
        )
    assert exc.value.code == "REJECTED"
    assert handle_bankroll(root=tmp_path)["bots"][0]["allocation"]["observed"]["value"]["unit_cents"] == 625


def test_control_confirmation_still_does_not_write_live_host(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv("VITAL_AWS_CONTROL", "1")
    posted = handle_allocation(
        BOT_ID,
        {"mode": "FIXED_CENTS", "amount_cents": 331, "confirmation": CONTROL_CONFIRMATION},
        root=tmp_path,
    )
    assert posted["applied"] is False
    assert posted["apply_status"] == "CONTROL_DISABLED"


def test_malformed_mode_and_zero_cents_rejected(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    with pytest.raises(VitalError):
        handle_allocation(BOT_ID, {"mode": "PERCENT"}, root=tmp_path)
    with pytest.raises(VitalError):
        handle_allocation(BOT_ID, {"mode": "FIXED_CENTS", "amount_cents": 0}, root=tmp_path)
    with pytest.raises(VitalError):
        handle_limits(BOT_ID, {"max_daily_entries": 0}, root=tmp_path)


def test_demo_toml_writes_sizing_and_limits():
    from roller.jump.bots.demo_host import demo_toml

    text = demo_toml(
        {
            "settings": {
                "bankroll_cents": 3931,
                "sizing_mode": "FIXED_CENTS",
                "allocation_bps": 800,
                "amount_cents": 331,
                "max_daily_entries": 3,
                "max_daily_loss_cents": 331,
            }
        }
    )
    assert 'mode = "paper"' in text
    assert "allocation_bps = 800" in text
    assert "initial_bankroll_cents = 3931" in text
    assert 'sizing_mode = "FIXED_CENTS"' in text
    assert "max_position_budget_cents = 331" in text
    assert "max_daily_entries = 3" in text
    assert "max_daily_loss_cents = 331" in text
    assert "enabled = false" in text
    assert "ENABLE_LIVE_TRADING" not in text


def test_limits_persist_desired_remaining_unread(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    posted = handle_limits(
        BOT_ID,
        {"max_daily_entries": 3, "max_daily_wins": 2, "max_daily_loss_cents": 331},
        root=tmp_path,
    )
    assert posted["desired"]["max_daily_entries"] == 3
    assert posted["apply_status"] == "APPLY_REQUIRED"
    view = handle_bankroll(root=tmp_path)
    limits = next(row for row in view["bots"] if row["bot_id"] == BOT_ID)["limits"]
    assert limits["desired"]["value"]["max_daily_entries"] == 3
    assert limits["desired"]["value"]["max_daily_loss_cents"] == 331
    assert limits["remaining"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert limits["hit"]["status"] == "OBSERVATION_UNAVAILABLE"
