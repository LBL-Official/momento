"""Labelled FIRST78 78/67 signal sheet. The sheet numbers are not the population N."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LABEL = "FIRST78_67"
FOLDER_ID = "FIRST78_67"
SHEET_ROWS: tuple[tuple[str, str], ...] = (
    ("Entry", "78"),
    ("Exit", "67"),
    ("Top Out", "85"),
    ("Touch (N)", "1"),
    ("Batch (N)", "10"),
    ("Allocation", "0.06"),
    ("Hedge", "Limit @ 68"),
    ("Hedge Path", "68,67,66,65,64,63,62,61,60,59,58,57,56,55"),
    ("Market Dump", "<55"),
    ("Ontologic", "[Placeholder]"),
    ("TK Ultra", "[Placeholder]"),
    ("Ball Hog", "[Placeholder]"),
    ("Choosin Texas", "[Placeholder]"),
    ("Austin", "[Placeholder]"),
    ("Positman", "[Placeholder]"),
    ("Drevo", "[Placeholder]"),
)
PLACEHOLDER_LABELS = (
    "Ontologic",
    "TK Ultra",
    "Ball Hog",
    "Choosin Texas",
    "Austin",
    "Positman",
    "Drevo",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def signal_path() -> Path:
    return repo_root() / "research" / "stryke" / "first78_67" / "signal.json"


def jump_pointer_path() -> Path:
    return repo_root() / "research" / "jump" / "signals" / FOLDER_ID / "signal.json"


def sheet_rows() -> list[dict[str, str]]:
    return [{"label": label, "value": value} for label, value in SHEET_ROWS]


def _pointers() -> dict[str, Any]:
    from roller.austin_first78.config import CFG
    from roller.austin_first78.paths import summary_path
    from roller.austin_first78.store import load_json
    from roller.choosin_texas.first78.artifact import load_derived
    from roller.choosin_texas.first78.desk import present_derived

    summary = load_json(summary_path()) or {}
    coverage = summary.get("coverage") if isinstance(summary.get("coverage"), dict) else {}
    austin_n = coverage.get("n_trades")
    presented = present_derived(load_derived())
    universe = presented.get("universe") if isinstance(presented.get("universe"), dict) else {}
    return {
        "choosin": {
            "universe": presented.get("population_id"),
            "n": universe.get("n"),
            "note": "Qualified 78¢ count. Not Touch (N). Not Austin training N.",
        },
        "austin": {
            "universe": CFG.dataset_version,
            "n": austin_n,
            "note": "Austin 78/67 fit. Not Touch (N). Not the qualified count.",
        },
    }


def build_signal() -> dict[str, Any]:
    return {
        "label": LABEL,
        "folder_id": FOLDER_ID,
        "product": "Stryke",
        "system_id": "signal_generation",
        "strategy_id": "FIRST78_67",
        "live_execution": False,
        "submits": False,
        "execution_authorized": False,
        "candle_path_is_fill": False,
        "allocation_note": "Signal spec. Does not change Risk or the Choosin 6% cap.",
        "rows": sheet_rows(),
        "pointers": _pointers(),
    }


def write_signal(body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = body or build_signal()
    dest = signal_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def load_signal() -> dict[str, Any]:
    path = signal_path()
    if not path.is_file():
        raise FileNotFoundError(path)
    body = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(body, dict):
        raise ValueError("signal artifact is not an object")
    return body
