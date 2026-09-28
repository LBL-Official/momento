"""ROLLER desk settings and price-path R:R."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from roller.desk_settings import (
    DeskSettingsError,
    default_settings,
    from_ui,
    load_desk_settings,
    public_settings,
    save_desk_settings,
    scaled_levels,
)
from roller.superasi.debase.ingest import extract_entry
from roller.superasi.debase.rr import format_rr, plan_rr, ratio, report_rr, trade_mean_rr
from roller.superasi.models import SuperasiError


def test_fifty_seventy_five_twenty_five_is_one_to_one():
    assert ratio(entry=5000, win_exit=7500, loss_exit=2500) == pytest.approx(1.0)
    assert format_rr(1.0) == "1.00:1"


def test_twenty_forty_ten_is_two_to_one():
    assert ratio(entry=2000, win_exit=4000, loss_exit=1000) == pytest.approx(2.0)
    assert format_rr(2.0) == "2.00:1"


def test_variable_entries_average_per_trade_ratios():
    trades = [
        {"entry_value": "2000"},
        {"entry_value": "2500"},
        {"entry_value": "3000"},
    ]
    block = trade_mean_rr(trades, win_exit=4000, loss_exit=1000)
    assert block["rr"] == pytest.approx((2.0 + 1.0 + 0.5) / 3.0)
    assert block["n"] == 3
    assert block["methods_disagree"] is True
    assert block["ratio_of_means"] == pytest.approx(1500.0 / 1500.0)


def test_zero_risk_fail_closed():
    with pytest.raises(SuperasiError) as ei:
        ratio(entry=2500, win_exit=7500, loss_exit=2500)
    assert ei.value.code == "RR_REQUIRED"
    with pytest.raises(SuperasiError) as ei:
        trade_mean_rr([{"entry_value": "1000"}], win_exit=4000, loss_exit=1000)
    assert ei.value.code == "RR_REQUIRED"


def test_report_rr_uses_plan_when_entries_constant():
    parsed = {
        "meta": {
            "entry_parameters": json.dumps({"op": "CROSS", "price_e4": 5000}),
            "win_exit_parameters": json.dumps({"op": "REACH", "price_e4": 7500}),
            "loss_exit_parameters": json.dumps({"op": "REACH", "price_e4": 2500}),
        },
        "trade_rows": [{"entry_value": "5000"}, {"entry_value": "5000"}],
    }
    out = report_rr(parsed)
    assert out["risk_reward"] == pytest.approx(1.0)
    assert out["risk_reward_basis"] == "plan"
    assert out["risk_reward_display"] == "1.00:1"


def test_report_rr_averages_when_entries_vary():
    parsed = {
        "meta": {
            "entry_parameters": json.dumps({"op": "FIRST_TOUCH", "price_e4": 2000}),
            "win_exit_parameters": json.dumps({"op": "REACH", "price_e4": 4000}),
            "loss_exit_parameters": json.dumps({"op": "REACH", "price_e4": 1000}),
        },
        "trade_rows": [{"entry_value": "2000"}, {"entry_value": "2500"}, {"entry_value": "3000"}],
    }
    out = report_rr(parsed)
    assert out["risk_reward_plan"] == pytest.approx(2.0)
    assert out["risk_reward"] == pytest.approx((2.0 + 1.0 + 0.5) / 3.0)
    assert out["risk_reward_basis"] == "trade_mean"
    assert out["risk_reward_methods_disagree"] is True


def test_extract_entry_prefers_compiled_plan():
    parsed = {
        "meta": {"entry_parameters": json.dumps({"op": "CROSS", "price_e4": 6300})},
        "trade_rows": [{"entry_value": "7000"}],
    }
    assert extract_entry(parsed) == pytest.approx(6300)
    assert plan_rr(entry=6300, win_exit=9000, loss_exit=4100) == pytest.approx(2700 / 2200)


def test_desk_settings_absent_are_defaults(tmp_path: Path):
    rec = load_desk_settings(root=tmp_path)
    assert rec["bankroll_cents"] == 2_000_000
    assert rec["allocation_bps"] == 500
    assert rec["source"] == "defaults"
    levels = scaled_levels(root=tmp_path)
    assert levels["initial_bankroll"] == pytest.approx(20_000.0)
    assert levels["trade_allocation"] == pytest.approx(0.05)
    assert levels["bankroll_floor"] == pytest.approx(15_000.0)
    assert levels["target_bankroll"] == pytest.approx(30_000.0)


def test_desk_settings_persist_and_scale(tmp_path: Path):
    saved = save_desk_settings(bankroll_cents=1_000_000, allocation_bps=1000, root=tmp_path)
    loaded = load_desk_settings(root=tmp_path)
    assert loaded["bankroll_cents"] == 1_000_000
    assert loaded["allocation_bps"] == 1000
    assert loaded["source"] == "disk"
    pub = public_settings(saved)
    assert pub["bankroll_dollars"] == pytest.approx(10_000.0)
    assert pub["allocation_pct"] == pytest.approx(10.0)
    assert pub["floor_dollars"] == pytest.approx(7_500.0)
    assert pub["target_dollars"] == pytest.approx(15_000.0)


def test_desk_settings_corrupt_fail_closed(tmp_path: Path):
    dest = tmp_path / "config"
    dest.mkdir()
    (dest / "desk_settings.json").write_text("{not-json", encoding="utf-8")
    with pytest.raises(DeskSettingsError):
        load_desk_settings(root=tmp_path)
    (dest / "desk_settings.json").write_text(json.dumps({"bankroll_cents": 0, "allocation_bps": 500}), encoding="utf-8")
    with pytest.raises(DeskSettingsError):
        load_desk_settings(root=tmp_path)


def test_from_ui_rejects_invalid():
    with pytest.raises(DeskSettingsError):
        from_ui(bankroll_dollars=0, allocation_pct=5)
    with pytest.raises(DeskSettingsError):
        from_ui(bankroll_dollars=20000, allocation_pct=0)
    cents, bps = from_ui(bankroll_dollars=20000, allocation_pct=5)
    assert cents == 2_000_000
    assert bps == 500
    assert default_settings()["bankroll_cents"] == 2_000_000


def test_settings_api_round_trip(tmp_path: Path, monkeypatch):
    import sys

    (tmp_path / "config").mkdir()
    monkeypatch.setattr("roller.desk_settings.find_root", lambda: tmp_path)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from fastapi.testclient import TestClient

    import terminal_api

    client = TestClient(terminal_api.app)
    empty = client.get("/warehouse-research/settings")
    assert empty.status_code == 200
    assert empty.json()["bankroll_dollars"] == pytest.approx(20_000.0)
    assert empty.json()["allocation_pct"] == pytest.approx(5.0)
    put = client.put(
        "/warehouse-research/settings",
        json={"bankroll_dollars": 10000, "allocation_pct": 10},
    )
    assert put.status_code == 200
    body = put.json()
    assert body["bankroll_cents"] == 1_000_000
    assert body["allocation_bps"] == 1000
    assert body["floor_dollars"] == pytest.approx(7_500.0)
    again = client.get("/warehouse-research/settings")
    assert again.json()["bankroll_dollars"] == pytest.approx(10_000.0)
    bad = client.put("/warehouse-research/settings", json={"bankroll_dollars": 0, "allocation_pct": 5})
    assert bad.status_code == 400
