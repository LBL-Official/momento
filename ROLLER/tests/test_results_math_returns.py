from roller.results_math.means import mean, median, sample_std, sample_variance, t_interval
from roller.results_math.returns import return_distribution, trade_sharpe


def test_known_vector():
    xs = [-10, 20, 30]
    assert mean(xs) == 40 / 3
    assert median(xs) == 20
    # sample var: mean=13.333..., diffs 23.333^2 + 6.667^2 + 16.667^2 / 2
    v = sample_variance(xs)
    assert v is not None
    expected = ((-10 - 40 / 3) ** 2 + (20 - 40 / 3) ** 2 + (30 - 40 / 3) ** 2) / 2
    assert abs(v - expected) < 1e-9
    assert abs(sample_std(xs) - expected**0.5) < 1e-9
    dist = return_distribution(xs)
    assert dist["n"] == 3
    assert dist["min_cents"] == -10
    assert dist["max_cents"] == 30
    assert dist["sharpe_trade"] == trade_sharpe(xs)


def test_n1_unavailable():
    dist = return_distribution([5])
    assert dist["std_cents"] is None
    assert dist["sharpe_trade"] is None
    assert t_interval([5]) is None


def test_zero_variance_sharpe_unavailable():
    assert trade_sharpe([3, 3, 3]) is None


def test_empty_returns_unavailable():
    dist = return_distribution([])
    assert dist["status"] == "UNAVAILABLE"
    assert dist["n"] == 0


def test_missing_exit_not_zero():
    from roller.results_math.observations import normalize_rows, valid_returns

    rows = [
        {"hyp_pnl_cents": 5, "entry_ts": "a"},
        {"hyp_pnl_cents": None, "exit_close": None, "entry_ts": "b"},
    ]
    xs = valid_returns(normalize_rows(rows))
    assert xs == [5]


def test_t_interval_has_se_tstat_pvalue():
    xs = [-10, 20, 30]
    ci = t_interval(xs)
    assert ci is not None
    assert ci["standard_error"] > 0
    assert ci["t_statistic"] == ci["estimate"] / ci["standard_error"]
    assert ci["null"] == "EV = 0"
    assert 0 < ci["p_value"] <= 1
    assert ci["zero_inside_ci"] is True
    assert ci["lower"] < 0 < ci["upper"]


def test_symmetric_zero_mean_pvalue_high():
    ci = t_interval([-5, 0, 5])
    assert ci is not None
    assert abs(ci["estimate"]) < 1e-12
    assert ci["p_value"] > 0.9
    assert ci["zero_inside_ci"] is True
