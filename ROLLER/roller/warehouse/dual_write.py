"""Dual-write a monthly CSV to a sibling parquet. Does not switch load_dataset."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from roller.io_csv import read_csv
from roller.warehouse.manifest import manifest_for_pair, write_partition_manifest
from roller.warehouse.partitioning import month_key, month_parquet
from roller.warehouse.schema import contract_for
from roller.warehouse.validation import validate_frame


def dual_write_month(
    csv_path: Path,
    *,
    dataset_name: str,
    sport: str,
    league: str,
    season: str,
) -> dict[str, Any]:
    if not csv_path.is_file():
        raise FileNotFoundError(csv_path)
    frame = read_csv(csv_path)
    report = validate_frame(dataset_name, frame)
    if not report.ok:
        return {"status": "FAILED", "issues": report.to_dict(), "csv": str(csv_path)}
    dest = month_parquet(csv_path.parent, month_key(csv_path))
    tmp = dest.with_suffix(".parquet.tmp")
    frame.to_parquet(tmp, index=False)
    round_trip = pd.read_parquet(tmp)
    if len(round_trip) != len(frame):
        tmp.unlink(missing_ok=True)
        return {
            "status": "FAILED",
            "reason": "row_count_mismatch",
            "csv_rows": len(frame),
            "parquet_rows": len(round_trip),
        }
    tmp.replace(dest)
    contract = contract_for(dataset_name)
    man = manifest_for_pair(
        dataset_name=dataset_name,
        observation_basis=None if contract is None else contract.observation_basis,
        sport=sport,
        league=league,
        season=season,
        month=month_key(csv_path),
        csv_path=csv_path,
        parquet_path=dest,
        row_count=len(frame),
    )
    write_partition_manifest(dest.with_name(dest.stem + ".manifest.json"), man)
    return {
        "status": "INGESTED",
        "csv": str(csv_path),
        "parquet": str(dest),
        "row_count": len(frame),
        "csv_sha256": man.csv_sha256,
        "parquet_sha256": man.parquet_sha256,
    }
