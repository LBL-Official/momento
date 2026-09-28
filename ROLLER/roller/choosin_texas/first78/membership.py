"""Derived-four membership for the FIRST78 ladder. Not the 687-entry ex-ante cohort."""

from __future__ import annotations

import csv
from pathlib import Path

from roller.choosin_texas.models import ChoosinTexasError
from roller.choosin_texas.sources import default_asked_six_csv

SLICES = {
    ("NBA", "Q2"): "Q2",
    ("NBA", "Q3"): "Q3",
    ("NCAAB", "H1_2"): "H1_2",
    ("NCAAB", "H2_1"): "H2_1",
}
MEMBERSHIP_N = 936


def _bool(value: object) -> bool | None:
    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _int(value: object) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def load_membership(path: Path | None = None) -> list[dict]:
    csv_path = path or default_asked_six_csv()
    if not csv_path.is_file():
        raise ChoosinTexasError("DATA_REQUIRED", f"missing {csv_path}")
    rows = []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            key = (str(raw.get("sport") or "").strip(), str(raw.get("slice") or "").strip())
            if key not in SLICES:
                continue
            terminal = _bool(raw.get("terminal_yes"))
            rows.append(
                {
                    "sport": key[0],
                    "slice": SLICES[key],
                    "event_id": str(raw.get("event_id") or ""),
                    "ticker": str(raw.get("ticker") or ""),
                    "side": str(raw.get("side") or "").strip().lower(),
                    "terminal": None if terminal is None else ("yes" if terminal else "no"),
                    "final_home": _int(raw.get("final_score_home")),
                    "final_away": _int(raw.get("final_score_away")),
                }
            )
    if len(rows) != MEMBERSHIP_N:
        raise ChoosinTexasError("LOCK_MISMATCH", f"derived four membership {len(rows)} != {MEMBERSHIP_N}")
    return rows
