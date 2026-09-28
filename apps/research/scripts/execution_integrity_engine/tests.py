"""EIE invariants. Gap ≠ fill. Modeled ≠ actual."""

from .classify import classify_l2
from .enums import E1, EXACT_OBSERVATION, GAP_THROUGH, L4, NO_OBSERVATION
from .expectancy import decompose
from .models import e1_conservative, e_theoretical_threshold


def test_gap_not_e1_fill():
    l2 = classify_l2(True, True, 75.0, True, 40, 40, 40)
    assert l2["opportunity_class"] == GAP_THROUGH
    assert l2["threshold_crossing"] is True
    e1 = e1_conservative(l2, -40.0)
    assert e1["hedge_filled"] is False
    assert e1["pnl"] == -40.0
    theo = e_theoretical_threshold(l2, 20.0, 40)
    assert theo["hedge_filled"] is True
    assert theo["hedge_price"] == 40.0
    assert theo["fill_claim"] == "ILLEGAL_PROMOTION_BENCHMARK"


def test_exact_observed_not_l4():
    l2 = classify_l2(True, True, 40.0, False, 40, 40, 40)
    assert l2["opportunity_class"] == EXACT_OBSERVATION
    e1 = e1_conservative(l2, -40.0)
    assert e1["hedge_price"] == 40.0
    assert e1["fill_claim"] != "ACTUAL"
    assert e1["execution_model_id"] == E1
    assert e1["evidence_level"] != L4


def test_no_obs():
    l2 = classify_l2(False, False, None, False, 40, 40, 40)
    assert l2["opportunity_class"] == NO_OBSERVATION
    assert e1_conservative(l2, 20.0)["hedge_filled"] is False


def test_decomp_identity():
    pnls = [20, -40, -20, 20]
    labs = ["A", "B", "C", "A"]
    d = decompose(pnls, labs)
    assert d["identity_ok"]


def run_unit() -> None:
    test_gap_not_e1_fill()
    test_exact_observed_not_l4()
    test_no_obs()
    test_decomp_identity()
    print("eie unit ok", flush=True)
