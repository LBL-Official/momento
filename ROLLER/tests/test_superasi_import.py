"""Server-authoritative import. Client preview is never N."""

from __future__ import annotations

import pytest

from roller.superasi.decompose import decompose
from roller.superasi.import_source import authoritative_trades, import_from_roller
from roller.superasi.library import load_package
from roller.superasi.models import SuperasiError


def test_refuses_truncated_preview():
    env = {
        "population": {
            "count": 290,
            "rows": [{"ticker": "x"}] * 200,
            "rows_truncated": True,
        }
    }
    with pytest.raises(SuperasiError) as ei:
        authoritative_trades(env)
    assert ei.value.code == "SOURCE_POPULATION_UNAVAILABLE"


def test_accepts_full_trades():
    trades = [{"ticker": f"T{i}"} for i in range(5)]
    got = authoritative_trades({"population": {"count": 5, "trades": trades, "rows": trades[:2]}})
    assert len(got) == 5


def test_empty_import_rejected(tmp_path):
    with pytest.raises(SuperasiError) as ei:
        import_from_roller({"research_spec": {"schema_version": "research_spec_v0"}}, root=tmp_path)
    assert ei.value.code in {"EMPTY_POPULATION", "SOURCE_POPULATION_UNAVAILABLE"}


def _row(i: int) -> dict:
    return {
        "ticker": f"T{i}",
        "internal_game_id": f"G{i}",
        "sport": "NBA",
        "slice": "Q3",
        "dataset_split": "OOS",
        "entry_close": 80,
        "path_true": True,
        "win_exit": True,
        "loss_exit": False,
        "terminal_yes": True,
        "price_basis": "YES_BID_CLOSE",
    }


def test_frozen_ignores_question(monkeypatch, tmp_path):
    calls = {"q": 0, "f": 0}

    def fake_q(_payload):
        calls["q"] += 1
        return {"execution_status": "COMPLETE", "population": {"count": 0, "trades": []}}

    def fake_f(_spec):
        calls["f"] += 1
        trades = [_row(i) for i in range(3)]
        return {
            "execution_status": "COMPLETE",
            "research_object_id": "FIRST80_Q3",
            "population": {"count": 3, "trades": trades},
            "provenance": {"path": "frozen_reference"},
        }

    monkeypatch.setattr("roller.superasi.import_source.execute_question", fake_q)
    monkeypatch.setattr("roller.superasi.import_source.execute_research_object", fake_f)
    out = import_from_roller(
        {
            "research_spec": {"definition_versions": {"FIRST80": "warehouse_frozen_v1"}},
            "research_object_id": "FIRST80_Q3",
            "question": {"universe": {}},
            "client_result": {
                "research_object_id": "FIRST80_Q3",
                "provenance": {"path": "frozen_reference"},
            },
        },
        root=tmp_path,
    )
    assert calls["f"] == 1
    assert calls["q"] == 0
    assert out["source"] == "roller_frozen"
    assert out["population_n"] == 3


def test_generic_non_importable_status(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "roller.superasi.import_source.execute_question",
        lambda _payload: {
            "execution_status": "READY_WITH_LIMITATIONS",
            "population": {"count": 0, "trades": []},
        },
    )
    with pytest.raises(SuperasiError) as ei:
        import_from_roller({"draft": {"universe": {}}}, root=tmp_path)
    assert ei.value.code == "SOURCE_POPULATION_UNAVAILABLE"


def test_roller_partition_not_stored_as_four_cell(monkeypatch, tmp_path):
    trades = [_row(i) for i in range(2)]
    monkeypatch.setattr(
        "roller.superasi.import_source.execute_question",
        lambda _payload: {
            "execution_status": "COMPLETE",
            "population": {"count": 2, "trades": trades},
            "empirical_partition": {
                "status": "COMPLETE",
                "cells": [
                    {"key": "T_AND_W", "n": 1},
                    {"key": "T_AND_NOT_W", "n": 1},
                ],
            },
        },
    )
    from roller.superasi.library import load_package

    out = import_from_roller({"draft": {"universe": {}}}, root=tmp_path)
    loaded = load_package(out["package_id"], root=tmp_path)
    assert "empirical_four_cell" not in loaded["package"]
    assert loaded["package"]["roller_handoff"]["empirical_partition"]["cells"][0]["key"] == "T_AND_W"


def test_fallback_executed_envelope_when_reexecute_data_required(monkeypatch, tmp_path):
    trades = [_row(i) for i in range(5)]
    monkeypatch.setattr(
        "roller.superasi.import_source.execute_question",
        lambda _payload: {
            "execution_status": "DATA_REQUIRED",
            "population": {"count": 0, "trades": []},
        },
    )
    out = import_from_roller(
        {
            "draft": {"universe": {}},
            "client_result": {
                "execution_status": "COMPLETE",
                "population": {
                    "count": 5,
                    "trades": trades,
                    "rows": trades[:2],
                    "rows_truncated": True,
                },
            },
        },
        root=tmp_path,
    )
    assert out["population_n"] == 5
    assert out["message"] == "MEASUREMENT IMPORTED"


