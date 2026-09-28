"""Paired 80/40 vs 80/65 replay on the derived four. Research only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from roller.choosin_texas.api import handle_health, handle_paired_replay
from roller.choosin_texas.models import ChoosinTexasError
from datetime import datetime

from roller.choosin_texas.paired_replay import (
    CONFIGS,
    NY,
    build_paired_replay,
    decide_capital_entry,
    load_rows,
    loss_severity,
    reconstruct_occupancy,
    replay,
    replay_capital_6pct,
    touches_json_path,
    write_planned_risk_audit,
)


REPO = Path(__file__).resolve().parents[2]
FRONTEND_APP = REPO / "frontend" / "choosin-texas" / "src" / "App.tsx"
FRONTEND_PAIRED = REPO / "frontend" / "choosin-texas" / "src" / "Paired.tsx"


def _survivor(ticker: str = "ONLY") -> dict:
    return {
        "ticker": ticker,
        "event_id": ticker,
        "entry_ts": 1,
        "ledger_exit_ts": 50,
        "ledger_exit_kind": "SETTLEMENT_YES",
        "t40_ts": None,
        "t40_close": None,
        "t65_ts": None,
        "t65_close": None,
    }


def _stop40(index: int, close: int, *, entry: int, exit_ts: int) -> dict:
    return {
        "ticker": f"T{index}",
        "event_id": f"E{index}",
        "entry_ts": entry,
        "ledger_exit_ts": exit_ts,
        "ledger_exit_kind": "T40_CLOSE",
        "t40_ts": exit_ts,
        "t40_close": close,
        "t65_ts": None,
        "t65_close": None,
    }


def test_unit_books_clock_and_live_stay_closed():
    body = build_paired_replay()
    assert body["status"] == "OBSERVED"
    assert body["live_execution"] is False
    assert body["submits"] is False
    assert body["live_authorized"] is False
    assert body["primary_research_candidate"] == "80/40"
    assert body["label"] == "CANDLE_PATH_NOT_FILL"
    assert body["n"] == 936
    assert body["fees"] == "UNAVAILABLE"
    assert body["unit_book"]["80/40"]["through_close_book_cents"] == 3297
    assert body["unit_book"]["80/40"]["stops"] == 236
    assert body["unit_book"]["80/65"]["through_close_book_cents"] == 2410
    assert body["unit_book"]["80/65"]["stops"] == 421
    assert body["clock"]["t65_stops_ledger_settlement_yes"] == 185
    assert body["clock"]["those_marked_at_settlement"] == 0
    by_key = {(run["book"], run["configuration_id"], run["sizing"]): run for run in body["runs"]}
    cap4 = by_key[("80/40", "cap_4", "flat_stop")]
    no_cap = by_key[("80/40", "no_count_cap", "flat_stop")]
    assert cap4["through_close_pnl_cents"] == no_cap["through_close_pnl_cents"]
    assert cap4["skips"]["POSITION_CAP"] > 0
    assert no_cap["skips"]["POSITION_CAP"] == 0
    assert no_cap["skips"]["SKIP_RISK_BUDGET"] == cap4["skips"]["POSITION_CAP"]
    wide = by_key[("80/65", "cap_1", "flat_stop")]
    assert wide["resized_cash_n"] == 9
    assert wide["skips"]["SKIP_CASH"] == 0
    assert wide["skips"]["SKIP_RISK_BUDGET"] == 0
    assert "drawdown" not in cap4
    assert "max_drawdown" not in cap4
    assert cap4["flat_stop_stress_proxy"]["name"] == "flat_stop_stress_proxy"
    assert "marked-to-market" in cap4["flat_stop_stress_proxy"]["meaning"]
    assert cap4["realized_pnl_path"]["name"] == "realized_through_close_pnl"


def test_empty_book_uses_the_fixed_allocation():
    row = [_survivor()]
    assert replay(row, "80/40", CONFIGS[0], sizing="flat_stop")["contracts_taken"] == 3000
    assert replay(row, "80/40", CONFIGS[1], sizing="flat_stop")["contracts_taken"] == 750
    assert replay(row, "80/40", CONFIGS[2], sizing="flat_stop")["contracts_taken"] == 750
    assert replay(row, "80/65", CONFIGS[0], sizing="flat_stop")["contracts_taken"] == 8000
    assert replay(row, "80/65", CONFIGS[1], sizing="flat_stop")["contracts_taken"] == 2000
    assert replay(row, "80/65", CONFIGS[2], sizing="flat_stop")["contracts_taken"] == 2000
    assert replay(row, "80/40", CONFIGS[0], sizing="in_sample_average_gap")["contracts_taken"] == 2645
    assert replay(row, "80/40", CONFIGS[1], sizing="in_sample_average_gap")["contracts_taken"] == 661
    assert replay(row, "80/65", CONFIGS[0], sizing="in_sample_average_gap")["contracts_taken"] == 6403
    assert replay(row, "80/65", CONFIGS[1], sizing="in_sample_average_gap")["contracts_taken"] == 1600
    cheap = [_stop40(0, 79, entry=1, exit_ts=2)]
    dear = [_stop40(0, 1, entry=1, exit_ts=2)]
    assert replay(cheap, "80/40", CONFIGS[1], sizing="flat_stop")["contracts_taken"] == replay(
        dear, "80/40", CONFIGS[1], sizing="flat_stop"
    )["contracts_taken"]


def test_cash_shortfall_is_not_a_risk_skip():
    rows = [_stop40(i, 0, entry=i * 10, exit_ts=i * 10 + 1) for i in range(10)]
    result = replay(rows, "80/40", CONFIGS[0], sizing="flat_stop")
    assert result["resized_cash_n"] == 1
    assert result["resized_cash"][0]["contracts_requested"] == 3000
    assert result["resized_cash"][0]["contracts_taken"] == 1000
    assert result["resized_cash"][0]["premium_cut_cents"] == 160_000
    assert result["skips"]["SKIP_CASH"] == 1
    assert result["skips"]["SKIP_RISK_BUDGET"] == 0
    overlap = [_stop40(i, 40, entry=1, exit_ts=100) for i in range(5)]
    capped = replay(overlap, "80/40", CONFIGS[1], sizing="flat_stop")
    open_count = replay(overlap, "80/40", CONFIGS[2], sizing="flat_stop")
    assert capped["skips"]["POSITION_CAP"] == 1
    assert capped["skips"]["SKIP_RISK_BUDGET"] == 0
    assert capped["skips"]["SKIP_CASH"] == 0
    assert open_count["skips"]["POSITION_CAP"] == 0
    assert open_count["skips"]["SKIP_RISK_BUDGET"] == 1
    assert open_count["skips"]["SKIP_CASH"] == 0
    assert open_count["entries_taken"] == 4


def test_missing_timestamp_and_drift_fail(tmp_path: Path):
    doc = json.loads(touches_json_path().read_text(encoding="utf-8"))
    broken = tmp_path / "touches.json"
    for row in doc["rows"]:
        if row.get("t65_ts") is not None:
            row["t65_ts"] = None
            break
    broken.write_text(json.dumps(doc))
    with pytest.raises(ChoosinTexasError) as missing:
        load_rows(touch_json_path=broken)
    assert missing.value.code == "DATA_REQUIRED"

    doc = json.loads(touches_json_path().read_text(encoding="utf-8"))
    for row in doc["rows"]:
        if row.get("t65_close") is not None:
            row["post_min"] = 99
            break
    drifted = tmp_path / "drift.json"
    drifted.write_text(json.dumps(doc))
    with pytest.raises(ChoosinTexasError) as mismatch:
        load_rows(touch_json_path=drifted)
    assert mismatch.value.code == "LOCK_MISMATCH"


def test_handle_and_terminal_api_paired_replay():
    health = handle_health()
    assert "choosin_texas_paired_replay" in health["capabilities"]
    body = handle_paired_replay()
    assert body["page"] == "paired_replay"
    assert body["unit_book"]["80/40"]["through_close_book_cents"] == 3297

    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    client = TestClient(terminal_api.app)
    desk = client.get("/health").json()
    assert "choosin_texas_paired_replay" in desk["capabilities"]
    res = client.get("/choosin-texas/paired-replay")
    assert res.status_code == 200
    payload = res.json()
    assert payload["live_authorized"] is False
    assert payload["unit_book"]["80/65"]["through_close_book_cents"] == 2410


def _ts(year: int, month: int, day: int, hour: int, minute: int = 0, second: int = 0) -> int:
    return int(datetime(year, month, day, hour, minute, second, tzinfo=NY).timestamp())


def _surv(index: int, entry: int, exit_ts: int, *, ticker: str | None = None) -> dict:
    name = ticker or f"T{index:02d}"
    return {
        "ticker": name,
        "event_id": name,
        "entry_ts": entry,
        "ledger_exit_ts": exit_ts,
        "ledger_exit_kind": "SETTLEMENT_YES",
        "t40_ts": None,
        "t40_close": None,
        "t65_ts": None,
        "t65_close": None,
    }


def _wipe(index: int, entry: int, exit_ts: int, close: int = 0) -> dict:
    return _stop40(index, close, entry=entry, exit_ts=exit_ts)


def test_capital_policy_on_the_locked_936():
    body = build_paired_replay()
    assert body["unit_book"]["80/40"]["through_close_book_cents"] == 3297
    assert body["unit_book"]["80/40"]["stops"] == 236
    assert body["unit_book"]["80/65"]["stops"] == 421
    assert all(run.get("sizing_label") == "IN_SAMPLE" for run in body["runs"] if run["sizing"] == "in_sample_average_gap")
    assert all("sizing_label" not in run for run in body["runs"] if run["sizing"] == "flat_stop")
    policy = body["capital_policy"]
    assert policy["id"] == "CAPITAL_6PCT_CAP3"
    assert policy["october_3_arms_either_book"] is False
    assert policy["session_timezone"] == "America/New_York"
    assert policy["notices"]["FEES_UNAVAILABLE"] == "FEES_UNAVAILABLE"
    assert policy["notices"]["forecast"] == "Historical chronological replay; not a forecast."
    assert policy["accepted_both"] == 814
    assert policy["accepted_only_80_40"] == 6
    assert policy["accepted_only_80_65"] == 51
    book40 = policy["books"]["80/40"]
    book65 = policy["books"]["80/65"]
    assert book40["candidates"] == 936
    assert book65["candidates"] == 936
    assert book40["accepted"] == 820
    assert book65["accepted"] == 865
    assert book40["through_close_pnl_cents"] == 11_164_842
    assert book65["through_close_pnl_cents"] == 8_119_467
    assert book40["ending_cash_cents"] == 2_000_000 + book40["through_close_pnl_cents"]
    assert book65["ending_cash_cents"] == 2_000_000 + book65["through_close_pnl_cents"]
    assert book40["planned_flat_loss_per_full_position_cents"] == 60_000
    assert book65["planned_flat_loss_per_full_position_cents"] == 22_500
    assert book40["initial_full_position_contracts"] == 1500
    for book in (book40, book65):
        first = next(row for row in book["decisions"] if row["accepted_contracts"] > 0)
        assert first["accepted_contracts"] == 1500
        assert book["realized_capital"]["name"] == "realized_capital"
        assert book["realized_capital_max_drawdown"]["name"] == "realized_capital_max_drawdown"
        assert book["flat_stop_stress_proxy"]["name"] == "flat_stop_stress_proxy"
        assert "Open P&L is omitted" in book["realized_capital"]["meaning"]
        assert "mark-to-market" in book["realized_capital_max_drawdown"]["meaning"]
    settlement = [
        row
        for row in book65["decisions"]
        if row["stopped"] and row["ledger_exit_kind"] == "SETTLEMENT_YES"
    ]
    assert len(settlement) == 185
    assert all(row["exit_ts"] != row["ledger_exit_ts"] for row in settlement)


def test_capital_session_basis_and_gates():
    day1 = _ts(2026, 1, 15, 15)
    rows = [
        _surv(0, day1, _ts(2026, 1, 15, 18)),
        _surv(1, _ts(2026, 1, 15, 20), _ts(2026, 1, 17, 15)),
        _surv(2, _ts(2026, 1, 16, 15), _ts(2026, 1, 16, 18)),
    ]
    sized = replay_capital_6pct(rows, "80/40")
    by_ticker = {row["ticker"]: row for row in sized["decisions"]}
    assert by_ticker["T00"]["accepted_contracts"] == 1500
    assert by_ticker["T01"]["accepted_contracts"] == 1500
    assert by_ticker["T02"]["accepted_contracts"] == 1522
    day2 = next(row for row in sized["sessions"] if row["date"] == "2026-01-16")
    assert day2["carried_positions"] == 1
    assert day2["carried_positions_priced_at_entry_cost"] is True
    assert day2["open_entry_premium_at_freeze_cents"] == 120_000
    assert day2["session_basis_cents"] == 2_030_000

    midnight = replay_capital_6pct(
        [
            _surv(0, day1, _ts(2026, 1, 16, 0, 0, 0)),
            _surv(1, _ts(2026, 1, 16, 15), _ts(2026, 1, 16, 18)),
        ],
        "80/40",
    )
    assert [row["accepted_contracts"] for row in midnight["decisions"]] == [1500, 1522]

    four = [
        _wipe(i, day1 + i, day1 + 3600, 40)
        for i in range(4)
    ]
    capped = replay_capital_6pct(four, "80/40")
    assert [row["accepted_contracts"] for row in capped["decisions"][:3]] == [1500, 1500, 1500]
    assert capped["decisions"][3]["reason"] == "POSITION_CAP"
    assert capped["max_open_entry_premium_cents"] == 360_000

    held = _surv(0, day1, _ts(2026, 1, 20, 15), ticker="HELD")
    wipes = [_wipe(i + 1, day1 + 60 * (i + 1), day1 + 60 * (i + 1) + 30) for i in range(12)]
    blocked = _surv(20, _ts(2026, 1, 16, 15), _ts(2026, 1, 16, 18), ticker="BLOCK")
    reduced = replay_capital_6pct([held, *wipes, blocked], "80/40")
    assert reduced["decisions"][-1]["reason"] == "SKIP_CAPITAL_BUDGET"
    assert reduced["decisions"][-1]["ticker"] == "BLOCK"
    carried = next(row for row in reduced["sessions"] if row["date"] == "2026-01-16")
    assert carried["carried_over_cap"] is True
    assert carried["carried_positions"] == 1
    assert reduced["ending_cash_cents"] == 2_000_000 + reduced["through_close_pnl_cents"]

    burn = [_wipe(i, day1 + 60 * i, day1 + 60 * i + 30) for i in range(16)]
    burn.append(_wipe(16, day1 + 60 * 16, day1 + 60 * 16 + 30))
    cash_resize = replay_capital_6pct(burn, "80/40")
    last = cash_resize["decisions"][-1]
    assert last["reason"] == "RESIZED_CASH"
    assert last["requested_contracts"] == 1500
    assert last["accepted_contracts"] == 1000
    assert cash_resize["reasons"]["SKIP_CAPITAL_BUDGET"] == 0

    partial_wipes = [_wipe(i + 1, day1 + 60 * (i + 1), day1 + 60 * (i + 1) + 30) for i in range(9)]
    partial = replay_capital_6pct(
        [held, *partial_wipes, _surv(21, _ts(2026, 1, 16, 16), _ts(2026, 1, 16, 18), ticker="PART")],
        "80/40",
    )
    assert partial["decisions"][-1]["reason"] == "RESIZED_CAPITAL_BUDGET"
    assert partial["decisions"][-1]["constraint_tie"] is False
    tie = decide_capital_entry(
        same_event=False,
        open_count=1,
        per_position_cap_cents=120_000,
        portfolio_premium_cap_cents=360_000,
        open_premium_cents=352_000,
        cash_cents=8_000,
    )
    assert tie["reason"] == "RESIZED_CAPITAL_BUDGET"
    assert tie["constraint_tie"] is True
    assert tie["accepted_contracts"] == 100
    cash_only = decide_capital_entry(
        same_event=False,
        open_count=1,
        per_position_cap_cents=120_000,
        portfolio_premium_cap_cents=360_000,
        open_premium_cents=0,
        cash_cents=4_000,
    )
    assert cash_only["reason"] == "RESIZED_CASH"
    assert cash_only["constraint_tie"] is False


def test_capital_clock_order_and_close_do_not_size():
    entry = _ts(2026, 1, 15, 15)
    stop_ts = _ts(2026, 1, 15, 16)
    settle = _ts(2026, 1, 15, 22)
    later = _ts(2026, 1, 15, 17)
    yes_stop = {
        "ticker": "YES",
        "event_id": "YES",
        "entry_ts": entry,
        "ledger_exit_ts": settle,
        "ledger_exit_kind": "SETTLEMENT_YES",
        "t40_ts": None,
        "t40_close": None,
        "t65_ts": stop_ts,
        "t65_close": 50,
    }
    follower = _surv(1, later, _ts(2026, 1, 15, 21), ticker="NEXT")
    booked = replay_capital_6pct([yes_stop, follower], "80/65")
    jump = next(ts for ts, capital in zip(booked["realized_capital"]["path_ts"], booked["realized_capital"]["path_cents"]) if capital != 2_000_000)
    assert jump == stop_ts
    assert booked["decisions"][1]["reason"] == "ADMITTED"

    cheap = replay_capital_6pct([_wipe(0, entry, stop_ts, 79)], "80/40")
    dear = replay_capital_6pct([_wipe(0, entry, stop_ts, 1)], "80/40")
    assert cheap["contracts_taken"] == dear["contracts_taken"] == 1500
    assert cheap["through_close_pnl_cents"] != dear["through_close_pnl_cents"]

    slot = entry
    exit_at = _ts(2026, 1, 15, 18)
    held = [_wipe(i, slot + i, _ts(2026, 1, 15, 20), 40) for i in range(2)]
    freeing = _wipe(2, slot + 2, exit_at, 40)
    arriving = _wipe(3, exit_at, _ts(2026, 1, 15, 21), 40)
    ordered = replay_capital_6pct([*held, freeing, arriving], "80/40")
    assert ordered["decisions"][-1]["reason"] == "ADMITTED"
    assert ordered["max_concurrent"] == 3


def test_frontend_paired_does_not_compute_rates():
    app = FRONTEND_APP.read_text(encoding="utf-8")
    assert "#/paired" in app
    page = FRONTEND_PAIRED.read_text(encoding="utf-8")
    assert "fetchPairedReplay" in page
    assert "flat_stop_stress_proxy" in page
    assert "SKIP_CASH" in page
    assert "SKIP_RISK_BUDGET" in page
    assert "* 100" not in page
    assert "/ n" not in page
    assert "*" not in page
    assert "6% deployed" in page
    assert "realized_capital_max_drawdown" in page
    assert "flat_stop_stress_proxy" in page
    assert "SKIP_CAPITAL_BUDGET" in page
    assert "planned_risk_policy" in page
    assert "realized_loss_cap" in page


def test_planned_risk_sizes_and_keeps_the_gap():
    day = _ts(2026, 1, 15, 15)
    later = _ts(2026, 1, 15, 18)
    nxt = _ts(2026, 1, 16, 15)
    first = replay_capital_6pct([_surv(0, day, later)], "80/40", mode="planned_risk")
    sixty = replay_capital_6pct([_surv(0, day, later)], "80/65", mode="planned_risk")
    assert first["decisions"][0]["accepted_contracts"] == 1000
    assert first["decisions"][0]["reason"] == "ADMITTED"
    assert first["decisions"][0]["planned_loss_cents"] == 40_000
    assert sixty["decisions"][0]["accepted_contracts"] == 1500
    assert sixty["planned_flat_loss_per_full_position_cents"] == 22_500
    assert first["realized_loss_cap"] == "NOT_ESTABLISHED"

    four = replay_capital_6pct(
        [_wipe(i, day + i, later, 40) for i in range(4)],
        "80/40",
        mode="planned_risk",
    )
    assert [row["reason"] for row in four["decisions"]][-1] == "POSITION_CAP"
    assert four["through_close_pnl_cents"] == -120_000
    assert four["ending_cash_cents"] == 2_000_000 - 120_000

    same = replay_capital_6pct(
        [
            _surv(0, day, later),
            _surv(1, later + 60, nxt),
            _surv(2, nxt, nxt + 3600),
        ],
        "80/40",
        mode="planned_risk",
    )
    assert [row["accepted_contracts"] for row in same["decisions"]] == [1000, 1000, 1010]

    gap = replay_capital_6pct([_wipe(0, day, later, 0)], "80/40", mode="planned_risk")
    other = replay_capital_6pct([_wipe(0, day, later, 39)], "80/40", mode="planned_risk")
    assert gap["decisions"][0]["accepted_contracts"] == other["decisions"][0]["accepted_contracts"] == 1000
    assert gap["through_close_pnl_cents"] == -80_000
    assert gap["loss_breaches"][0]["excess_cents"] == 40_000
    assert gap["ending_cash_cents"] == 2_000_000 + gap["through_close_pnl_cents"]
    assert other["through_close_pnl_cents"] == -41_000

    cursor = _ts(2026, 1, 15, 8)
    cash_rows = []
    for index in range(23):
        cash_rows.append(_wipe(index, cursor, cursor + 30, 0))
        cursor += 60
    cash_rows.append(_wipe(23, cursor, cursor + 30, 1))
    cursor += 60
    cash_rows.append(_wipe(24, cursor, cursor + 30, 0))
    cursor += 60
    cash_rows.append(_wipe(25, cursor, cursor + 30, 40))
    cash_book = replay_capital_6pct(cash_rows, "80/40", mode="planned_risk")
    last = cash_book["decisions"][-1]
    assert last["reason"] == "RESIZED_CASH"
    assert last["requested_contracts"] == 1000
    assert last["accepted_contracts"] == 12

    morning = _ts(2026, 1, 15, 10)
    held = _wipe(0, morning, _ts(2026, 1, 16, 20), 0)
    cursor = morning + 120
    carried = [held]
    for index in range(1, 19):
        carried.append(_wipe(index, cursor, cursor + 30, 0))
        cursor += 60
    probe = _wipe(90, _ts(2026, 1, 16, 12), _ts(2026, 1, 16, 18), 40)
    carried.append(probe)
    shrunk = replay_capital_6pct(carried, "80/40", mode="planned_risk")
    assert shrunk["decisions"][-1]["reason"] == "RESIZED_CAPITAL_BUDGET"
    assert shrunk["decisions"][-1]["constraint_tie"] is False


def test_planned_risk_on_the_locked_936():
    body = build_paired_replay()
    capital = body["capital_policy"]
    assert capital["books"]["80/40"]["through_close_pnl_cents"] == 11_164_842
    assert capital["books"]["80/40"]["accepted"] == 820
    assert capital["books"]["80/65"]["through_close_pnl_cents"] == 8_119_467
    planned = body["planned_risk_policy"]
    assert planned["id"] == "PLANNED_RISK_CAP3"
    assert planned["realized_loss_cap"] == "NOT_ESTABLISHED"
    assert planned["live_authorized"] is False
    assert planned["accepted_both"] == 814
    assert planned["accepted_only_80_40"] == 6
    assert planned["accepted_only_80_65"] == 51
    book40 = planned["books"]["80/40"]
    book65 = planned["books"]["80/65"]
    assert book40["initial_full_position_contracts"] == 1000
    assert book65["initial_full_position_contracts"] == 1500
    assert book40["through_close_pnl_cents"] == 5_335_376
    assert book40["ending_cash_cents"] == 7_335_376
    assert book40["loss_breach_summary"]["count"] == 168
    assert book65["through_close_pnl_cents"] == 8_119_467
    assert book65["ending_cash_cents"] == 10_119_467
    assert book65["loss_breach_summary"]["count"] == 283
    assert book65["loss_breaches"] == []
    assert book40["max_planned_stop_risk_of_basis_pct_display"] == "2.0000%"
    assert book65["max_planned_stop_risk_of_basis_pct_display"] == "1.1250%"
    assert planned["prior_result_status"] == "CONFIRMED"
    assert planned["configuration"]["reconstructed_max_concurrent_80_40"] == 3
    assert planned["configuration"]["reconstructed_max_concurrent_80_65"] == 3
    assert book40["loss_severity"]["largest_dollar_and_percent_same_event"] is False
    assert book40["turnover"]["candidates_by_open_count_before"]["4_or_more"] == 0
    assert book40["turnover"]["blocked_example"]["blocking_event_ids_display"]
    steps65 = book65["turnover"]["freed_example"]["steps"]
    assert [step["event_id"] for step in steps65] == [
        "KXNBAGAME-25OCT22CLENYK",
        "KXNBAGAME-25OCT22MIAORL",
        "KXNBAGAME-25OCT22DETCHI",
    ]
    assert [step["open_count"] for step in steps65] == [2, 1, 2]
    for previous, step in zip(steps65, steps65[1:]):
        assert step["open_count_before"] == previous["open_count"]
    assert "KXNBAGAME-25OCT22DETCHI" in book65["turnover"]["blocked_example"]["relation_to_freed_window"]
    assert book65["turnover"]["blocked_example"]["entry_ts_display"].startswith("2025-10-22 21:28:00")
    prior_planned = json.loads((REPO / "research" / "choosin_texas" / "paired_replay" / "prior" / "planned_risk_cap3.json").read_text())
    prior_capital = json.loads((REPO / "research" / "choosin_texas" / "paired_replay" / "prior" / "capital_6pct_cap3.json").read_text())
    assert prior_planned["policy_id"] == "PLANNED_RISK_CAP3"
    assert "11164842" not in json.dumps(prior_planned)
    assert prior_planned["planned_risk_policy"]["books"]["80/40"]["through_close_pnl_cents"] == 5_335_376
    assert prior_capital["policy_id"] == "CAPITAL_6PCT_CAP3"
    assert prior_capital["capital_policy"]["books"]["80/40"]["through_close_pnl_cents"] == 11_164_842
    caps = {(row["book"], row["max_open_positions"]): row for row in planned["diagnostics"]}
    assert caps[("80/40", 1)]["initial_full_position_contracts"] == 1000
    assert caps[("80/65", 2)]["initial_full_position_contracts"] == 1500
    assert caps[("80/40", 1)]["reconstructed_max_concurrent"] == 1
    assert caps[("80/65", 2)]["reconstructed_max_concurrent"] == 2
    audit = write_planned_risk_audit(load_rows())
    assert (audit / "manifest.json").is_file()
    assert (audit / "80_40" / "open_3" / "positions.json").is_file()


def test_position_cap_is_global_and_immediate():
    day = _ts(2026, 1, 15, 15)
    later = _ts(2026, 1, 15, 20)
    four = [
        _wipe(0, day, later, 40) | {"ticker": "A", "event_id": "A", "sport": "NBA", "slice": "Q2"},
        _wipe(1, day, later, 40) | {"ticker": "B", "event_id": "B", "sport": "NBA", "slice": "Q3"},
        _wipe(2, day, later, 40) | {"ticker": "C", "event_id": "C", "sport": "NCAAB", "slice": "H1_2"},
        _wipe(3, day, later, 40) | {"ticker": "D", "event_id": "D", "sport": "NCAAB", "slice": "H2_1"},
    ]
    book = replay_capital_6pct(four, "80/40", mode="planned_risk", max_open_positions=3)
    assert [row["reason"] for row in book["decisions"]] == ["ADMITTED", "ADMITTED", "ADMITTED", "POSITION_CAP"]
    assert book["decisions"][-1]["blocking_event_ids"] == ["A", "B", "C"]
    assert book["through_close_pnl_cents"] == -120_000
    assert book["ending_cash_cents"] == 2_000_000 - 120_000
    assert {row["sport"] for row in book["decisions"]} == {"NBA", "NCAAB"}

    same_time = replay_capital_6pct(four, "80/40", mode="planned_risk", max_open_positions=3)
    assert same_time["decisions"][-1]["event_id"] == "D"
    tied = [
        _wipe(0, day, later, 40) | {"ticker": "C", "event_id": "Z"},
        _wipe(1, day, later, 40) | {"ticker": "C", "event_id": "A"},
        _wipe(2, day, later, 40) | {"ticker": "A", "event_id": "A1"},
        _wipe(3, day, later, 40) | {"ticker": "B", "event_id": "B1"},
    ]
    ordered = replay_capital_6pct(tied, "80/40", mode="planned_risk", max_open_positions=3)
    assert [row["event_id"] for row in ordered["decisions"] if row["accepted"]] == ["A1", "B1", "A"]
    assert ordered["decisions"][-1]["event_id"] == "Z"

    exit_at = _ts(2026, 1, 15, 18)
    held = [_wipe(i, day, later, 40) | {"ticker": f"H{i}", "event_id": f"H{i}"} for i in range(2)]
    freeing = _wipe(2, day, exit_at, 40) | {"ticker": "FREE", "event_id": "FREE"}
    arriving = _wipe(3, exit_at, later, 40) | {"ticker": "NEW", "event_id": "NEW"}
    freed = replay_capital_6pct([*held, freeing, arriving], "80/40", mode="planned_risk", max_open_positions=3)
    assert freed["decisions"][-1]["reason"] == "ADMITTED"
    assert freed["decisions"][-1]["open_count_before"] == 2

    blocked = replay_capital_6pct(four, "80/40", mode="planned_risk", max_open_positions=3)
    rejected = blocked["decisions"][-1]
    assert rejected["cash_after_cents"] == rejected["cash_before_cents"]
    assert blocked["ending_cash_cents"] == 2_000_000 + blocked["through_close_pnl_cents"]

    overnight = _wipe(0, day, _ts(2026, 1, 16, 18), 40) | {"ticker": "HELD", "event_id": "HELD"}
    morning = _wipe(1, _ts(2026, 1, 16, 10), _ts(2026, 1, 16, 12), 40) | {"ticker": "NEXT", "event_id": "NEXT"}
    carried = replay_capital_6pct([overnight, morning], "80/40", mode="planned_risk", max_open_positions=3)
    assert carried["decisions"][1]["occupying_event_ids"] == ["HELD"]

    shared = {
        "ticker": "ONE",
        "event_id": "ONE",
        "entry_ts": day,
        "ledger_exit_ts": later,
        "ledger_exit_kind": "SETTLEMENT_YES",
        "t40_ts": None,
        "t40_close": None,
        "t65_ts": exit_at,
        "t65_close": 65,
    }
    follower = _surv(1, exit_at, later) | {"ticker": "TWO", "event_id": "TWO"}
    slow = replay_capital_6pct([shared, follower], "80/40", mode="planned_risk", max_open_positions=1)
    fast = replay_capital_6pct([shared, follower], "80/65", mode="planned_risk", max_open_positions=1)
    assert slow["decisions"][1]["reason"] == "POSITION_CAP"
    assert slow["decisions"][1]["occupying_event_ids"] == ["ONE"]
    assert fast["decisions"][1]["reason"] == "ADMITTED"
    assert fast["max_concurrent"] == 1

    cap1 = replay_capital_6pct([_surv(0, day, later)], "80/40", mode="planned_risk", max_open_positions=1)
    cap2 = replay_capital_6pct([_surv(0, day, later)], "80/65", mode="planned_risk", max_open_positions=2)
    assert cap1["decisions"][0]["accepted_contracts"] == 1000
    assert cap2["decisions"][0]["accepted_contracts"] == 1500
    wide = replay_capital_6pct(four, "80/40", mode="planned_risk", max_open_positions=1)
    assert sum(1 for row in wide["decisions"] if row["accepted"]) == 1

    with pytest.raises(ChoosinTexasError):
        reconstruct_occupancy(
            [
                {"event_id": name, "ticker": name, "entry_ts": day, "exit_ts": later}
                for name in ("A", "B", "C", "D")
            ],
            max_open_positions=3,
        )

    severity = loss_severity(
        {
            "book": "80/40",
            "decisions": [
                {
                    "accepted_contracts": 1000,
                    "realized_pnl_cents": -50_000,
                    "entry_session_basis_cents": 2_000_000,
                    "stopped": True,
                    "event_id": "BIG",
                },
                {
                    "accepted_contracts": 10,
                    "realized_pnl_cents": -800,
                    "entry_session_basis_cents": 10_000,
                    "stopped": True,
                    "event_id": "PCT",
                },
            ],
            "loss_breaches": [],
            "loss_breach_summary": {"count": 0},
        }
    )
    assert severity["largest_dollar_loss"]["event_id"] == "BIG"
    assert severity["largest_percent_loss"]["event_id"] == "PCT"
    assert severity["largest_dollar_and_percent_same_event"] is False
