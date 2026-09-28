from __future__ import annotations

from roller.v4b.measurements import compute_observed
from tests.helpers_v4b import make_xt


def test_pure_theta_requires_same_period_and_score():
    xt = make_xt(s_t=-3, s_prev=-3, period_t=2, period_prev=2, elapsed_t=780, elapsed_prev=720)
    p = compute_observed(xt)["pure_theta"]
    assert p.status == "valid"
    assert p.value == compute_observed(xt)["theta_observed"].value
    assert p.provenance["interpretation"] == "PARTIAL"
    assert p.provenance["not"] == "NO-EVENT THETA"


def test_pure_theta_mixed_when_score_changes():
    xt = make_xt(s_t=1, s_prev=-2, period_t=2, period_prev=2)
    p = compute_observed(xt)["pure_theta"]
    assert p.value is None
    assert p.status == "MIXED_INTERVAL"


def test_pure_theta_mixed_when_period_changes():
    xt = make_xt(s_t=1, s_prev=1, period_t=3, period_prev=2)
    p = compute_observed(xt)["pure_theta"]
    assert p.status == "MIXED_INTERVAL"
