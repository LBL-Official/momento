"""Demo MLB shard plan is fail-closed. Missing is not $0. Production is refused."""

from __future__ import annotations

import pytest

from roller.vital.demo_shard import (
    plan_demo_mlb_ensure_user,
    plan_demo_mlb_transfer,
    refuse_production_transfer,
)


def _body(*, breakdown, top=2000):
    return {
        "environment": "DEMO",
        "balance_cents": top,
        "balance_breakdown": breakdown,
        "origin": "https://external-api.demo.kalshi.co",
    }


def test_refuse_production_environment():
    with pytest.raises(ValueError, match="production"):
        refuse_production_transfer(environment="production")


def test_refuse_production_secret_id():
    with pytest.raises(ValueError, match="production secret"):
        refuse_production_transfer(environment="demo", secret_id="momento/kalshi/production")


def test_refuse_production_origin():
    with pytest.raises(ValueError, match="production origin"):
        refuse_production_transfer(environment="demo", origin="https://external-api.kalshi.com")


def test_missing_breakdown_is_unread_not_zero():
    planned = plan_demo_mlb_transfer({"environment": "DEMO", "balance_cents": 2000})
    assert planned["ok"] is False
    assert planned["transfer"] is False
    assert planned["mlb_shard_cents"] is None
    assert "unread" in planned["detail"]


def test_missing_mlb_index_is_unread_not_zero():
    planned = plan_demo_mlb_transfer(
        _body(breakdown=[{"exchange_index": 0, "balance": "20.00"}])
    )
    assert planned["ok"] is False
    assert planned["mlb_shard_cents"] is None
    assert planned["exchange_index"] is None
    assert "3 unread" in planned["detail"]


def test_already_funded_does_not_transfer():
    planned = plan_demo_mlb_transfer(
        _body(
            breakdown=[
                {"exchange_index": 0, "balance": "10.00"},
                {"exchange_index": 3, "balance": "12.00"},
            ]
        )
    )
    assert planned["ok"] is True
    assert planned["transfer"] is False
    assert planned["mlb_shard_cents"] == 1200


def test_already_funded_still_plans_ensure_user_touch():
    planned = plan_demo_mlb_ensure_user(
        _body(
            breakdown=[
                {"exchange_index": 0, "balance": "10.00"},
                {"exchange_index": 3, "balance": "10.00"},
            ]
        )
    )
    assert planned["ok"] is True
    assert planned["transfer"] is True
    assert planned["ensure_user"] is True
    assert planned["amount_cents"] == 100
    assert planned["amount_centicents"] == 10_000
    assert planned["source_remaining_cents"] == 900
    assert planned["not_create_v2"] is True


def test_plans_ten_dollars_when_source_has_enough():
    planned = plan_demo_mlb_transfer(
        _body(
            breakdown=[
                {"exchange_index": 0, "balance": "20.00"},
                {"exchange_index": 3, "balance": "0.00"},
            ]
        )
    )
    assert planned["ok"] is True
    assert planned["transfer"] is True
    assert planned["amount_cents"] == 1000
    assert planned["amount_centicents"] == 100_000
    assert planned["source_exchange_shard"] == 0
    assert planned["destination_exchange_shard"] == 3
    assert planned["source_remaining_cents"] == 1000
    assert planned["mlb_shard_cents"] == 0


def test_source_short_fails_closed():
    planned = plan_demo_mlb_transfer(
        _body(
            breakdown=[
                {"exchange_index": 0, "balance": "5.00"},
                {"exchange_index": 3, "balance": "0.00"},
            ]
        )
    )
    assert planned["ok"] is False
    assert planned["transfer"] is False
    assert planned["mlb_shard_cents"] == 0
    assert "fewer" in planned["detail"]


def test_demo_sync_book_keeps_mlb_shard():
    from roller.jump.catalog.connection import sync_kalshi

    packed = {
        "ok": True,
        "environment": "DEMO",
        "current_cents": 2000,
        "balance_cents": 2000,
        "balance_breakdown": [
            {"exchange_index": 0, "balance": "20.00"},
            {"exchange_index": 3, "balance": "0.00"},
        ],
        "fills": [],
        "positions": [],
    }
    # Exercise the persist shape used by sync: pack then copy shard fields.
    from roller.jump.catalog.bankroll import pack_book

    book = pack_book(packed)
    assert book["mlb_shard_cents"] == 0
    assert book["balance_breakdown"]


def test_demo_pack_keeps_breakdown_and_mlb_shard():
    from roller.jump.catalog.bankroll import pack_book

    packed = pack_book(
        {
            "environment": "DEMO",
            "balance_cents": 2000,
            "balance_breakdown": [
                {"exchange_index": 0, "balance": "20.00"},
                {"exchange_index": 3, "balance": "0.00"},
            ],
        }
    )
    assert packed is not None
    assert packed["current_cents"] == 2000
    assert packed["mlb_shard_cents"] == 0
    assert packed["exchange_index"] == 3
    assert packed["balance_breakdown"]


