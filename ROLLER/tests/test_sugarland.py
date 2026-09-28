"""Sugarland cohort rules. Synthetic clocks only — no Austin confirmation cohorts."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

from roller.choosin_texas.sugarland.accum import TickerState
from roller.choosin_texas.sugarland.associate import ENTRY_FEATURES, design_descriptive, design_entry
from roller.choosin_texas.sugarland.clocks import classify_stored_schedule
from roller.choosin_texas.sugarland.constants import ENTRY_FEATURES as LOCKED_FEATURES
from roller.choosin_texas.sugarland.metrics import dpp, gross_dollars, return_on_ask, summarize_dpp
from roller.choosin_texas.sugarland.slope import path_from_grid
from roller.choosin_texas.sugarland.trades import aggregate_positions, reconcile_fill_id

START = 1_700_000_000
T_END = START - 1800


def _state(**kwargs: object) -> TickerState:
    params = dict(
        ticker="T",
        game_id="G",
        sport="NBA",
        season="2025-2026",
        team_side="home",
        game_date="2025-11-01",
        clock_label="RETROSPECTIVE_ACTUAL_START",
        t_start=START,
        t_end=T_END,
        t_end_sched=None,
        quarantine="",
        schedule_relation="STORED_SCHEDULE_UNAVAILABLE",
        partition="discovery",
    )
    params.update(kwargs)
    return TickerState(**params)  # type: ignore[arg-type]


def test_cohort_a_does_not_search_forward_for_70() -> None:
    state = _state()
    state.consume(START - 48 * 3600, 6000, 6100, 3)
    state.consume(START - 24 * 3600, 7500, 7600, 3)
    state.consume(T_END - 60, 7600, 7700, 3)
    row = state.finalize()
    assert row["in_a"] is False
    assert row["exclusion"] == "FIRST_OBSERVED_NOT_ABOVE_70"
    assert row["p0_bid_e4"] == 6000
    assert row["h48_above70"] is False
    assert row["h48_around80"] is False


def test_cohort_a_includes_first_valid_above_70_and_counts_invalid_history() -> None:
    state = _state()
    state.consume(START - 50 * 3600, 0, 100, 1)
    state.consume(START - 48 * 3600, 7200, 7300, 4)
    state.consume(T_END - 60, 7500, 7600, 4)
    row = state.finalize()
    assert row["in_a"] is True
    assert row["n_invalid_before_valid"] == 1
    assert row["history_before_first_raw"] == "UNKNOWN"
    assert row["listing_time"] == "UNAVAILABLE"
    assert row["dpp_e4"] == 300
    assert row["dpp"] == Fraction(3, 1)
    assert dpp(7200, 7500) == Fraction(300, 100)


def test_future_candle_is_not_the_endpoint() -> None:
    state = _state()
    state.consume(START - 10 * 3600, 7200, 7300, 1)
    state.consume(T_END - 120, 7400, 7500, 1)
    state.consume(T_END + 120, 9000, 9100, 1)
    row = state.finalize()
    assert row["p30_bid_e4"] == 7400
    assert row["p30_ts"] <= T_END
    assert row["p0_ts"] < T_END


def test_stale_quote_misses_primary_endpoint() -> None:
    state = _state()
    state.consume(START - 6 * 3600, 8100, 8200, 1)
    state.consume(T_END - 45 * 60, 8300, 8400, 1)
    row = state.finalize()
    assert row["in_a"] is True
    assert row["p30_bid_e4"] is None
    assert row["endpoint_status"] == "MISSING_ENDPOINT"
    assert row["p30_age_1800_bid_e4"] is None
    assert row["p30_age_3600_bid_e4"] == 8300


def test_horizon_filter_is_applied_after_the_quote_is_retrieved() -> None:
    state = _state()
    state.consume(START - 48 * 3600 - 600, 6000, 6100, 1)
    state.consume(START - 48 * 3600 + 60, 8200, 8300, 1)
    state.consume(START - 24 * 3600 - 300, 8100, 8200, 1)
    state.consume(T_END - 60, 8400, 8500, 1)
    row = state.finalize()
    assert row["h48_bid_e4"] == 6000
    assert row["h48_above70"] is False
    assert row["h48_around80"] is False
    assert row["h24_bid_e4"] == 8100
    assert row["h24_around80"] is True
    assert row["in_a"] is False


def test_crossing_keeps_actual_price_and_already_above_is_separate() -> None:
    crossing = _state(ticker="C")
    crossing.consume(START - 30 * 3600, 7900, 8000, 1)
    crossing.consume(START - 20 * 3600, 8250, 8350, 1)
    crossing.consume(T_END - 60, 8400, 8500, 1)
    row = crossing.finalize()
    assert row["in_b"] is True
    assert row["b_bid_e4"] == 8250
    assert row["already_above_80"] is False

    opened = _state(ticker="O")
    opened.consume(START - 30 * 3600, 8300, 8400, 1)
    opened.consume(T_END - 60, 8500, 8600, 1)
    opened_row = opened.finalize()
    assert opened_row["already_above_80"] is True
    assert opened_row["in_b"] is False


def test_stored_schedule_match_is_not_implementable() -> None:
    start = parse_pair()
    info = classify_stored_schedule(start, start)
    assert info["schedule_relation"] == "STORED_MATCH_NOT_IMPLEMENTABLE"
    assert info["quarantine"] == ""
    assert "IMPLEMENTABLE" not in info["primary_role"]
    late = classify_stored_schedule(start, start.replace(hour=start.hour) )  # same
    assert late["quarantine"] == ""


def parse_pair():
    from datetime import datetime, timezone

    return datetime(2025, 11, 1, 23, 0, tzinfo=timezone.utc)


def test_schedule_exception_over_six_hours() -> None:
    from datetime import timedelta

    start = parse_pair()
    info = classify_stored_schedule(start, start + timedelta(hours=7))
    assert info["quarantine"] == "SCHEDULE_EXCEPTION"


def test_slope_stale_gap_has_zero_weight_and_time_above_uses_covered_time() -> None:
    anchor = 0
    # 15-minute steps for 30 minutes: two intervals, both above anchor except we set bids.
    grid = {900: (900, 8100), 1800: (1800, 7900), 2700: (2700, 7900)}
    path = path_from_grid(grid, anchor, 8000, 2700)
    assert path["n_positive_weights"] == 3
    assert path["covered_hours"] == 0.75
    assert path["share_above"] == 1 / 3
    assert path["share_below"] == 1 / 3
    assert path["share_unchanged"] == 1 / 3
    assert path["uncovered_hours"] == 0
    assert path["status"] == "INSUFFICIENT_COVERAGE"

    gapped = {7200: (7200, 8100)}
    gapped_path = path_from_grid(gapped, 0, 8000, 7200)
    assert gapped_path["n_positive_weights"] == 0
    assert gapped_path["covered_hours"] == 0


def test_slope_reports_when_coverage_gates_pass() -> None:
    anchor_bid = 8000
    grid = {}
    # 25 quarter-hours = 6.25h of steps after t=0; weights on the first 24 gaps = 6h.
    for step in range(1, 26):
        grid_t = step * 900
        grid[grid_t] = (grid_t, 8000 + step)
    path = path_from_grid(grid, 0, anchor_bid, 25 * 900)
    assert path["status"] == "OK"
    assert path["n_positive_weights"] >= 8
    assert path["beta_pp_per_hour"] is not None
    assert path["beta_pp_per_hour"] > 0


def test_quote_benchmark_units() -> None:
    assert gross_dollars(7300, 7500) == Fraction(200, 10000)
    assert return_on_ask(7300, 7500) == Fraction(200, 7300)
    summary = summarize_dpp(
        [
            {"game_date": "2025-11-01", "dpp": Fraction(2, 1), "return_on_ask": Fraction(1, 80), "gross_positive": True},
            {"game_date": "2025-11-02", "dpp": Fraction(-1, 1), "return_on_ask": Fraction(-1, 80), "gross_positive": False},
        ]
    )
    assert summary["endpoint_n"] == 2
    assert summary["mean_dpp"] == 0.5
    assert summary["status"] == "OBSERVED"
    assert summarize_dpp([])["mean_dpp"] is None
    assert summarize_dpp([])["status"] == "UNAVAILABLE"


def test_entry_model_rejects_actual_start_lead_time() -> None:
    assert not any("lead" in name for name in LOCKED_FEATURES)
    assert ENTRY_FEATURES == LOCKED_FEATURES
    row = {
        "sport": "NBA",
        "p0_bid_e4": 8100,
        "p0_spread_e4": 100,
        "p0_volume": 12,
        "lead_hours_descriptive": 36,
    }
    entry = design_entry(row)
    descriptive = design_descriptive(row)
    assert "lead_hours_actual_start" not in entry
    assert "lead_hours_descriptive" not in entry
    assert descriptive["lead_hours_actual_start"] == 36


def test_fill_conflict_and_partial_fill_aggregation() -> None:
    conflict = reconcile_fill_id(
        [
            {"contracts": {"status": "CONFIRMED", "value": 5}, "price_cents": {"status": "CONFIRMED", "value": 81}},
            {"contracts": {"status": "CONFIRMED", "value": 7}, "price_cents": {"status": "CONFIRMED", "value": 81}},
        ]
    )
    assert conflict["conflict"] is True
    assert conflict["contracts"]["status"] == "RECONCILIATION_CONFLICT"

    first = reconcile_fill_id(
        [
            {
                "contracts": {"status": "CONFIRMED", "value": 2},
                "price_cents": {"status": "CONFIRMED", "value": 81},
                "amount_cents": {"status": "CONFIRMED", "value": 162},
                "order_id": {"status": "CONFIRMED", "value": "ord"},
                "market": {"status": "CONFIRMED", "value": "KXWNBAGAME-1-LV"},
                "fee_cents": {"status": "UNAVAILABLE", "value": None},
            }
        ]
    )
    second = reconcile_fill_id(
        [
            {
                "contracts": {"status": "CONFIRMED", "value": 3},
                "price_cents": {"status": "CONFIRMED", "value": 81},
                "amount_cents": {"status": "CONFIRMED", "value": 243},
                "order_id": {"status": "CONFIRMED", "value": "ord"},
                "market": {"status": "CONFIRMED", "value": "KXWNBAGAME-1-LV"},
                "fee_cents": {"status": "UNAVAILABLE", "value": None},
            }
        ]
    )
    first["fill_id"] = "f1"
    second["fill_id"] = "f2"
    positions = aggregate_positions([first, second])
    assert len(positions) == 1
    assert positions[0]["contracts"] == 5
    assert positions[0]["acquisition_cost_cents"] == 405
    assert positions[0]["realized_pnl"] == "NOT_SUPPORTED"
    assert positions[0]["fee_cents"] == "UNAVAILABLE"
    assert positions[0]["price_band"] == "EXACT_81"


def test_missing_endpoint_classifies_boundary_stale_absent_and_spread() -> None:
    boundary = _state(ticker="B")
    boundary.consume(START - 48 * 3600, 8000, 8100, 1)
    boundary.consume(T_END - 60, 9900, 10000, 1)
    row = boundary.finalize()
    assert row["p30_bid_e4"] is None
    assert row["endpoint_exclusion"] == "BOUNDARY_QUOTE"
    assert row["boundary_p30_bid_e4"] == 9900
    assert row["boundary_log_odds_defined"] is True
    assert row["h48_around80"] is True

    certain = _state(ticker="C")
    certain.consume(START - 48 * 3600, 8000, 8100, 1)
    certain.consume(T_END - 30, 10000, 10000, 1)
    certain_row = certain.finalize()
    assert certain_row["endpoint_exclusion"] == "BOUNDARY_QUOTE"
    assert certain_row["boundary_p30_bid_e4"] == 10000
    assert certain_row["boundary_log_odds_defined"] is False

    stale = _state(ticker="S")
    stale.consume(START - 6 * 3600, 8100, 8200, 1)
    stale.consume(T_END - 45 * 60, 8300, 8400, 1)
    stale_row = stale.finalize()
    assert stale_row["p30_bid_e4"] is None
    assert stale_row["endpoint_exclusion"] == "STALE_OBSERVATION"

    absent = _state(ticker="A")
    absent.consume(START - 10 * 3600, 9000, 8000, 1)
    absent_row = absent.finalize()
    assert absent_row["endpoint_exclusion"] == "ABSENT_CANDLES"

    wide = _state(ticker="W")
    wide.consume(START - 48 * 3600, 8000, 8100, 1)
    wide.consume(T_END - 60, 8000, 9500, 1)
    wide_row = wide.finalize()
    assert wide_row["endpoint_exclusion"] == "EXCESSIVE_SPREAD"
    assert wide_row["boundary_p30_bid_e4"] is None

    kept = _state(ticker="K")
    kept.consume(START - 48 * 3600, 8000, 8100, 1)
    kept.consume(T_END - 20 * 60, 8100, 8200, 1)
    kept.consume(T_END - 60, 10000, 10000, 1)
    kept_row = kept.finalize()
    assert kept_row["p30_bid_e4"] == 8100
    assert kept_row["endpoint_exclusion"] == ""


def test_spread_identity_and_paired_48h_selection() -> None:
    from roller.choosin_texas.sugarland.audit import paired_from_48h, spread_terms

    rows = [
        {
            "sport": "NBA",
            "game_date": "2025-11-01",
            "quarantine": "",
            "h48_around80": True,
            "h48_bid_e4": 8000,
            "h48_ask_e4": 8300,
            "h24_around80": False,
            "h24_bid_e4": 9000,
            "h24_ask_e4": 9100,
            "p30_bid_e4": 8600,
        },
        {
            "sport": "NBA",
            "game_date": "2025-11-02",
            "quarantine": "",
            "h48_around80": True,
            "h48_bid_e4": 8100,
            "h48_ask_e4": 8200,
            "h24_around80": True,
            "h24_bid_e4": 8000,
            "h24_ask_e4": 8100,
            "p30_bid_e4": None,
            "endpoint_exclusion": "STALE_OBSERVATION",
        },
    ]
    terms = spread_terms(rows, 48)
    assert terms["complete_n"] == 1
    assert terms["bid_appreciation_cents"]["mean_cents"] == 6
    assert terms["entry_spread_cents"]["mean_cents"] == 3
    assert terms["quote_profit_cents"]["mean_cents"] == 3
    assert terms["quote_profit_cents"]["interval_status"] == "INSUFFICIENT_SAMPLE"
    assert terms["identity_max_abs_cents"] == 0
    paired = paired_from_48h(rows)
    assert paired["paired_n"] == 1
    assert paired["dropped_missing_endpoint"] == 1
    assert paired["still_outside_around80_at_24h"] == 1
    assert paired["cents_48_to_24"]["mean_cents"] == 10
    assert paired["cents_24_to_30"]["mean_cents"] == -4
    assert paired["cents_48_to_30"]["mean_cents"] == 6


def test_one_contract_interval_is_insufficient_sample() -> None:
    from roller.choosin_texas.sugarland.report import headline_for

    cell = headline_for(
        [
            {
                "game_date": "2025-12-01",
                "partition": "validation",
                "dpp": -2,
                "return_on_ask": -0.05,
                "gross_positive": False,
            }
        ]
    )
    assert cell["endpoint_n"] == 1
    assert cell["mean_dpp"] == -2
    assert cell["ci95_low"] == "INSUFFICIENT_SAMPLE"
    assert cell["ci95_high"] == "INSUFFICIENT_SAMPLE"


def test_source_does_not_reference_sealed_confirmation_cohorts() -> None:
    root = Path(__file__).resolve().parents[1] / "roller" / "choosin_texas" / "sugarland"
    text = "\n".join(path.read_text() for path in root.glob("*.py"))
    assert "confirmation_cohort" not in text


def test_examples_recompute_from_e4() -> None:
    path = Path(__file__).resolve().parents[2] / "research" / "sugarland" / "v1" / "examples.json"
    if not path.is_file():
        return
    import json

    payload = json.loads(path.read_text())
    for kind in ("appreciation", "depreciation"):
        row = payload[kind]
        assert row is not None
        assert row["p30_ts"] <= row["t_end"]
        assert row["p0_ts"] < row["t_end"]
        assert row["dpp_e4"] == row["p30_bid_e4"] - row["p0_bid_e4"]
        if kind == "appreciation":
            assert row["dpp_e4"] > 0
        else:
            assert row["dpp_e4"] < 0
    missing = payload["missing_endpoint"]
    assert missing is not None
    assert missing["p30_bid_e4"] is None
    schedule = payload["schedule_exception"]
    assert schedule is not None
    assert schedule["kind"] in {"schedule_exception", "mlb_or_start_missing"}
