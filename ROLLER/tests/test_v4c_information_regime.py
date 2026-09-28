from __future__ import annotations

from roller.validation.v4c_information_regime import (
    audit_declared_clocks,
    audit_information_regimes,
)
from roller.v4c.availability import DECLARED_CLOCKS


def test_regimes_and_clocks():
    assert audit_information_regimes() == []
    assert audit_declared_clocks() == []
    assert "timestamp" not in DECLARED_CLOCKS
    assert "event_available_at" in DECLARED_CLOCKS
    assert "book_snapshot_available_at" in DECLARED_CLOCKS
