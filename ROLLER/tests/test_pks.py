from __future__ import annotations

from pathlib import Path

from roller.admin import load_dataset
from roller.config import RollerConfig
from roller.maintenance.update import update_sport


def test_no_duplicate_primary_keys(roller_env: Path):
    cfg = RollerConfig(roller_env)
    update_sport(cfg, "NBA", "2025-2026", include_pbp=True, include_candles=True)
    games = load_dataset(cfg, "NBA", "2025-2026", "games")
    pbp = load_dataset(cfg, "NBA", "2025-2026", "pbp")
    candles = load_dataset(cfg, "NBA", "2025-2026", "kalshi_candles")
    feats = load_dataset(cfg, "NBA", "2025-2026", "team_features")
    assert not games["internal_game_id"].duplicated().any()
    assert not pbp.duplicated(["internal_game_id", "event_number"]).any()
    assert not candles.duplicated(["internal_game_id", "ticker", "candle_timestamp"]).any()
    assert not feats.duplicated(["internal_game_id", "team_id"]).any()


def test_conservative_proxy_labeled(roller_env: Path):
    cfg = RollerConfig(roller_env)
    update_sport(cfg, "NBA", "2025-2026", include_pbp=False, include_candles=False)
    games = load_dataset(cfg, "NBA", "2025-2026", "games")
    assert set(games["availability_quality"]) == {"CONSERVATIVE_PROXY"}
