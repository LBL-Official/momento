"""SuperASI Phase B — Debase. Roller-dynamic EV / R:R."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from roller.config import RollerConfig
from roller.labs.store import save_lab
from roller.risk.formulas import break_even_probability, trade_ev, weekly_return_from_wins
from roller.risk.simulation import simulate_mode_b
from roller.superasi.base.grade_config import letter_rank
from roller.superasi.base.pipeline import run_base
from roller.superasi.debase.export_csv import SUPERASI_COLUMNS
from roller.superasi.debase.ingest import load_phase_a_folder
from roller.superasi.debase.pipeline import run_debase
from roller.superasi.debase.store import get_debase_csv_bytes, load_debase_inspect
from roller.superasi.debase.valuation import desk_identity_checks, payoff_from_roller
from roller.superasi.models import SuperasiError
from roller.desk_settings import default_settings


def _ev(n: int, wins: int, reward: float = 2000.0, risk: float = 2500.0) -> float:
    losses = n - wins
    return (wins * reward - losses * risk) / n


def _payload(*, name: str, n: int, wins: int, gross_ev: float | None = None, header_wins: int | None = None) -> dict:
    losses = n - wins
    header_w = wins if header_wins is None else header_wins
    header_l = n - header_w
    wr = header_w / n if n else 0.0
    ev = _ev(n, header_w) if gross_ev is None else gross_ev
    rows = []
    for i in range(n):
        klass = "WIN" if i < wins else "LOSS"
        rows.append(
            {
                "internal_game_id": f"g{i:04d}",
                "market_id": f"M{i:04d}",
                "entry_timestamp": f"2025-10-{(1 + i // 8):02d}T{(i // 60):02d}:{(i % 60):02d}:00Z",
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
                "date_from": "2025-10-01",
                "date_to": "2025-10-31",
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
                "ev_e4": ev,
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


def _prep(tmp_path: Path, monkeypatch):
    labs = tmp_path / "labs"
    phase_a = tmp_path / "phase_a"
    phase_b = tmp_path / "phase_b"
    monkeypatch.setattr("roller.labs.store.labs_root", lambda _cfg=None: labs)
    monkeypatch.setattr("roller.superasi.base.store.phase_a_root", lambda _cfg=None: phase_a)
    monkeypatch.setattr("roller.superasi.debase.store.phase_b_root", lambda _cfg=None: phase_b)
    monkeypatch.setattr("roller.labs.store.LABS_RISK_PATHS", 80)
    monkeypatch.setattr("roller.desk_settings.load_desk_settings", lambda **_kw: default_settings())
    return labs, phase_a, phase_b


def _run_pair(tmp_path: Path, monkeypatch, *, name: str, n: int, wins: int, **kw):
    _prep(tmp_path, monkeypatch)
    saved = save_lab(
        name=name,
        payload=_payload(name=name, n=n, wins=wins, **kw),
        folder="NBA",
        question=_payload(name=name, n=n, wins=wins, **kw)["question"],
        cfg=RollerConfig(),
    )
    base = run_base(lab_id=saved["lab_id"], cfg=RollerConfig(), monte_carlo_paths=80)
    debase = run_debase(result_id=base["result_id"], cfg=RollerConfig(), monte_carlo_paths=80)
    return saved, base, debase


def test_load_debase_inspect_rebuilds_selected_layout(tmp_path: Path, monkeypatch):
    saved, _base, debase = _run_pair(tmp_path, monkeypatch, name="Inspect Rebuild B", n=20, wins=15)
    loaded = load_debase_inspect(debase["result_id"], RollerConfig())
    inspect = debase["inspect"]
    assert loaded is not None
    assert loaded["source_lab_id"] == saved["lab_id"]
    assert loaded["observed"]["population"] == inspect["observed"]["population"]
    assert loaded["observed"]["wins"] == inspect["observed"]["wins"]
    assert loaded["DEBASE_GRADE"] == inspect["DEBASE_GRADE"]
    assert loaded["p_working"] == pytest.approx(inspect["p_working"])
    assert loaded["valuation"]["weekly_ev"] == pytest.approx(inspect["valuation"]["weekly_ev"], abs=1e-6)
    assert loaded["desk"]["break_even_probability"] == pytest.approx(inspect["desk"]["break_even_probability"])
    assert loaded["risk_profile"]["source"] == "roller_payoff"
    assert "capped_to_base" in loaded
    assert loaded["files"]["debase_filename"] == inspect["files"]["debase_filename"]


def test_desk_identity_anchors():
    rows = {item["id"]: item["ok"] for item in desk_identity_checks()}
    assert rows["desk_break_even"]
    assert rows["desk_ev_at_70"]
    assert rows["desk_week_7"]
    assert rows["desk_week_10"]
    assert rows["desk_week_0"]
    assert rows["desk_compound_20"]
    assert rows["desk_target_30k"]
    assert rows["desk_floor_14999"]
    assert break_even_probability(0.01, -0.02) == pytest.approx(2.0 / 3.0)
    assert trade_ev(0.70, 0.01, -0.02) == pytest.approx(0.001)
    assert weekly_return_from_wins(7, 10, 0.01, -0.02) == pytest.approx(0.01)


def test_roller_payoff_is_dynamic():
    payoff = payoff_from_roller(average_win=2000.0, average_loss=2500.0, entry=6500.0)
    assert payoff["p_be"] == pytest.approx(2500.0 / 4500.0)
    assert payoff["risk_reward"] == pytest.approx(0.8)
    assert payoff["win_return_on_capital"] == pytest.approx(2000.0 / 6500.0)
    assert payoff["loss_return_on_capital"] == pytest.approx(-2500.0 / 6500.0)
    assert payoff["R_w"] != pytest.approx(0.01)
    assert payoff["R_l"] != pytest.approx(-0.02)
    with pytest.raises(SuperasiError) as ei:
        payoff_from_roller(average_win=None, average_loss=2500.0, entry=6500.0)
    assert ei.value.code == "PAYOFF_REQUIRED"


def test_mode_b_floor_is_additive():
    cfg = {
        "initial_bankroll": 20_000,
        "trade_allocation": 0.05,
        "win_return": 2000.0 / 6500.0,
        "loss_return": -2500.0 / 6500.0,
        "win_probability": 0.70,
        "trades_per_week": 10,
        "target_weekly_ev": 0.01,
        "weeks_per_year": 20,
        "monte_carlo_paths": 200,
        "bankroll_floor": 15_000,
        "target_bankroll": 30_000,
    }
    sim = simulate_mode_b(cfg, ["WIN", "LOSS"] * 10, seed=20260913)
    assert "P_min_bankroll_le_floor" in sim["probabilities"]
    assert "weekly_path_bands" in sim
    default = simulate_mode_b(
        {
            "initial_bankroll": 20_000,
            "trade_allocation": 0.05,
            "win_return": 0.20,
            "loss_return": -0.40,
            "win_probability": 0.70,
            "trades_per_week": 10,
            "target_weekly_ev": 0.01,
            "weeks_per_year": 52,
            "monte_carlo_paths": 80,
        },
        ["WIN", "LOSS"] * 10,
        seed=1,
    )
    assert "P_min_bankroll_le_floor" not in default["probabilities"]
    assert "weekly_path_bands" not in default


def test_p_working_is_iqr1_and_desk_uses_it(tmp_path: Path, monkeypatch):
    from roller.risk.formulas import trade_ev, wilson_interval
    from roller.superasi.debase.iqr import iqr_hinges
    from roller.superasi.debase.versions import P_WORKING_BASIS, WILSON_Z_IQR1

    _, base, debase = _run_pair(tmp_path, monkeypatch, name="Dynamic 75", n=40, wins=30)
    inspect = debase["inspect"]
    hinges = iqr_hinges(wins=30, decided=40)
    _, wilson_lo, _ = wilson_interval(30, 40, z=1.96)
    assert inspect["p_working"] == pytest.approx(hinges["p_iqr1"])
    assert inspect["p_working_basis"] == P_WORKING_BASIS
    assert inspect["p_iqr1"] == pytest.approx(hinges["p_iqr1"])
    assert inspect["p_working"] < inspect["observed"]["win_rate"]
    assert inspect["p_working"] > wilson_lo
    assert hinges["z"] == pytest.approx(WILSON_Z_IQR1)
    assert inspect["p_be_roller"] == pytest.approx(2500.0 / 4500.0)
    assert inspect["gross_ev"] == pytest.approx(_ev(40, 30))
    assert inspect["risk_reward"] == pytest.approx(0.8)
    assert inspect["risk_reward_display"] == "0.80:1"
    assert inspect["valuation"]["R_w"] != pytest.approx(0.01)
    assert inspect["desk"]["break_even_probability"] == pytest.approx(base["inspect"]["desk"]["break_even_probability"])
    assert inspect["desk"]["p_used"] == pytest.approx(hinges["p_iqr1"])
    assert inspect["desk"]["trade_ev"] == pytest.approx(
        trade_ev(hinges["p_iqr1"], inspect["desk"]["R_w"], inspect["desk"]["R_l"])
    )
    assert inspect["desk"]["trade_ev"] < base["inspect"]["desk"]["trade_ev"]
    assert inspect["risk_profile"]["p_used"] == pytest.approx(hinges["p_iqr1"])
    assert inspect["capped_to_base"] is not None
    assert inspect["valuation"]["weekly_ev"] == pytest.approx(inspect["desk"]["weekly_ev"])


def test_debase_grade_cannot_exceed_base(tmp_path: Path, monkeypatch):
    _, base, debase = _run_pair(tmp_path, monkeypatch, name="Cap Grade", n=40, wins=30)
    base_letter = base["inspect"]["BASE_GRADE"]
    debase_letter = debase["inspect"]["DEBASE_GRADE"]
    assert letter_rank(debase_letter) <= letter_rank(base_letter)
    assert debase["inspect"]["BASE_GRADE"] == base_letter


def test_n20_vs_n500_different_debase_grade(tmp_path: Path, monkeypatch):
    _prep(tmp_path, monkeypatch)
    small = save_lab(name="Small D", payload=_payload(name="Small D", n=20, wins=15), folder="NBA", cfg=RollerConfig())
    large = save_lab(name="Large D", payload=_payload(name="Large D", n=500, wins=375), folder="NBA", cfg=RollerConfig())
    a = run_base(lab_id=small["lab_id"], cfg=RollerConfig(), monte_carlo_paths=80)
    b = run_base(lab_id=large["lab_id"], cfg=RollerConfig(), monte_carlo_paths=80)
    da = run_debase(result_id=a["result_id"], cfg=RollerConfig(), monte_carlo_paths=80)
    db = run_debase(result_id=b["result_id"], cfg=RollerConfig(), monte_carlo_paths=80)
    assert da["inspect"]["observed"]["win_rate"] == pytest.approx(0.75)
    assert db["inspect"]["observed"]["win_rate"] == pytest.approx(0.75)
    assert da["inspect"]["DEBASE_GRADE"] != db["inspect"]["DEBASE_GRADE"]
    assert da["inspect"]["components"]["robustness"] != db["inspect"]["components"]["robustness"]


def test_hash_mismatch_fail_closed(tmp_path: Path, monkeypatch):
    labs, phase_a, _ = _prep(tmp_path, monkeypatch)
    saved = save_lab(name="Hash Boom", payload=_payload(name="Hash Boom", n=20, wins=15), folder="NBA", cfg=RollerConfig())
    base = run_base(lab_id=saved["lab_id"], cfg=RollerConfig(), monte_carlo_paths=80)
    meta_path = phase_a / base["result_id"] / "metadata.json"
    rec = json.loads(meta_path.read_text(encoding="utf-8"))
    rec["source_csv_sha256"] = "0" * 64
    meta_path.write_text(json.dumps(rec), encoding="utf-8")
    with pytest.raises(SuperasiError) as ei:
        load_phase_a_folder(base["result_id"], cfg=RollerConfig())
    assert ei.value.code == "HASH_MISMATCH"
    assert labs.is_dir()


def test_missing_abase_fail_closed(tmp_path: Path, monkeypatch):
    _, phase_a, _ = _prep(tmp_path, monkeypatch)
    saved = save_lab(name="No Abase", payload=_payload(name="No Abase", n=20, wins=15), folder="NBA", cfg=RollerConfig())
    base = run_base(lab_id=saved["lab_id"], cfg=RollerConfig(), monte_carlo_paths=80)
    (phase_a / base["result_id"] / base["abase_filename"]).unlink()
    with pytest.raises(SuperasiError) as ei:
        run_debase(result_id=base["result_id"], cfg=RollerConfig(), monte_carlo_paths=80)
    assert ei.value.code == "PHASE_A_INCOMPLETE"


def test_ev_mismatch_fail_closed(tmp_path: Path, monkeypatch):
    _prep(tmp_path, monkeypatch)
    saved = save_lab(
        name="Bad EV",
        payload=_payload(name="Bad EV", n=20, wins=15, gross_ev=400.0),
        folder="NBA",
        cfg=RollerConfig(),
    )
    base = run_base(lab_id=saved["lab_id"], cfg=RollerConfig(), monte_carlo_paths=80)
    with pytest.raises(SuperasiError) as ei:
        run_debase(result_id=base["result_id"], cfg=RollerConfig(), monte_carlo_paths=80)
    assert ei.value.code == "EV_RECONCILE_FAILED"


def test_byte_identity_three_csvs(tmp_path: Path, monkeypatch):
    _, base, debase = _run_pair(tmp_path, monkeypatch, name="Three Files", n=24, wins=18)
    for which, key in (("debase", "debase_filename"), ("abase", "abase_filename"), ("roller", "roller_filename")):
        found = get_debase_csv_bytes(debase["result_id"], which=which)
        assert found is not None
        assert found[0] == debase[key]
        disk = tmp_path / "phase_b" / debase["result_id"] / found[0]
        assert found[1] == disk.read_bytes()
    debase_csv = get_debase_csv_bytes(debase["result_id"], which="debase")
    assert debase_csv is not None
    assert debase_csv[0] == "SuperasiBDeBase[Three Files].csv"
    parsed = list(csv.DictReader(io.StringIO(debase_csv[1].decode("utf-8"))))
    assert list(parsed[0].keys()) == list(SUPERASI_COLUMNS)
    grades = {row["metric"]: row["value"] for row in parsed if row["record_type"] == "degrading"}
    assert grades["DEBASE_GRADE"]
    assert any(row["metric"] == "BASE_GRADE" for row in parsed)
    assert any(row["metric"] == "p_be" and row["source"] == "roller_payoff" for row in parsed)
    assert any(row["metric"] == "question_sha256" for row in parsed)
    meta = json.loads((tmp_path / "phase_b" / debase["result_id"] / "metadata.json").read_text(encoding="utf-8"))
    assert meta["question_status"] == "PRESENT"
    assert meta["question"]["terminal"] == "BOTH"
    assert debase["inspect"]["question_status"] == "PRESENT"
    assert base["inspect"]["files"]["roller_filename"]


def test_health_lists_debase_capabilities():
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from fastapi.testclient import TestClient

    import terminal_api

    body = TestClient(terminal_api.app).get("/health").json()
    assert "superasi_debase_run" in body["capabilities"]
    assert "superasi_debase_results" in body["capabilities"]
    assert "superasi_base_run" in body["capabilities"]
    assert "warehouse_research_settings" in body["capabilities"]


def test_debase_stamps_and_uses_saved_desk_settings(tmp_path: Path, monkeypatch):
    _prep(tmp_path, monkeypatch)
    custom = {
        "schema_version": "desk_settings_v1.0.0",
        "bankroll_cents": 1_000_000,
        "allocation_bps": 1000,
        "updated_at": "",
        "source": "disk",
    }
    monkeypatch.setattr("roller.desk_settings.load_desk_settings", lambda **_kw: custom)
    saved = save_lab(
        name="Desk Ten",
        payload=_payload(name="Desk Ten", n=20, wins=15),
        folder="NBA",
        question=_payload(name="Desk Ten", n=20, wins=15)["question"],
        cfg=RollerConfig(),
    )
    assert saved["bankroll_cents"] == 1_000_000
    assert saved["allocation_bps"] == 1000
    base = run_base(lab_id=saved["lab_id"], cfg=RollerConfig(), monte_carlo_paths=80)
    assert base["bankroll_cents"] == 1_000_000
    debase = run_debase(result_id=base["result_id"], cfg=RollerConfig(), monte_carlo_paths=80)
    inspect = debase["inspect"]
    assert inspect["desk_settings"]["bankroll_dollars"] == pytest.approx(10_000.0)
    assert inspect["desk_settings"]["allocation_pct"] == pytest.approx(10.0)
    assert inspect["desk_settings"]["floor_dollars"] == pytest.approx(7_500.0)
    assert inspect["desk_settings"]["target_dollars"] == pytest.approx(15_000.0)
    assert inspect["valuation"]["R_w"] == pytest.approx(0.10 * (2000.0 / 6500.0))
    meta = json.loads((tmp_path / "phase_b" / debase["result_id"] / "metadata.json").read_text(encoding="utf-8"))
    assert meta["bankroll_cents"] == 1_000_000
    assert meta["allocation_bps"] == 1000


def _hold_yes_payload(*, name: str, held_yes: int, held_no: int, path_loss: int) -> dict:
    n = held_yes + held_no + path_loss
    rows = (
        [{"classification": "HELD_TO_SETTLEMENT", "settlement_status": "YES", "entry_value": 8000, "internal_game_id": f"hy{i}", "market_id": f"M{i}", "entry_timestamp": f"2025-10-10T00:{i:02d}:00Z"} for i in range(held_yes)]
        + [{"classification": "HELD_TO_SETTLEMENT", "settlement_status": "NO", "entry_value": 8000, "internal_game_id": f"hn{i}", "market_id": f"N{i}", "entry_timestamp": f"2025-10-11T00:{i:02d}:00Z"} for i in range(held_no)]
        + [{"classification": "LOSS", "settlement_status": "YES", "entry_value": 8000, "internal_game_id": f"pl{i}", "market_id": f"L{i}", "entry_timestamp": f"2025-10-12T00:{i:02d}:00Z"} for i in range(path_loss)]
    )
    w, l = held_yes, held_no + path_loss
    ev = (held_yes * 2000 - held_no * 8000 - path_loss * 4500) / n
    body = _payload(name=name, n=n, wins=w, gross_ev=ev)
    contract = body["results_contract"]
    contract["win_hold"] = True
    contract["entry"] = [{"op": "FIRST_TOUCH", "price_e4": 8000}]
    contract["win_exit"] = [{"id": "win_hold", "op": "HOLD", "outcome": "win"}]
    contract["loss_exit"] = [{"op": "REACH", "price_e4": 3500}]
    contract["classification"] = {"WIN": 0, "LOSS": path_loss, "HELD_TO_SETTLEMENT": held_yes + held_no}
    contract["statistics"] = {
        "population": n,
        "W": w,
        "L": l,
        "win_rate": w / n,
        "loss_rate": l / n,
        "reward_e4": 2000,
        "risk_e4": 4500,
        "rr": 2000 / 4500,
        "ev_e4": ev,
    }
    contract["audit_rows"] = rows
    return body


def test_debase_iqr1_is_generic_for_hold_yes_and_path_only(tmp_path: Path, monkeypatch):
    from roller.superasi.debase.iqr import iqr_hinges

    _prep(tmp_path, monkeypatch)
    hold = save_lab(
        name="Hold IQR",
        payload=_hold_yes_payload(name="Hold IQR", held_yes=8, held_no=1, path_loss=1),
        folder="NBA",
        cfg=RollerConfig(),
    )
    path = save_lab(
        name="Path IQR",
        payload=_payload(name="Path IQR", n=20, wins=13),
        folder="NBA",
        cfg=RollerConfig(),
    )
    a_hold = run_base(lab_id=hold["lab_id"], cfg=RollerConfig(), monte_carlo_paths=80)
    a_path = run_base(lab_id=path["lab_id"], cfg=RollerConfig(), monte_carlo_paths=80)
    assert a_hold["inspect"]["observed"]["wins"] == 8
    assert a_hold["inspect"]["observed"]["losses"] == 2
    b_hold = run_debase(result_id=a_hold["result_id"], cfg=RollerConfig(), monte_carlo_paths=80)
    b_path = run_debase(result_id=a_path["result_id"], cfg=RollerConfig(), monte_carlo_paths=80)
    hold_q1 = iqr_hinges(wins=8, decided=10)["p_iqr1"]
    path_q1 = iqr_hinges(wins=13, decided=20)["p_iqr1"]
    assert b_hold["inspect"]["p_working"] == pytest.approx(hold_q1)
    assert b_path["inspect"]["p_working"] == pytest.approx(path_q1)
    assert b_hold["inspect"]["desk"]["p_used"] == pytest.approx(hold_q1)
    assert b_path["inspect"]["desk"]["p_used"] == pytest.approx(path_q1)
    assert b_hold["inspect"]["desk"]["p_used"] != pytest.approx(b_hold["inspect"]["observed"]["win_rate"])
    assert b_path["inspect"]["desk"]["p_used"] != pytest.approx(b_path["inspect"]["observed"]["win_rate"])


def test_existing_debase_folder_not_rewritten_when_settings_change(tmp_path: Path, monkeypatch):
    _prep(tmp_path, monkeypatch)
    _, _, first = _run_pair(tmp_path, monkeypatch, name="Keep Old", n=20, wins=15)
    first_meta = json.loads((tmp_path / "phase_b" / first["result_id"] / "metadata.json").read_text(encoding="utf-8"))
    first_csv = (tmp_path / "phase_b" / first["result_id"] / first["debase_filename"]).read_bytes()
    custom = {
        "schema_version": "desk_settings_v1.0.0",
        "bankroll_cents": 5_000_000,
        "allocation_bps": 250,
        "updated_at": "",
        "source": "disk",
    }
    monkeypatch.setattr("roller.desk_settings.load_desk_settings", lambda **_kw: custom)
    later_meta = json.loads((tmp_path / "phase_b" / first["result_id"] / "metadata.json").read_text(encoding="utf-8"))
    later_csv = (tmp_path / "phase_b" / first["result_id"] / first["debase_filename"]).read_bytes()
    assert later_meta == first_meta
    assert later_csv == first_csv
    assert first_meta["bankroll_cents"] == 2_000_000
