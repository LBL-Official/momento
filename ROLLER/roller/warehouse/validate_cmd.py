"""Validate on-disk datasets that actually exist. Sample only — do not full-scan."""

from __future__ import annotations

from typing import Any

import pandas as pd

from roller.config import RollerConfig
from roller.io_csv import read_csv
from roller.warehouse.catalog import catalog
from roller.warehouse.partitioning import list_month_csvs
from roller.warehouse.validation import validate_frame


def _sample(ref) -> pd.DataFrame:
    if ref.kind == "file":
        frame = read_csv(ref.path)
        return frame.head(5_000)
    months = list_month_csvs(ref.path)
    if not months:
        return pd.DataFrame()
    return read_csv(months[0]).head(5_000)


def run_validate(cfg: RollerConfig | None = None) -> dict[str, Any]:
    cfg = cfg or RollerConfig()
    reports: list[dict[str, Any]] = []
    for season in catalog(cfg):
        if not season.root.is_dir():
            continue
        for name, ref in season.datasets.items():
            if ref.kind == "missing":
                continue
            try:
                frame = _sample(ref)
            except FileNotFoundError:
                continue
            report = validate_frame(name, frame)
            payload = report.to_dict()
            payload["sport"] = season.sport
            payload["season"] = season.season
            payload["sampled"] = True
            reports.append(payload)
    return {"reports": reports, "failed": [r for r in reports if not r.get("ok")]}
