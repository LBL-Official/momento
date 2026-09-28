"""No PIT-safe dataset returns future measurement tables."""

from __future__ import annotations

from pathlib import Path

import pytest

from roller import Roller
from roller.point_in_time.filters import FutureInformationError
from roller.validation.greek_leakage import audit_baseline_eligibility_example


def test_measurement_tables_rejected_from_dataset(roller_env: Path):
    db = Roller(roller_env)
    for name in ("market_response_5m", "v3_response_corpus", "response_residual", "greek_theta"):
        with pytest.raises(FutureInformationError):
            db.dataset("NBA", "2025-2026", name, as_of="2025-12-21")


def test_baseline_eligibility_contract():
    assert audit_baseline_eligibility_example() == []
