"""Warehouse paths. Writes only under derived/terminal_efficiency/."""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[1]
CONFIG_DIR = PACKAGE_ROOT / "config"


def data_root() -> Path:
    env = os.environ.get("MOMENTO_RESEARCH_DATA_DIR")
    if env:
        return Path(env)
    return REPO_ROOT / "Backtesting Suite" / "Data"


def warehouse(league: str, season: str) -> Path:
    return data_root() / league.upper() / season / "warehouse"


def derived_root(league: str, season: str) -> Path:
    sport = "nba" if league.upper() == "NBA" else "ncaab"
    p = warehouse(league, season) / "derived" / sport / "terminal_efficiency"
    p.mkdir(parents=True, exist_ok=True)
    return p


def reports_dir(league: str, season: str) -> Path:
    p = derived_root(league, season) / "reports"
    p.mkdir(parents=True, exist_ok=True)
    return p


def models_dir(league: str, season: str) -> Path:
    p = derived_root(league, season) / "models"
    p.mkdir(parents=True, exist_ok=True)
    return p


def predictions_dir(league: str, season: str) -> Path:
    p = derived_root(league, season) / "predictions"
    p.mkdir(parents=True, exist_ok=True)
    return p
