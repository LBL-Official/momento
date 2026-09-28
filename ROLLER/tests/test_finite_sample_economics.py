"""Plan-level checks: two EVs, capital, no invented settlement, RoR not presented."""

from roller.results_math.analyze import analyze_result
from roller.results_math.payoff import decompose
from roller.results_math.sizing import size_allocation


def test_book_price_70_85_35():
    d = decompose(win_n=84, loss_n=29, win_payoff_cents=15, loss_payoff_cents=-35)
    assert d["denominator"] == 113
    assert abs(d["ev_cents"] - (84 * 15 + 29 * (-35)) / 113) < 1e-9


def test_capital_1428():
    s = size_allocation(bankroll_cents=2_000_000, allocation_cents=100_000, entry_cents=70)
    assert s["contracts"] == 1428


def test_ror_not_computed_on_analysis():
    rows = [{"hyp_pnl_cents": i, "entry_ts": f"2026-01-01T00:00:{i:02d}Z"} for i in range(5)]
    out = analyze_result(rows)
    assert out["risk_of_ruin"]["status"] == "NOT_COMPUTED"
