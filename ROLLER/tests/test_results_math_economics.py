from roller.results_math.analyze import analyze_result
from roller.results_math.payoff import (
    binary_entry_sensitivity,
    binary_settlement_payoffs,
    breakeven_probability,
    payoff_ev,
)
from roller.results_math.sizing import size_allocation


def test_payoff_743_30_70():
    ev = payoff_ev(0.743, 30, -70, 0.257)
    assert abs(float(ev) - 4.30) < 1e-9


def test_book_ev_84_113_exact():
    # 84/113 * 15 + 29/113 * -35
    ev = payoff_ev(84 / 113, 15, -35, 29 / 113)
    assert abs(float(ev) - (84 * 15 + 29 * (-35)) / 113) < 1e-12


def test_sizing_1000_at_70():
    s = size_allocation(allocation_cents=100_000, entry_cents=70)
    assert s["contracts"] == 1428
    assert s["deployed_cents"] == 99960
    assert s["residual_cents"] == 40


def test_dollar_ev_from_integer_sum():
    # (sum × contracts) / n
    s = size_allocation(allocation_cents=100_000, entry_cents=70)
    dollar_cents = (89 * s["contracts"]) / 113
    assert abs(dollar_cents / 100 - 11.2478) < 0.01


def test_breakeven_80_20():
    assert abs(breakeven_probability(20, -80) - 0.80) < 1e-12


def test_binary_70():
    assert binary_settlement_payoffs(70) == (30, -70)
    assert abs(breakeven_probability(30, -70) - 0.70) < 1e-12


def test_settlement_absent_not_invented():
    rows = [
        {
            "hyp_pnl_cents": 5,
            "entry_ts": "2026-01-01T00:00:00Z",
            "entry_close": 7000,
            "exit_close": 7500,
            "exit_outcome": "WIN_EXIT",
            "path_true": True,
            "terminal_yes": None,
            "internal_game_id": "g1",
        },
        {
            "hyp_pnl_cents": -8,
            "entry_ts": "2026-01-01T00:01:00Z",
            "entry_close": 7200,
            "exit_close": 6400,
            "exit_outcome": "LOSS_EXIT",
            "path_true": False,
            "terminal_yes": None,
            "internal_game_id": "g2",
        },
    ]

    class _Q:
        entry_conditions = [type("E", (), {"price_e4": 7000})()]
        path_conditions = [
            type("P", (), {"outcome": type("O", (), {"value": "win"})(), "op": type("Op", (), {"value": "REACH"})(), "price_e4": 8500})(),
            type("P", (), {"outcome": type("O", (), {"value": "loss"})(), "op": type("Op", (), {"value": "DROP_TO"})(), "price_e4": 3500})(),
        ]

    out = analyze_result(
        rows,
        question=_Q(),
        metrics={"win_exit": 1, "loss_exit": 1, "terminal_yes": 0, "terminal_available": 0, "terminal_missing": 2, "path_true": 1, "path_available": 2},
    )
    assert out["settlement_payoff"]["status"] == "UNAVAILABLE"
    assert "TERMINAL DATA UNAVAILABLE" in out["settlement_payoff"]["reason"]
    assert out["observed_ev"]["estimate_cents"] == (5 - 8) / 2
    assert out["hypothetical_payoff"]["status"] == "HYPOTHETICAL"
    assert out["risk_of_ruin"]["status"] == "NOT_COMPUTED"
    assert out["observed_ev"]["estimate_cents"] != out["hypothetical_payoff"]["ev_cents"]


def test_settlement_only_on_measured_subset():
    rows = [
        {"hyp_pnl_cents": 1, "entry_ts": "a", "terminal_yes": True, "exit_outcome": "WIN_EXIT", "path_true": True},
        {"hyp_pnl_cents": -2, "entry_ts": "b", "terminal_yes": False, "exit_outcome": "LOSS_EXIT", "path_true": False},
        {"hyp_pnl_cents": 3, "entry_ts": "c", "terminal_yes": None, "exit_outcome": "WIN_EXIT", "path_true": True},
    ]
    class _Q:
        entry_conditions = [type("E", (), {"price_e4": 7000})()]
        path_conditions = []

    out = analyze_result(
        rows,
        question=_Q(),
        metrics={"win_exit": 2, "loss_exit": 1, "terminal_yes": 1, "terminal_available": 2, "terminal_missing": 1, "path_true": 2, "path_available": 3},
    )
    assert out["settlement_payoff"]["status"] == "DERIVED"
    assert out["settlement_payoff"]["denominator"] == 2
    assert out["settlement_payoff"]["terminal_missing"] == 1


