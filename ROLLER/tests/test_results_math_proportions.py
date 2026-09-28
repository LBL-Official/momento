from roller.results_math.proportions import clopper_pearson, rate, wilson_interval


def test_rate_84_113():
    r = rate(84, 113)
    assert r is not None
    assert abs(r["percentage"] - 74.336) < 0.01
    assert r["successes"] == 84
    assert r["denominator"] == 113


def test_rate_188_271():
    r = rate(188, 271)
    assert r is not None
    assert abs(r["percentage"] - 69.37) < 0.01


def test_wilson_84_113():
    w = wilson_interval(84, 113)
    assert w is not None
    assert abs(w["p_hat"] - 84 / 113) < 1e-12
    # ~65.6% — 81.5%
    assert 0.655 < w["lower"] < 0.658
    assert 0.813 < w["upper"] < 0.817
    assert w["method"] == "wilson"


def test_clopper_pearson_contains_hat():
    c = clopper_pearson(84, 113)
    assert c is not None
    assert c["lower"] < 84 / 113 < c["upper"]
    assert c["method"] == "clopper_pearson"


def test_rate_zero_n():
    assert rate(0, 0) is None
    assert wilson_interval(0, 0) is None
