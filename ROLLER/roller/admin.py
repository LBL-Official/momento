"""Admin / build API — unrestricted readers for pipeline scripts only."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from roller.config import RollerConfig
from roller.io_csv import concat_partition_csvs, partition_months, read_csv, read_csv_optional


def load_table(
    path: Path,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
) -> pd.DataFrame:
    if path.is_dir():
        return concat_partition_csvs(path, months=partition_months(date_from, date_to))
    return read_csv(path)


def load_dataset(
    cfg: RollerConfig,
    sport: str,
    season: str,
    dataset: str,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
) -> pd.DataFrame:
    return load_table(
        cfg.dataset_path(sport, season, dataset),
        date_from=date_from,
        date_to=date_to,
    )


def load_identity(cfg: RollerConfig) -> pd.DataFrame:
    return read_csv_optional(
        cfg.root / "meta" / "game_identity.csv",
        columns=cfg.schemas["datasets"]["game_identity"]["columns"],
    )


def load_teams(cfg: RollerConfig) -> pd.DataFrame:
    return read_csv_optional(cfg.root / "meta" / "teams.csv")
