"""Z does not invent a probability from a missing quote."""

from roller.ontologic_xyz.status import joint_status


def test_october_3_without_a_quote_is_not_calibrated():
    body = joint_status(
        "2026-10-03",
        {
            "status": "SOURCE_UNAVAILABLE",
            "bookmaker": "williamhill",
            "quotes": [],
        },
    )
    assert body["x"]["status"] == "SOURCE_UNAVAILABLE"
    assert body["x"]["quote_count"] == 0
    assert body["y"]["status"] == "MARKET_MODEL_UNAVAILABLE"
    assert body["z"]["status"] == "NOT_CALIBRATED"
    assert body["z"]["probability"] is None
    assert body["z"]["method"] == "JOINT_CALIBRATION_NOT_AN_AVERAGE"
    assert body["live_execution"] is False
