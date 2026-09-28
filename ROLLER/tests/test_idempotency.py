from __future__ import annotations

from pathlib import Path

from roller.admin import load_dataset, load_identity
from roller.config import RollerConfig
from roller.maintenance.update import update_sport


def test_update_twice_no_duplicate_identity(roller_env: Path):
    cfg = RollerConfig(roller_env)
    update_sport(cfg, "NBA", "2025-2026", include_pbp=True, include_candles=True)
    a = load_identity(cfg)
    update_sport(cfg, "NBA", "2025-2026", include_pbp=True, include_candles=True)
    b = load_identity(cfg)
    assert list(a["internal_game_id"]) == list(b["internal_game_id"])
    assert not b["internal_game_id"].duplicated().any()
    g1 = load_dataset(cfg, "NBA", "2025-2026", "games")
    update_sport(cfg, "NBA", "2025-2026", include_pbp=False, include_candles=False)
    g2 = load_dataset(cfg, "NBA", "2025-2026", "games")
    assert len(g1) == len(g2)
    assert list(g1["internal_game_id"]) == list(g2["internal_game_id"])
