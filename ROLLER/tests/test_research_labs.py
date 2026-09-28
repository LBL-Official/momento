"""Labs CSV schema, determinism, and download byte identity."""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest

from roller.config import RollerConfig
from roller.labs.schema import CSV_COLUMNS, csv_filename, render_rows
from roller.labs.store import get_lab_csv_bytes, list_labs, rename_lab, save_lab


def _payload() -> dict:
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
            "population": 2,
            "classification": {"WIN": 1, "LOSS": 1},
            "statistics": {
                "population": 2,
                "W": 1,
                "L": 1,
                "win_rate": 0.5,
                "loss_rate": 0.5,
                "reward_e4": 2000,
                "risk_e4": 2500,
                "rr": 0.8,
                "ev_e4": -250.0,
            },
            "entry": [{"op": "CROSS", "price_e4": 6500}],
            "win_exit": [{"op": "REACH", "price_e4": 8500}],
            "loss_exit": [{"op": "REACH", "price_e4": 4000}],
            "audit_rows": [
                {
                    "internal_game_id": "g2",
                    "market_id": "M2",
                    "entry_timestamp": "2025-10-10T01:00:00Z",
                    "entry_value": 6500,
                    "entry_operation": "CROSS",
                    "classification": "LOSS",
                    "settlement_status": "NO",
                    "settlement_value": 0,
                },
                {
                    "internal_game_id": "g1",
                    "market_id": "M1",
                    "entry_timestamp": "2025-10-10T00:00:00Z",
                    "entry_value": 6500,
                    "entry_operation": "CROSS",
                    "classification": "WIN",
                    "settlement_status": "YES",
                    "settlement_value": 100,
                },
            ],
            "reproducibility": {
                "result_hash": "bb" * 32,
                "plan_hash": "aa" * 32,
                "execution_version": "1.0.0",
                "warehouse_version": "wh1",
            },
        },
        "result": {"result_hash": "bb" * 32, "engine_version": "1.0.0"},
    }


def _read_csv(raw: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))


def test_canonical_schema_and_sort(tmp_path: Path, monkeypatch):
    cfg = RollerConfig()
    monkeypatch.setattr("roller.labs.store.labs_root", lambda _cfg=None: tmp_path)
    assert len(CSV_COLUMNS) == len(set(CSV_COLUMNS))
    rows = render_rows("NBA Cross 65", _payload())
    trade = [r for r in rows if r["record_type"] == "row"]
    assert [r["internal_game_id"] for r in trade] == ["g1", "g2"]
    assert list(rows[0].keys()) == list(CSV_COLUMNS)
    assert trade[0]["strategy_name"] == "NBA Cross 65"
    assert trade[0]["win_rate"] == "0.500000"
    assert trade[0]["gross_ev"] == "-250.000000"
    first = save_lab(name="NBA Cross 65", payload=_payload(), folder="NBA", cfg=cfg)
    second = save_lab(name="NBA Cross 65", payload=_payload(), folder="NBA", cfg=cfg)
    a = get_lab_csv_bytes(first["lab_id"], cfg)
    b = get_lab_csv_bytes(second["lab_id"], cfg)
    assert a is not None and b is not None
    assert a[0] == csv_filename("NBA Cross 65")
    assert a[0] == "Roller[NBA Cross 65].csv"
    assert a[1] == b[1]
    assert first["csv_sha256"] == second["csv_sha256"]
    assert first["created_at"] != ""
    listed = list_labs(cfg)
    assert {i["lab_id"] for i in listed} == {first["lab_id"], second["lab_id"]}
    header = a[1].split(b"\n", 1)[0].decode("utf-8")
    assert header.split(",") == list(CSV_COLUMNS)
    parsed = _read_csv(a[1])
    kinds = {row["record_type"] for row in parsed}
    assert kinds == {"row", "risk", "weekly"}
    risk = next(row for row in parsed if row["record_type"] == "risk")
    weekly = [row for row in parsed if row["record_type"] == "weekly"]
    assert float(risk["break_even_probability"]) == pytest.approx(2.0 / 3.0)
    assert float(risk["trade_ev"]) == pytest.approx(0.001)
    assert float(risk["weekly_ev"]) == pytest.approx(0.01)
    assert float(risk["capital_per_trade"]) == pytest.approx(1000)
    assert risk["risk_mode"] == "A"
    assert risk["risk_seed"] == "20260913"
    assert risk["fees"] == "UNAVAILABLE"
    assert risk["slippage"] == "UNAVAILABLE"
    assert risk["fills"] == "UNAVAILABLE"
    assert risk["net_ev"] == "NOT_COMPUTABLE"
    assert risk["correlation_status"] == "CORRELATION_DATA_REQUIRED"
    assert risk["risk_not"] == "candle_path_not_fill"
    assert risk["static_weekly_sizing"] == "true"
    assert int(risk["monte_carlo_paths"]) == 100000
    assert risk["mc_bankroll_mean"] != ""
    assert risk["mc_bankroll_median"] != ""
    assert len(weekly) == 11
    assert [int(row["weekly_wins"]) for row in weekly] == list(range(11))
    trade_saved = [row for row in parsed if row["record_type"] == "row"]
    assert trade_saved[0]["risk_mode"] == ""
    assert trade_saved[0]["weekly_wins"] == ""


def test_rename_lab_keeps_identity(tmp_path: Path, monkeypatch):
    cfg = RollerConfig()
    monkeypatch.setattr("roller.labs.store.labs_root", lambda _cfg=None: tmp_path)
    saved = save_lab(name="913", payload=_payload(), folder="NBA", cfg=cfg)
    listed = list_labs(cfg)
    assert listed[0]["rows"] == 2
    assert listed[0]["header_population"] == 2
    assert listed[0]["population_matches_rows"] is True
    renamed = rename_lab(saved["lab_id"], "913-renamed", cfg=cfg)
    assert renamed is not None
    assert renamed["lab_id"] == saved["lab_id"]
    assert renamed["result_hash"] == saved["result_hash"]
    assert renamed["strategy_name"] == "913-renamed"
    assert renamed["filename"] == "Roller[913-renamed].csv"
    again = get_lab_csv_bytes(saved["lab_id"], cfg)
    assert again is not None
    assert again[0] == "Roller[913-renamed].csv"
    parsed = _read_csv(again[1])
    assert parsed[0]["strategy_name"] == "913-renamed"