def test_refuses_preview_rows_as_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "roller.superasi.import_source.execute_question",
        lambda _payload: {
            "execution_status": "DATA_REQUIRED",
            "population": {"count": 0, "trades": []},
        },
    )
    with pytest.raises(SuperasiError) as ei:
        import_from_roller(
            {
                "draft": {"universe": {}},
                "client_result": {
                    "execution_status": "COMPLETE",
                    "population": {
                        "count": 228,
                        "rows": [_row(i) for i in range(200)],
                        "rows_truncated": True,
                    },
                },
            },
            root=tmp_path,
        )
    assert ei.value.code == "SOURCE_POPULATION_UNAVAILABLE"


def test_generic_import_n_matches_count(monkeypatch, tmp_path):
    trades = [_row(i) for i in range(7)]
    monkeypatch.setattr(
        "roller.superasi.import_source.execute_question",
        lambda payload: {
            "execution_status": "COMPLETE",
            "population": {"count": 7, "trades": trades, "rows": trades[:2], "rows_truncated": True},
        },
    )
    out = import_from_roller({"draft": {"universe": "generic"}}, root=tmp_path)
    assert out["population_n"] == 7
    assert out["source"] == "roller_generic"
    assert out["message"] == "MEASUREMENT IMPORTED"


def test_generic_full_envelope_skips_rescan(monkeypatch, tmp_path):
    calls = {"q": 0}
    trades = [_row(i) for i in range(4)]

    def fake_q(_payload):
        calls["q"] += 1
        raise AssertionError("generic import must not rescan when full trades are present")

    monkeypatch.setattr("roller.superasi.import_source.execute_question", fake_q)
    out = import_from_roller(
        {
            "draft": {"universe": {}},
            "client_result": {
                "execution_status": "COMPLETE",
                "population": {"count": 4, "trades": trades, "rows": trades[:2], "rows_truncated": True},
            },
        },
        root=tmp_path,
    )
    assert calls["q"] == 0
    assert out["population_n"] == 4
    assert out["message"] == "MEASUREMENT IMPORTED"


def test_count_mismatch_fails_import():
    with pytest.raises(SuperasiError) as ei:
        authoritative_trades(
            {"population": {"count": 4, "trades": [_row(0), _row(1)]}}
        )
    assert ei.value.code == "POPULATION_COUNT_MISMATCH"


def test_import_stores_question_hash_from_envelope(tmp_path):
    trades = [_row(i) for i in range(3)]
    trades.append(
        {
            **_row(3),
            "path_true": False,
            "win_exit": False,
            "loss_exit": True,
            "terminal_yes": False,
            "T40": True,
        }
    )
    hashes = {
        "question_hash": "qh-envelope-aaa",
        "state_hash": "st-1",
        "entry_hash": "en-1",
    }
    out = import_from_roller(
        {
            "draft": {"universe": {}},
            "spec_fingerprint": "fp_ui_only",
            "compile_fingerprint": "fp_ui_only",
            "hashes": hashes,
            "dataset_version": "ds-v1",
            "client_result": {
                "execution_status": "COMPLETE",
                "population": {"count": 4, "trades": trades},
                "hashes": hashes,
                "dataset_version": "ds-v1",
            },
        },
        root=tmp_path,
    )
    assert out["question_hash"] == "qh-envelope-aaa"
    assert out["dataset_version"] == "ds-v1"
    assert out["trade_origin"] == "executed_envelope"
    loaded = load_package(out["package_id"], root=tmp_path)
    pkg = loaded["package"]
    assert pkg["question_hash"] == "qh-envelope-aaa"
    assert pkg["hashes"]["question_hash"] == "qh-envelope-aaa"
    assert pkg["hashes"]["state_hash"] == "st-1"
    assert pkg["dataset_version"] == "ds-v1"
    assert pkg["spec_fingerprint"] == "fp_ui_only"
    assert pkg["compile_fingerprint"] == "fp_ui_only"
    assert pkg["roller_handoff"]["hashes"]["question_hash"] == "qh-envelope-aaa"
    decomp = decompose(out["package_id"], root=tmp_path)
    assert decomp["question_hash"] == "qh-envelope-aaa"
    assert decomp["dataset_version"] == "ds-v1"
    assert decomp["checksums"]["trades"] == pkg["checksums"]["trades"]


def test_reexecute_hash_mismatch_refused(monkeypatch, tmp_path):
    trades = [_row(i) for i in range(2)]

    def fake_q(_payload):
        return {
            "execution_status": "COMPLETE",
            "population": {"count": 2, "trades": trades},
            "hashes": {"question_hash": "qh-reexec-bbb"},
        }

    monkeypatch.setattr("roller.superasi.import_source.execute_question", fake_q)
    with pytest.raises(SuperasiError) as ei:
        import_from_roller(
            {
                "draft": {"universe": {}},
                "hashes": {"question_hash": "qh-client-aaa"},
                "client_result": {
                    "execution_status": "COMPLETE",
                    "hashes": {"question_hash": "qh-client-aaa"},
                    "population": {
                        "count": 2,
                        "rows": trades,
                        "rows_truncated": True,
                    },
                },
            },
            root=tmp_path,
        )
    assert ei.value.code == "QUESTION_HASH_MISMATCH"
