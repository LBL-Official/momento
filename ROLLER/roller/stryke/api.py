"""HTTP handlers for Stryke. Reads the Jump folder. Does not submit."""

from __future__ import annotations

from typing import Any

from roller.stryke.artifact import FOLDER_ID, load_signal


def handle_health() -> dict[str, Any]:
    try:
        signal = load_signal()
        book = signal.get("label")
    except (OSError, ValueError):
        book = "UNAVAILABLE"
    return {
        "ok": book == FOLDER_ID,
        "product": "Stryke",
        "system_id": "signal_generation",
        "book": book,
        "live_execution": False,
        "submits": False,
        "execution_authorized": False,
        "candle_path_is_fill": False,
    }


def handle_folders() -> dict[str, Any]:
    from roller.jump.research import scan_superasi_folders

    folders: list[dict[str, Any]] = []
    for scan in scan_superasi_folders():
        if scan.package_id != FOLDER_ID and scan.folder_name != FOLDER_ID:
            continue
        folders.append(
            {
                "folder_id": FOLDER_ID,
                "display_name": scan.identity_name or scan.name or FOLDER_ID,
                "path": scan.folder_path,
                "jump_pointer": "research/jump/signals/FIRST78_67/signal.json",
                "population_n": scan.population_n,
                "population_note": "Derived-four membership pointer. Not Touch (N).",
                "live_execution": False,
            }
        )
    return {"folders": folders, "live_execution": False}


def handle_signal(folder_id: str) -> dict[str, Any]:
    if str(folder_id) != FOLDER_ID:
        return {
            "status": "UNAVAILABLE",
            "folder_id": folder_id,
            "detail": "Stryke reads the FIRST78_67 Jump folder.",
            "live_execution": False,
        }
    body = load_signal()
    body["status"] = "OBSERVED"
    return body
