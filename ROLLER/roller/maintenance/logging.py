"""Append-only update_log.csv."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from roller.io_csv import read_csv_optional, write_csv
from roller.timeutil import now_utc_iso

LOG_COLUMNS = [
    "update_id",
    "timestamp",
    "dataset",
    "sport",
    "season",
    "records_before",
    "records_added",
    "records_updated",
    "records_after",
    "status",
    "error_message",
    "source_version",
    "pipeline_version",
    "prior_source_hash",
    "new_source_hash",
]


def append_log(root: Path, row: dict) -> None:
    path = root / "meta" / "update_log.csv"
    prev = read_csv_optional(path, LOG_COLUMNS)
    rec = {c: row.get(c, "") for c in LOG_COLUMNS}
    if not rec.get("timestamp"):
        rec["timestamp"] = now_utc_iso()
    next_df = pd.concat([prev, pd.DataFrame([rec])], ignore_index=True)
    write_csv(path, next_df, LOG_COLUMNS)
