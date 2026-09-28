from terminal_efficiency.ingestion.kalshi import record_existing_kalshi_gap
from terminal_efficiency.pipeline import apply_candles


def test_kalshi_partial_or_missing_is_documented():
    status = record_existing_kalshi_gap("NBA", "2024-2025")
    assert status["status"] in {"MISSING", "PARTIAL", "AVAILABLE"}
    if status["status"] != "AVAILABLE":
        assert "data_gap" in status


def test_apply_candles_without_states():
    # Uses real derived path; empty is ok
    out = apply_candles("NCAAB", "1999-2000")
    assert out.get("status") in {"MISSING", "DATA_GAP", "PARTIAL"} or "reason" in out
