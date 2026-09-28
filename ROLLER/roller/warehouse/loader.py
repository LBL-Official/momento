"""Warehouse readers. Confirm & Run still uses admin.load_dataset (CSV).

This loader may read a dual-written parquet for audit/round-trip only.
It must not become a silent second Confirm & Run path.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from roller.admin import load_dataset
from roller.config import RollerConfig
from roller.io_csv import read_csv
from roller.warehouse.partitioning import month_parquet


def load_canonical_csv(
    cfg: RollerConfig,
    sport: str,
    season: str,
    dataset: str,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
) -> pd.DataFrame:
    """Same bytes as admin.load_dataset. Explicit name for audits."""
    return load_dataset(cfg, sport, season, dataset, date_from=date_from, date_to=date_to)


def read_month_csv(path: Path) -> pd.DataFrame:
    return read_csv(path)


def read_month_parquet(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(path)
    return pd.read_parquet(path)


def parquet_beside(csv_path: Path) -> Path:
    month = csv_path.name[len("month=") : -len(".csv")]
    return month_parquet(csv_path.parent, month)