def test_attach_funds_mlb_before_unit_start(monkeypatch, tmp_path):
    from roller.vital.demo_attach import attach_demo

    monkeypatch.delenv("JUMP_SKIP_KALSHI", raising=False)
    monkeypatch.setenv("VITAL_ROOT", str(tmp_path / "vital"))
    order: list[object] = []

    def _fund(*, execute: bool = False):
        order.append(("fund", execute))
        return {
            "ok": True,
            "transferred": True,
            "not_create_v2": True,
            "after": {"mlb_shard_cents": 1000},
        }

    def _start(bot):
        order.append("start")
        return {
            "attempted": True,
            "active": True,
            "unit_started": True,
            "ok": True,
            "secret_missing": False,
            "aws_runtime_id": "momento-demo@mlb-099.service",
            "unit": "momento-demo@mlb-099.service",
            "state_dir": "/var/lib/momento/demo/mlb-099/state",
            "reason": None,
            "factory_path_used": False,
        }

    monkeypatch.setattr(
        "roller.vital.demo_attach._observe_demo_book",
        lambda: {
            "status": "CONFIRMED",
            "ok": True,
            "read_only": True,
            "submits": False,
            "environment": "DEMO",
            "balance_cents": 2000,
            "fill_n": 0,
            "position_n": 0,
            "detail": None,
            "http_200_not_running": True,
        },
    )
    monkeypatch.setattr(
        "roller.vital.demo_attach.inspect_aws_demo",
        lambda: {
            "status": "CONFIRMED",
            "session": "CONFIRMED",
            "demo_secret": "CONFIRMED",
            "unit_started": False,
            "factory_toml_refused": True,
            "momento_live_untouched": True,
            "detail": None,
        },
    )
    monkeypatch.setattr("roller.vital.demo_attach.start_iti_unit", _start)
    monkeypatch.setattr("roller.vital.demo_shard.fund_demo_mlb_shard", _fund)
    bot = {"bot_id": "mlb-099", "sport": "mlb", "kind": "research_iti"}
    out = attach_demo(bot, vital_root=tmp_path / "vital")
    assert order == [("fund", True), "start"]
    assert out["attach"]["mlb_shard"]["transferred"] is True
    assert out["attach"]["not_create_v2"] is True
    assert out["activation"] == "RUNNING_DEMO"


def test_attach_skips_fund_for_nba(monkeypatch, tmp_path):
    from roller.vital.demo_attach import attach_demo

    monkeypatch.delenv("JUMP_SKIP_KALSHI", raising=False)
    monkeypatch.setenv("VITAL_ROOT", str(tmp_path / "vital"))
    called = {"fund": 0}

    def _fund(*, execute: bool = False):
        called["fund"] += 1
        raise AssertionError("NBA attach must not fund the MLB shard")

    monkeypatch.setattr(
        "roller.vital.demo_attach._observe_demo_book",
        lambda: {"status": "CONFIRMED", "ok": True, "environment": "DEMO", "http_200_not_running": True},
    )
    monkeypatch.setattr(
        "roller.vital.demo_attach.inspect_aws_demo",
        lambda: {"status": "CONFIRMED", "session": "CONFIRMED", "unit_started": False},
    )
    monkeypatch.setattr(
        "roller.vital.demo_attach.start_iti_unit",
        lambda bot: {
            "attempted": True,
            "active": True,
            "unit_started": True,
            "ok": True,
            "aws_runtime_id": "momento-demo@nba-001.service",
            "unit": "momento-demo@nba-001.service",
            "factory_path_used": False,
        },
    )
    monkeypatch.setattr("roller.vital.demo_shard.fund_demo_mlb_shard", _fund)
    out = attach_demo(
        {"bot_id": "nba-001", "sport": "nba", "kind": "research_iti"},
        vital_root=tmp_path / "vital",
    )
    assert called["fund"] == 0
    assert out["attach"]["mlb_shard"]["skipped"] is True
    assert out["attach"]["mlb_shard"]["not_create_v2"] is True


def test_attach_starts_when_mlb_fund_fails(monkeypatch, tmp_path):
    from roller.vital.demo_attach import attach_demo

    monkeypatch.delenv("JUMP_SKIP_KALSHI", raising=False)
    monkeypatch.setenv("VITAL_ROOT", str(tmp_path / "vital"))
    monkeypatch.setattr(
        "roller.vital.demo_attach._observe_demo_book",
        lambda: {"status": "CONFIRMED", "ok": True, "environment": "DEMO", "http_200_not_running": True},
    )
    monkeypatch.setattr(
        "roller.vital.demo_attach.inspect_aws_demo",
        lambda: {"status": "CONFIRMED", "session": "CONFIRMED", "unit_started": False},
    )
    monkeypatch.setattr(
        "roller.vital.demo_attach.start_iti_unit",
        lambda bot: {
            "attempted": True,
            "active": True,
            "unit_started": True,
            "ok": True,
            "aws_runtime_id": "momento-demo@mlb-098.service",
            "unit": "momento-demo@mlb-098.service",
            "factory_path_used": False,
        },
    )
    monkeypatch.setattr(
        "roller.vital.demo_shard.fund_demo_mlb_shard",
        lambda **_: (_ for _ in ()).throw(RuntimeError("fills-read unread")),
    )
    out = attach_demo(
        {"bot_id": "mlb-098", "sport": "mlb", "kind": "research_iti"},
        vital_root=tmp_path / "vital",
    )
    assert out["attach"]["unit_started"] is True
    assert out["attach"]["mlb_shard"]["ok"] is False
    assert out["attach"]["mlb_shard"]["execute_error"] is True
    assert out["activation"] == "RUNNING_DEMO"


def test_plan_refuses_production_environment_in_body():
    planned = plan_demo_mlb_transfer(
        {
            "environment": "PRODUCTION",
            "balance_breakdown": [{"exchange_index": 3, "balance": "0.00"}],
        }
    )
    assert planned["ok"] is False
    assert planned["mlb_shard_cents"] is None
