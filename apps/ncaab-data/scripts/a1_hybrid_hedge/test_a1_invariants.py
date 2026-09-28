"""Invariants: threshold ≠ fill. Observed price is not normalized to H."""

from .execution import band_for, classify_opportunity
from .pnl import CostModel, hybrid_pnl, lock_pnl


def test_gap_does_not_fill():
    band = band_for("exact", 40)
    cls = classify_opportunity(True, 75.0, 0, True, band, 3)
    assert cls["tier"] == "TIER3_GAP"
    assert cls["gap"] is True
    assert cls["in_band"] is False


def test_observed_price_not_normalized():
    band = band_for("band_37_42", 40)
    cls = classify_opportunity(True, 37.0, 2, False, band, 3)
    assert cls["in_band"] is True
    assert cls["obs_px"] == 37.0
    assert lock_pnl(80, cls["obs_px"], CostModel(), True) == -17.0


def test_no_opportunity():
    band = band_for("exact", 40)
    cls = classify_opportunity(False, None, None, False, band, 3)
    assert cls["tier"] == "NONE"
    assert hybrid_pnl(-40, 80, None, 1, 1, CostModel()) == -40


def test_lock_identity():
    assert lock_pnl(80, 17, CostModel(), True) == 3
    assert lock_pnl(80, 20, CostModel(), True) == 0
    assert lock_pnl(80, 40, CostModel(), True) == -20


if __name__ == "__main__":
    test_gap_does_not_fill()
    test_observed_price_not_normalized()
    test_no_opportunity()
    test_lock_identity()
    print("a1 invariants ok")
