"""SuperASI Phase A — Base. Evidence grade of a Labs CSV."""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest

from roller import desk_settings
from roller.config import RollerConfig
from roller.labs.schema import CSV_COLUMNS
from roller.labs.store import get_lab_csv_bytes, save_lab
from roller.risk.formulas import break_even_probability, required_win_probability, wilson_interval
from roller.risk.simulation import simulate_mode_a
from roller.superasi.base.export_csv import SUPERASI_COLUMNS
from roller.superasi.base.grading import grade_strategy
from roller.superasi.base.ingest import parse_labs_csv
from roller.superasi.base.observed import summarize_observed
from roller.superasi.base.pipeline import run_base
from roller.superasi.base.roller_desk import compute_roller_desk, inspect_risk_profile_from_desk
from roller.superasi.base.store import get_base_csv_bytes, load_base_inspect
from roller.superasi.base.validation import integrity_checks
from roller.superasi.debase.valuation import payoff_from_roller
from roller.superasi.models import SuperasiError
from roller.risk.formulas import required_win_probability, trade_ev, weekly_ev


def _payload(*, name: str, n: int, wins: int, gross_ev: float = 400.0, header_wins: int | None = None) -> dict:
    losses = n - wins
    header_w = wins if header_wins is None else header_wins
    header_l = n - header_w
    wr = header_w / n if n else 0.0
    rows = []
    for i in range(n):
        klass = "WIN" if i < wins else "LOSS"
        rows.append(
            {
                "internal_game_id": f"g{i:04d}",
                "market_id": f"M{i:04d}",
                "entry_timestamp": f"2025-10-10T{(i // 60):02d}:{(i % 60):02d}:00Z",
                "entry_value": 6500,
                "entry_operation": "CROSS",
                "classification": klass,
                "settlement_status": "YES" if klass == "WIN" else "NO",
                "settlement_value": 100 if klass == "WIN" else 0,
            }
        )
    return {
        "status": "READY",
        "question": {
            "universe": {
                "sports": ["NBA"],
                "leagues": ["NBA"],
                "seasons": ["2025-2026"],
                "date_from": "2025-10-10",
                "date_to": "2025-10-10",
            },
            "terminal": "BOTH",
        },
        "plan_hash": "aa" * 32,
        "results_contract": {
            "plan_hash": "aa" * 32,
            "compiler_version": "1.0.0",
            "warehouse_version": "wh1",
            "identity_version": "id1",
            "catalog_version": "1.0.0",
            "observation_basis": "TRADABLE_YES_BID",
            "resolution": "1_MINUTE_CANDLE",
            "pit_field": "available_at",
            "terminal": "BOTH",
            "population": n,
            "classification": {"WIN": header_w, "LOSS": header_l},
            "statistics": {
                "population": n,
                "W": header_w,
                "L": header_l,
                "win_rate": wr,
                "loss_rate": 1.0 - wr,
                "reward_e4": 2000,
                "risk_e4": 2500,
                "rr": 0.8,
                "ev_e4": gross_ev,
            },
            "entry": [{"op": "CROSS", "price_e4": 6500}],
            "win_exit": [{"op": "REACH", "price_e4": 8500}],
            "loss_exit": [{"op": "REACH", "price_e4": 4000}],
            "audit_rows": rows,
            "reproducibility": {
                "result_hash": "bb" * 32,
                "plan_hash": "aa" * 32,
                "execution_version": "1.0.0",
                "warehouse_version": "wh1",
            },
        },
        "result": {"result_hash": "bb" * 32, "engine_version": "1.0.0"},
    }


def _save(tmp_path: Path, monkeypatch, *, name: str, n: int, wins: int, **kw) -> dict:
    labs = tmp_path / "labs"
    phase = tmp_path / "phase_a"
    monkeypatch.setattr("roller.labs.store.labs_root", lambda _cfg=None: labs)
    monkeypatch.setattr("roller.superasi.base.store.phase_a_root", lambda _cfg=None: phase)
    monkeypatch.setattr("roller.labs.store.LABS_RISK_PATHS", 200)
    return save_lab(name=name, payload=_payload(name=name, n=n, wins=wins, **kw), folder="NBA", cfg=RollerConfig())


def test_mode_a_anchors_unchanged():
    assert break_even_probability(0.01, -0.02) == pytest.approx(2.0 / 3.0)
    assert required_win_probability(0.001, 0.01, -0.02) == pytest.approx(0.70)


