"""Provisional NBA warehouse_v0 paths. Phase 8 will relocate these.

Not a Confirm & Run source. Do not write beside canonical CSV.
"""

from __future__ import annotations

from pathlib import Path

from roller.config import RollerConfig

WAREHOUSE_V0_NAME = "warehouse_v0"
LINK_RULE_VERSION = "1.0.0"
LINK_METHOD_IDENTITY_TICKER = "identity_explicit_ticker"


def season_path_key(cfg: RollerConfig, sport: str, season: str) -> str:
    return str(cfg.season_meta(sport, season)["path_key"])


def warehouse_v0_root(cfg: RollerConfig, sport: str = "NBA", season: str = "2025-2026") -> Path:
    key = season_path_key(cfg, sport, season)
    return cfg.root / "data" / sport.lower() / key / "derived" / WAREHOUSE_V0_NAME


def crosswalk_path(cfg: RollerConfig) -> Path:
    return cfg.root / "meta" / "game_market_crosswalk.parquet"


def crosswalk_manifest_path(cfg: RollerConfig) -> Path:
    return cfg.root / "meta" / "game_market_crosswalk.manifest.json"


def sport_crosswalk_path(cfg: RollerConfig, sport: str = "NBA") -> Path:
    """NBA keeps the historical filename. Other desks write a sport-suffixed file."""
    if str(sport or "").upper() == "NBA":
        return crosswalk_path(cfg)
    return cfg.root / "meta" / f"game_market_crosswalk_{str(sport).lower()}.parquet"


def sport_crosswalk_manifest_path(cfg: RollerConfig, sport: str = "NBA") -> Path:
    if str(sport or "").upper() == "NBA":
        return crosswalk_manifest_path(cfg)
    return cfg.root / "meta" / f"game_market_crosswalk_{str(sport).lower()}.manifest.json"


def markets_parquet_path(cfg: RollerConfig, sport: str = "NBA", season: str = "2025-2026") -> Path:
    return warehouse_v0_root(cfg, sport, season) / "markets.parquet"


def observations_dir(cfg: RollerConfig, sport: str = "NBA", season: str = "2025-2026") -> Path:
    return warehouse_v0_root(cfg, sport, season) / "observations" / "basis=tradable_yes_bid"


def pbp_dir(cfg: RollerConfig, sport: str = "NBA", season: str = "2025-2026") -> Path:
    return warehouse_v0_root(cfg, sport, season) / "pbp"


def settlements_parquet_path(cfg: RollerConfig, sport: str = "NBA", season: str = "2025-2026") -> Path:
    return warehouse_v0_root(cfg, sport, season) / "settlements.parquet"


def settlements_manifest_path(cfg: RollerConfig, sport: str = "NBA", season: str = "2025-2026") -> Path:
    return warehouse_v0_root(cfg, sport, season) / "settlements.manifest.json"


def orderbook_dir(cfg: RollerConfig, sport: str = "NBA", season: str = "2025-2026") -> Path:
    return warehouse_v0_root(cfg, sport, season) / "orderbook"


def orderbook_capability_path(cfg: RollerConfig, sport: str = "NBA", season: str = "2025-2026") -> Path:
    return orderbook_dir(cfg, sport, season) / "capability.json"


def warehouse_v0_readme_path(cfg: RollerConfig, sport: str = "NBA", season: str = "2025-2026") -> Path:
    return warehouse_v0_root(cfg, sport, season) / "README.md"