def test_zero_terminal_missing_is_not_coerced_to_n():
    rows = [
        {"hyp_pnl_cents": 20, "entry_ts": "a", "terminal_yes": True, "exit_outcome": "WIN_EXIT", "path_true": True, "entry_close": 8000},
        {"hyp_pnl_cents": -45, "entry_ts": "b", "terminal_yes": False, "exit_outcome": "LOSS_EXIT", "path_true": False, "entry_close": 8000},
    ]

    class _Q:
        entry_conditions = [type("E", (), {"price_e4": 8000})()]
        path_conditions = []

    out = analyze_result(
        rows,
        question=_Q(),
        metrics={
            "win_exit": 1,
            "loss_exit": 1,
            "terminal_yes": 2,
            "terminal_available": 2,
            "terminal_missing": 0,
            "path_true": 1,
            "path_available": 2,
        },
    )
    assert out["settlement_payoff"]["status"] == "DERIVED"
    assert out["settlement_payoff"]["terminal_missing"] == 0
    assert out["settlement"]["terminal_missing"] == 0


def test_binary_sensitivity_70_matches_example():
    s = binary_entry_sensitivity(0.743)
    by = {r["entry_cents"]: r for r in s["rows"]}
    assert abs(by[70]["payoff_ev_cents"] - 4.3) < 1e-9
    assert abs(by[70]["margin"] - 0.043) < 1e-9
    assert abs(by[65]["payoff_ev_cents"] - 9.3) < 1e-9
    assert abs(by[75]["payoff_ev_cents"] + 0.7) < 1e-9
    assert s["status"] == "HYPOTHETICAL"
    assert "not settlement" in s["label"]


def test_capitalized_distribution_and_p_ev_not_computed():
    rows = [
        {
            "hyp_pnl_cents": 14,
            "entry_ts": f"2026-01-01T00:00:{i:02d}Z",
            "entry_close": 7160,
            "exit_outcome": "WIN_EXIT",
            "path_true": True,
            "internal_game_id": f"g{i}",
        }
        for i in range(10)
    ]
    rows.append(
        {
            "hyp_pnl_cents": -42,
            "entry_ts": "2026-01-01T00:01:00Z",
            "entry_close": 7000,
            "exit_outcome": "LOSS_EXIT",
            "path_true": False,
            "internal_game_id": "gL",
        }
    )

    class _Q:
        entry_conditions = [type("E", (), {"price_e4": 7000})()]
        path_conditions = [
            type("P", (), {"outcome": type("O", (), {"value": "win"})(), "op": type("Op", (), {"value": "REACH"})(), "price_e4": 8500})(),
            type("P", (), {"outcome": type("O", (), {"value": "loss"})(), "op": type("Op", (), {"value": "DROP_TO"})(), "price_e4": 3500})(),
        ]

    out = analyze_result(rows, question=_Q(), metrics={"win_exit": 10, "loss_exit": 1, "path_true": 10, "path_available": 11, "terminal_missing": 11, "terminal_available": 0})
    dist = out["capitalization"]["observed"]["distribution"]
    assert dist["n"] == 11
    assert dist["worst_dollars"] < dist["best_dollars"]
    assert out["observed_ev"]["significance"]["p_ev_gt_zero"]["status"] == "NOT_COMPUTED"
    assert out["observed_ev"]["significance"]["zero_inside_ci"] in (True, False)
    assert out["capitalization"]["prices"]["reference_cents"] == 70
    assert out["capitalization"]["prices"]["sizing_cents"] == 70
    boot_eq = out["equity"].get("bootstrap") or {}
    assert "ending_capital_cents" in boot_eq
    assert out["robustness"]["binary_entry_sensitivity"]["status"] == "HYPOTHETICAL"