def test_wilson_matches_formulas():
    assert wilson_interval(15, 20) == wilson_interval(15, 20, z=1.96)


def test_floor_and_target_are_additive():
    sim = simulate_mode_a(
        {
            "initial_bankroll": 20_000,
            "trade_allocation": 0.05,
            "win_return": 0.20,
            "loss_return": -0.40,
            "win_probability": 0.70,
            "trades_per_week": 10,
            "target_weekly_ev": 0.01,
            "weeks_per_year": 20,
            "monte_carlo_paths": 500,
            "bankroll_floor": 15_000,
            "target_bankroll": 30_000,
        },
        seed=20260913,
    )
    assert "P_min_bankroll_le_floor" in sim["probabilities"]
    assert "P_final_ge_target" in sim["probabilities"]
    assert sim["weekly_path_bands"][0]["week"] == 1
    default = simulate_mode_a(
        {
            "initial_bankroll": 20_000,
            "trade_allocation": 0.05,
            "win_return": 0.20,
            "loss_return": -0.40,
            "win_probability": 0.70,
            "trades_per_week": 10,
            "target_weekly_ev": 0.01,
            "weeks_per_year": 52,
            "monte_carlo_paths": 200,
        },
        seed=1,
    )
    assert "P_min_bankroll_le_floor" not in default["probabilities"]
    assert "weekly_path_bands" not in default


def test_n20_vs_n500_different_base_grade(tmp_path: Path, monkeypatch):
    small = _save(tmp_path, monkeypatch, name="Small 75", n=20, wins=15)
    large = _save(tmp_path, monkeypatch, name="Large 75", n=500, wins=375)
    a = run_base(lab_id=small["lab_id"], cfg=RollerConfig(), monte_carlo_paths=200)
    b = run_base(lab_id=large["lab_id"], cfg=RollerConfig(), monte_carlo_paths=200)
    assert a["inspect"]["observed"]["win_rate"] == pytest.approx(0.75)
    assert b["inspect"]["observed"]["win_rate"] == pytest.approx(0.75)
    assert a["inspect"]["BASE_GRADE"] != b["inspect"]["BASE_GRADE"]
    assert a["inspect"]["components"]["robustness"] != b["inspect"]["components"]["robustness"]
    assert a["inspect"]["instrument"]["break_even_probability"] == pytest.approx(2.0 / 3.0)
    assert a["inspect"]["instrument"]["required_win_probability"] == pytest.approx(0.70)
    payoff = payoff_from_roller(
        average_win=2000.0,
        average_loss=2500.0,
        entry=6500.0,
        allocation=float(desk_settings.scaled_levels()["trade_allocation"]),
    )
    ev_t = trade_ev(0.75, payoff["R_w"], payoff["R_l"])
    assert a["inspect"]["desk"]["break_even_probability"] == pytest.approx(2500.0 / 4500.0)
    assert a["inspect"]["desk"]["break_even_probability"] != pytest.approx(2.0 / 3.0)
    assert a["inspect"]["desk"]["trade_ev"] == pytest.approx(ev_t)
    assert a["inspect"]["desk"]["weekly_ev"] == pytest.approx(weekly_ev(10, ev_t))
    assert a["inspect"]["desk"]["required_win_probability"] == pytest.approx(
        required_win_probability(0.001, payoff["R_w"], payoff["R_l"])
    )
    assert a["inspect"]["desk"]["p_used"] == pytest.approx(0.75)
    assert a["inspect"]["desk"]["source"] == "roller_payoff"
    profile = a["inspect"]["risk_profile"]
    assert profile["source"] == "roller_payoff"
    assert profile["p_used"] == pytest.approx(0.75)
    assert profile["P_min_bankroll_le_floor"] != pytest.approx(0.0217, abs=1e-4)
    assert profile["P_final_ge_target"] != pytest.approx(0.1234, abs=1e-4)
    assert profile["mean_terminal_bankroll"] != pytest.approx(24425.98, abs=0.05)
    assert a["inspect"]["risk_profile"]["note"]


def _poison_header_books(raw: bytes, *, wins: int, losses: int) -> str:
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8")))
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=reader.fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in reader:
        row["wins"] = str(wins)
        row["losses"] = str(losses)
        writer.writerow(row)
    return buf.getvalue()


