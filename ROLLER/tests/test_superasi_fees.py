"""PublishedScheduleEstimate quotes. FEE MODEL = ESTIMATED."""

from __future__ import annotations

from roller.superasi.fees import load_fee_models, quote_one_contract


def test_published_schedule_one_contract():
    fm = load_fee_models()
    model = fm.PublishedScheduleEstimate()
    for price, maker in ((80, True), (80, False), (40, True), (40, False)):
        expected = model.calculate_entry_fee(1, price, maker)
        got = quote_one_contract(price, maker=maker)
        assert got["amount_e6"] == expected.amount_e6
        assert got["status"] == "ESTIMATED"
        assert got["model_id"] == "PUBLISHED_SCHEDULE_ESTIMATE"
