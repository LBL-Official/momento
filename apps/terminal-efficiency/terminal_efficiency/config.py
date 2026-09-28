from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from terminal_efficiency.paths import CONFIG_DIR


@dataclass(frozen=True)
class LeagueConfig:
    league: str
    regulation_periods: int
    period_seconds: int
    ot_seconds: int
    train_end: str
    exclude_game_id_prefixes: tuple[str, ...]
    pbp_source: str
    pace_minutes: int
    possession_rule_version: str
    n_mcd_simulations: int
    mcd_seed: int
    p5_only_in_game: bool = False
    d1_pregame_only_when_no_pbp: bool = False


def load_league_config(league: str) -> LeagueConfig:
    name = "nba.yaml" if league.upper() == "NBA" else "ncaab.yaml"
    path = CONFIG_DIR / name
    raw = yaml.safe_load(path.read_text())
    return LeagueConfig(
        league=str(raw["league"]),
        regulation_periods=int(raw["regulation_periods"]),
        period_seconds=int(raw["period_seconds"]),
        ot_seconds=int(raw["ot_seconds"]),
        train_end=str(raw["train_end"]),
        exclude_game_id_prefixes=tuple(raw.get("exclude_game_id_prefixes") or []),
        pbp_source=str(raw["pbp_source"]),
        pace_minutes=int(raw["pace_minutes"]),
        possession_rule_version=str(raw["possession_rule_version"]),
        n_mcd_simulations=int(raw["n_mcd_simulations"]),
        mcd_seed=int(raw["mcd_seed"]),
        p5_only_in_game=bool(raw.get("p5_only_in_game", False)),
        d1_pregame_only_when_no_pbp=bool(raw.get("d1_pregame_only_when_no_pbp", False)),
    )


def config_path(league: str) -> Path:
    name = "nba.yaml" if league.upper() == "NBA" else "ncaab.yaml"
    return CONFIG_DIR / name
