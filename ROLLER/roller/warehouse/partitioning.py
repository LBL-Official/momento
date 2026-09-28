"""Partition grain matches existing monthly CSV. Do not invent daily files yet.

Canonical CSV:  month=YYYY-MM.csv
Dual-write PQ:  month=YYYY-MM.parquet  (same directory, beside CSV)
"""

from __future__ import annotations

from pathlib import Path

MONTH_CSV = "month={month}.csv"
MONTH_PARQUET = "month={month}.parquet"


def month_csv(directory: Path, month: str) -> Path:
    return directory / MONTH_CSV.format(month=month)


def month_parquet(directory: Path, month: str) -> Path:
    return directory / MONTH_PARQUET.format(month=month)


def list_month_csvs(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(directory.glob("month=*.csv"))


def list_month_parquets(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(directory.glob("month=*.parquet"))


def month_key(path: Path) -> str:
    name = path.name
    if name.startswith("month=") and name.endswith(".csv"):
        return name[len("month=") : -len(".csv")]
    if name.startswith("month=") and name.endswith(".parquet"):
        return name[len("month=") : -len(".parquet")]
    return name
