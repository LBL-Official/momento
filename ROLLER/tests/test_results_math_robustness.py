from roller.results_math.analyze import analyze_result
from roller.results_math.multiple_testing import benjamini_hochberg, bonferroni, holm
from roller.results_math.robustness import cost_sensitivity
from roller.results_math.sizing import size_allocation


def test_cost_grid_and_breakeven():
    c = cost_sensitivity(4.30)
    assert c["break_even_cost_cents"] == 4.30
    assert c["grid"][0]["net_ev_cents"] == 4.30
    assert abs(c["grid"][-1]["net_ev_cents"] - (4.30 - 5.0)) < 1e-9


def test_multiple_testing_helpers():
    ps = [0.01, 0.04, 0.20]
    b = bonferroni(ps)
    assert b[0] == 0.03
    h = holm(ps)
    assert h[0] <= h[1]
    f = benjamini_hochberg(ps)
    assert f[0] <= 0.03 + 1e-12


def test_n_not_games():
    rows = [
        {"hyp_pnl_cents": 1, "entry_ts": "2026-01-01T00:00:00Z", "internal_game_id": "g1", "ticker": "A", "path_true": True},
        {"hyp_pnl_cents": 2, "entry_ts": "2026-01-01T00:01:00Z", "internal_game_id": "g1", "ticker": "A", "path_true": True},
        {"hyp_pnl_cents": -1, "entry_ts": "2026-01-02T00:00:00Z", "internal_game_id": "g2", "ticker": "B", "path_true": False},
    ]
    out = analyze_result(rows, metrics={"win_exit": 2, "loss_exit": 1, "path_true": 2, "path_available": 3, "terminal_missing": 3, "terminal_available": 0})
    assert out["dependence"]["n_observations"] == 3
    assert out["dependence"]["n_games"] == 2


def test_allocation_not_kelly():
    s = size_allocation(allocation_cents=100_000, entry_cents=70)
    assert "Kelly" not in s["label"]
    assert "Risk" in s["label"] or "not Risk" in s["note"] or "not Risk" in s["label"]


def test_last_trade_no_pnl():
    out = analyze_result(
        [{"hyp_pnl_cents": None, "path_true": True}],
        last_trade=True,
    )
    assert out["observed_returns"]["status"] == "UNAVAILABLE"
    assert "LAST TRADE" in out["observed_returns"]["reason"]
