"""Read Phase 3 CSVs. UNAVAILABLE stays missing. Never zero-fill."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from roller.austin.experiments.hazard.ids import NOT_APPLICABLE, UNAVAILABLE
from roller.austin.experiments.persistence.util import as_float


def parse_cell(value: object) -> Any:
    if value is None or value == "" or value == UNAVAILABLE:
        return None
    if value == NOT_APPLICABLE:
        return NOT_APPLICABLE
    if isinstance(value, bool):
        return value
    text = str(value).strip()
    if text in {"True", "true"}:
        return True
    if text in {"False", "false"}:
        return False
    num = as_float(text)
    if num is not None and text.replace(".", "", 1).replace("-", "", 1).replace("e", "", 1).replace("E", "", 1).replace("+", "", 1).isdigit() or (
        num is not None and any(ch.isdigit() for ch in text)
    ):
        if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
            return int(text)
        return num
    return text


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return [{k: parse_cell(v) for k, v in row.items()} for row in csv.DictReader(fh)]
