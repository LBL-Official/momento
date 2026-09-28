from __future__ import annotations

from pathlib import Path

import pytest

from roller.config import RollerConfig
from roller.ingest.games import load_sport_games, warehouse_available
from roller.paths import find_root

WAREHOUSE_HINT = Path(__file__).resolve().parents[2] / "Backtesting Suite" / "Data"


@pytest.mark.integration
def test_warehouse_nba_catalog_readable():
    if not (WAREHOUSE_HINT / "NBA" / "2025-2026" / "warehouse" / "normalized" / "nba" / "games" / "nba_games.json").is_file():
        pytest.skip("Momento warehouse not present")
    cfg = RollerConfig(find_root())
    assert warehouse_available(cfg, "NBA", "2025-2026")
    games, xwalk, _wh = load_sport_games(cfg, "NBA", "2025-2026")
    assert len(games) >= 1000
    assert any(r.get("match_status") == "MATCHED" for r in xwalk)
