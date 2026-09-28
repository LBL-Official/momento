from roller.results_math.bootstrap import bootstrap_returns
from roller.results_math.versions import BOOTSTRAP_SEED


def test_bootstrap_seeded_reproducible():
    xs = [1, -2, 3, 4, -1, 2, 0, 5, -3, 1]
    a = bootstrap_returns(xs, iterations=200, seed=BOOTSTRAP_SEED)
    b = bootstrap_returns(xs, iterations=200, seed=BOOTSTRAP_SEED)
    assert a["mean"]["lower"] == b["mean"]["lower"]
    assert a["mean"]["upper"] == b["mean"]["upper"]
    assert a["sharpe"] is not None
    assert a["seed"] == BOOTSTRAP_SEED


def test_bootstrap_n1():
    out = bootstrap_returns([4], iterations=50)
    assert out["status"] == "UNAVAILABLE"


def test_cluster_bootstrap_present():
    xs = [1, 2, -1, 3]
    groups = [[1, 2], [-1, 3]]
    out = bootstrap_returns(xs, groups=groups, iterations=100, seed=1)
    assert out["cluster"] is not None
    assert out["cluster"]["mean"]["lower"] <= out["cluster"]["mean"]["upper"]


def test_bootstrap_sequence_stats():
    xs = [1, -2, 3, 4, -1, 2, 0, 5, -3, 1]
    out = bootstrap_returns(xs, iterations=200, seed=1)
    end = out["ending_pnl_cents"]
    assert end["lower"] <= end["median"] <= end["upper"]
    assert out["max_drawdown_cents"]["p95"] is not None
    assert 0 <= out["share_means_positive"] <= 1
