"""Warehouse lab → SuperASI A → B handoff. Reuses existing results. Not ITI."""

from __future__ import annotations

from pathlib import Path

from roller.config import RollerConfig
from roller.desk_settings import default_settings
from roller.labs.store import save_lab
from roller.superasi.base.pipeline import run_base
from roller.superasi.debase.pipeline import run_debase
from roller.superasi.handoff import advance_lab_to_final, start_handoff
from roller.superasi.models import SuperasiError


def _payload(*, name: str, n: int = 20, wins: int = 15) -> dict:
    rows = []
    for i in range(n):
        klass = "WIN" if i < wins else "LOSS"
        rows.append(
            {
                "internal_game_id": f"g{i:04d}",
                "market_id": f"M{i:04d}",
                "entry_timestamp": f"2025-10-10T00:{i:02d}:00Z",
                "entry_value": 6500,
                "entry_operation": "CROSS",
                "classification": klass,
                "settlement_status": "YES" if klass == "WIN" else "NO",
                "settlement_value": 100 if klass == "WIN" else 0,
            }
        )
    wr = wins / n
    ev = (wins * 2000.0 - (n - wins) * 2500.0) / n
    return {
        "status": "READY",
        "question": {
            "universe": {
                "sports": ["ATP"],
                "leagues": ["ATP"],
                "seasons": ["2025-2026"],
                "date_from": "2025-07-01",
                "date_to": "2025-07-31",
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
            "classification": {"WIN": wins, "LOSS": n - wins},
            "statistics": {
                "population": n,
                "W": wins,
                "L": n - wins,
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
    monkeypatch.setattr("roller.labs.store.labs_root", lambda _cfg=None: tmp_path / "labs")
    monkeypatch.setattr("roller.superasi.base.store.phase_a_root", lambda _cfg=None: tmp_path / "phase_a")
    monkeypatch.setattr("roller.superasi.debase.store.phase_b_root", lambda _cfg=None: tmp_path / "phase_b")
    monkeypatch.setattr("roller.labs.store.LABS_RISK_PATHS", 80)
    monkeypatch.setattr("roller.desk_settings.load_desk_settings", lambda **_kw: default_settings())
    monkeypatch.setattr("roller.superasi.handoff.handoff_root", lambda _cfg=None: tmp_path / "handoff")


def test_handoff_missing_lab_fails_closed(tmp_path: Path, monkeypatch):
    _prep(tmp_path, monkeypatch)
    try:
        advance_lab_to_final("missing-lab", cfg=RollerConfig())
    except SuperasiError as exc:
        assert exc.code == "LAB_NOT_FOUND"
    else:
        raise AssertionError("expected LAB_NOT_FOUND")


def test_handoff_reuses_existing_final(tmp_path: Path, monkeypatch):
    _prep(tmp_path, monkeypatch)
    payload = _payload(name="ATP handoff reuse")
    saved = save_lab(
        name="ATP handoff reuse",
        payload=payload,
        folder="ATP",
        question=payload["question"],
        cfg=RollerConfig(),
    )
    base = run_base(lab_id=saved["lab_id"], cfg=RollerConfig(), monte_carlo_paths=80)
    debase = run_debase(result_id=base["result_id"], cfg=RollerConfig(), monte_carlo_paths=80)
    out = advance_lab_to_final(saved["lab_id"], cfg=RollerConfig(), monte_carlo_paths=80)
    assert out["reused_debase"] is True
    assert out["ran_base"] is False
    assert out["ran_debase"] is False
    assert out["result_id"] == debase["result_id"]
    assert out["inspect"]["source_lab_id"] == saved["lab_id"]


def test_handoff_runs_b_when_only_a_exists(tmp_path: Path, monkeypatch):
    _prep(tmp_path, monkeypatch)
    payload = _payload(name="ATP handoff B")
    saved = save_lab(
        name="ATP handoff B",
        payload=payload,
        folder="ATP",
        question=payload["question"],
        cfg=RollerConfig(),
    )
    base = run_base(lab_id=saved["lab_id"], cfg=RollerConfig(), monte_carlo_paths=80)
    out = advance_lab_to_final(saved["lab_id"], cfg=RollerConfig(), monte_carlo_paths=80)
    assert out["reused_base"] is True
    assert out["ran_base"] is False
    assert out["ran_debase"] is True
    assert out["phase_a_result_id"] == base["result_id"]
    assert out["result_id"]
    assert out["inspect"]["source_lab_id"] == saved["lab_id"]
    assert out["inspect"].get("DEBASE_GRADE")


def test_start_handoff_reuses_existing_final(tmp_path: Path, monkeypatch):
    _prep(tmp_path, monkeypatch)
    payload = _payload(name="ATP handoff start reuse")
    saved = save_lab(
        name="ATP handoff start reuse",
        payload=payload,
        folder="ATP",
        question=payload["question"],
        cfg=RollerConfig(),
    )
    base = run_base(lab_id=saved["lab_id"], cfg=RollerConfig(), monte_carlo_paths=80)
    debase = run_debase(result_id=base["result_id"], cfg=RollerConfig(), monte_carlo_paths=80)
    out = start_handoff(saved["lab_id"], cfg=RollerConfig(), background=True, monte_carlo_paths=80)
    assert out["status"] == "COMPLETE"
    assert out["reused_debase"] is True
    assert out["ran_base"] is False
    assert out["ran_debase"] is False
    assert out["result_id"] == debase["result_id"]
    assert out["handoff_id"] is None


def test_start_handoff_attaches_in_flight(tmp_path: Path, monkeypatch):
    import threading

    _prep(tmp_path, monkeypatch)
    payload = _payload(name="ATP handoff attach")
    saved = save_lab(
        name="ATP handoff attach",
        payload=payload,
        folder="ATP",
        question=payload["question"],
        cfg=RollerConfig(),
    )
    started = threading.Event()
    release = threading.Event()
    done = threading.Event()

    def blocker(lab_id, **_kwargs):
        started.set()
        try:
            release.wait(5)
            raise SuperasiError("HANDOFF_FAILED", f"stopped {lab_id}")
        finally:
            done.set()

    monkeypatch.setattr("roller.superasi.handoff.advance_lab_to_final", blocker)
    first = start_handoff(saved["lab_id"], cfg=RollerConfig(), background=True, monte_carlo_paths=80)
    assert started.wait(2)
    second = start_handoff(saved["lab_id"], cfg=RollerConfig(), background=True, monte_carlo_paths=80)
    assert first["handoff_id"]
    assert second["handoff_id"] == first["handoff_id"]
    release.set()
    assert done.wait(2)
