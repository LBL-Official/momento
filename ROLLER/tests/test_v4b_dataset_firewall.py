from __future__ import annotations

from pathlib import Path

import pytest

from roller import Roller
from roller.point_in_time.filters import FutureInformationError


def test_v4b_names_use_db_greeks_hint(roller_env: Path):
    db = Roller(roller_env)
    with pytest.raises(FutureInformationError, match="use db.greeks()"):
        db.dataset("NBA", "2025-2026", "v4b_greek_observations", as_of="2025-12-21")
    with pytest.raises(FutureInformationError, match="use db.greeks()"):
        db.dataset("NBA", "2025-2026", "greek_observations", as_of="2025-12-21")