def test_header_row_mismatch_fail_closed(tmp_path: Path, monkeypatch):
    saved = _save(tmp_path, monkeypatch, name="Mismatch", n=20, wins=15, header_wins=16)
    found = get_lab_csv_bytes(saved["lab_id"], RollerConfig())
    assert found is not None
    reconciled = summarize_observed(parse_labs_csv(found[1]))
    assert reconciled["wins"] == 15
    assert reconciled["header_wins"] == 15
    parsed = parse_labs_csv(_poison_header_books(found[1], wins=16, losses=4))
    observed = summarize_observed(parsed)
    checks = integrity_checks(parsed, observed)
    grading = grade_strategy(observed, checks)
    assert grading["components"]["validation"] == "F"
    assert any(c["id"] == "wins_match_recount" and not c["ok"] for c in checks)
    assert observed["wins"] == 15
    assert observed["header_wins"] == 16


def test_strategy_only_csv_rejected():
    header = ",".join(CSV_COLUMNS)
    body = header + "\n" + ",".join("strategy" if col == "record_type" else "" for col in CSV_COLUMNS) + "\n"
    with pytest.raises(SuperasiError) as ei:
        parse_labs_csv(body)
    assert ei.value.code == "LABS_ROWS_REQUIRED"


def test_evidence_layers_and_byte_identity(tmp_path: Path, monkeypatch):
    saved = _save(tmp_path, monkeypatch, name="Layer Check", n=40, wins=30)
    out = run_base(lab_id=saved["lab_id"], cfg=RollerConfig(), monte_carlo_paths=200)
    downloaded = get_base_csv_bytes(out["result_id"], which="base")
    roller = get_base_csv_bytes(out["result_id"], which="roller")
    assert downloaded is not None and roller is not None
    assert downloaded[0] == "SuperasiABase[Layer Check].csv"
    assert roller[0] == "Roller[Layer Check].csv"
    disk = tmp_path / "phase_a" / out["result_id"] / downloaded[0]
    assert downloaded[1] == disk.read_bytes()
    assert downloaded[1] == out["csv_text"].encode("utf-8")
    source = get_lab_csv_bytes(saved["lab_id"], RollerConfig())
    assert source is not None
    assert roller[1] == source[1]
    parsed = list(csv.DictReader(io.StringIO(downloaded[1].decode("utf-8"))))
    assert list(parsed[0].keys()) == list(SUPERASI_COLUMNS)
    numeric = [row for row in parsed if row["value"] not in {"", "true", "false"} and row["record_type"] != "meta"]
    for row in numeric:
        assert row["evidence_layer"] in {"OBSERVED", "THEORETICAL", "MONTE_CARLO"}
    grades = {row["metric"]: row["value"] for row in parsed if row["record_type"] == "grading"}
    assert grades["BASE_GRADE"]
    assert any(row["metric"] == "not_base_grade" for row in parsed if row["record_type"] == "risk_profile")
    assert any(row["metric"] == "P_min_bankroll_le_floor" for row in parsed)


def test_load_base_inspect_rebuilds_selected_layout(tmp_path: Path, monkeypatch):
    saved = _save(tmp_path, monkeypatch, name="Inspect Rebuild", n=40, wins=30)
    out = run_base(lab_id=saved["lab_id"], cfg=RollerConfig(), monte_carlo_paths=200)
    loaded = load_base_inspect(out["result_id"], RollerConfig())
    assert loaded is not None
    assert loaded["source_lab_id"] == saved["lab_id"]
    assert loaded["observed"]["population"] == out["inspect"]["observed"]["population"]
    assert loaded["observed"]["wins"] == out["inspect"]["observed"]["wins"]
    assert loaded["BASE_GRADE"] == out["inspect"]["BASE_GRADE"]
    assert loaded["desk"]["break_even_probability"] == pytest.approx(out["inspect"]["desk"]["break_even_probability"])
    assert loaded["instrument"]["break_even_probability"] == pytest.approx(2.0 / 3.0)
    assert loaded["risk_profile"]["P_min_bankroll_le_floor"] == pytest.approx(
        out["inspect"]["risk_profile"]["P_min_bankroll_le_floor"]
    )
    assert loaded["risk_profile"]["source"] == "roller_payoff"
    assert loaded["files"]["abase_filename"] == out["inspect"]["files"]["abase_filename"]


def test_hold_yes_is_the_roller_trade():
    import json

    from roller.superasi.base.validation import integrity_checks

    rows = (
        [{"classification": "HELD_TO_SETTLEMENT", "settlement_status": "YES", "entry_value": "8000"}] * 8
        + [{"classification": "HELD_TO_SETTLEMENT", "settlement_status": "NO", "entry_value": "8000"}]
        + [{"classification": "LOSS", "settlement_status": "YES", "entry_value": "8000"}]
    )
    parsed = {
        "header": list(CSV_COLUMNS),
        "schema_missing": [],
        "trade_rows": rows,
        "risk_rows": [{"record_type": "risk"}],
        "meta": {
            "population": "10",
            "wins": "8",
            "losses": "2",
            "win_rate": f"{8 / 10:.6f}",
            "gross_ev": "",
            "average_win": "",
            "average_loss": "",
            "risk_reward": "",
            "entry_parameters": json.dumps({"price_e4": 8000}),
            "win_exit_operation": "HOLD",
            "win_exit_parameters": json.dumps({"id": "win_hold", "op": "HOLD", "outcome": "win"}),
            "loss_exit_operation": "REACH",
            "loss_exit_parameters": json.dumps({"price_e4": 3500}),
            "result_hash": "bb" * 32,
            "plan_hash": "aa" * 32,
        },
    }
    observed = summarize_observed(parsed)
    assert observed["wins"] == 8
    assert observed["losses"] == 2
    assert observed["win_rate"] == pytest.approx(0.8)
    assert observed["average_win"] == pytest.approx(2000)
    assert observed["average_loss"] == pytest.approx(4500)
    assert observed["gross_ev"] == pytest.approx((8 * 2000 - 1 * 4500 - 1 * 8000) / 10)
    checks = integrity_checks(parsed, observed)
    assert all(
        c["ok"]
        for c in checks
        if c["id"] in {"wins_match_recount", "losses_match_recount", "win_rate_reconciles"}
    )
    desk = compute_roller_desk(parsed, observed)
    assert desk["status"] == "CONFIRMED"
    assert desk["p_used"] == pytest.approx(0.8)
    assert desk["trade_ev"] is not None
    grading = grade_strategy(observed, checks)
    assert grading["components"]["validation"] != "F"
    assert grading["components"]["research_evidence"] != "F"


def test_path_loss_then_official_yes_stays_loss():
    observed = summarize_observed(
        {
            "trade_rows": [
                {"classification": "LOSS", "settlement_status": "YES", "entry_value": "8000"},
                {"classification": "HELD_TO_SETTLEMENT", "settlement_status": "YES", "entry_value": "8000"},
            ],
            "meta": {
                "population": "2",
                "wins": "1",
                "losses": "1",
                "win_exit_operation": "HOLD",
            },
        }
    )
    assert observed["wins"] == 1
    assert observed["losses"] == 1


def test_path_only_held_yes_is_not_a_trade_win():
    observed = summarize_observed(
        {
            "trade_rows": [
                {"classification": "WIN", "settlement_status": "YES", "entry_value": "6300"},
                {"classification": "HELD_TO_SETTLEMENT", "settlement_status": "YES", "entry_value": "6300"},
            ],
            "meta": {
                "population": "2",
                "wins": "1",
                "losses": "0",
                "win_exit_operation": "REACH",
                "win_exit_parameters": '{"price_e4":8700}',
                "loss_exit_operation": "REACH",
                "loss_exit_parameters": '{"price_e4":4100}',
                "entry_parameters": '{"price_e4":6300}',
            },
        }
    )
    assert observed["wins"] == 1
    assert observed["losses"] == 0


def test_roller_desk_unavailable_without_payoff():
    parsed = {"trade_rows": [{"entry_value": ""}], "meta": {}}
    observed = {"average_win": None, "average_loss": None, "win_rate": 0.75}
    desk = compute_roller_desk(parsed, observed)
    assert desk["status"] == "DATA_REQUIRED"
    assert desk["break_even_probability"] is None
    assert desk["trade_ev"] is None
    assert desk["weekly_ev"] is None
    assert desk["required_win_probability"] is None
    profile = inspect_risk_profile_from_desk(desk)
    assert profile["status"] == "DATA_REQUIRED"
    assert profile["P_min_bankroll_le_floor"] is None
    assert profile["P_final_ge_target"] is None
    assert profile["mean_terminal_bankroll"] is None


def test_health_lists_base_capabilities():
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from fastapi.testclient import TestClient

    import terminal_api

    body = TestClient(terminal_api.app).get("/health").json()
    assert "superasi_base_run" in body["capabilities"]
    assert "superasi_base_results" in body["capabilities"]
    assert "superasi_seed_asked_six" in body["capabilities"]
