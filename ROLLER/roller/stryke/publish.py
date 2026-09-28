"""Point the labelled sheet through SuperASI into a Jump folder. No T40 decompose."""

from __future__ import annotations

import json
from typing import Any

from roller.choosin_texas.first78.membership import MEMBERSHIP_N, load_membership
from roller.stryke.artifact import FOLDER_ID, jump_pointer_path, signal_path, write_signal
from roller.superasi.library import write_package
from roller.superasi.package import new_package


def membership_trades() -> list[dict[str, Any]]:
    """Identity rows already on disk. Exits stay unset so T40 is not implied."""
    rows: list[dict[str, Any]] = []
    for member in load_membership():
        rows.append(
            {
                "ticker": member["ticker"],
                "sport": member["sport"],
                "slice": member["slice"],
                "internal_game_id": member.get("event_id") or None,
                "price_basis": "YES_BID_CLOSE",
            }
        )
    if len(rows) != MEMBERSHIP_N:
        raise ValueError(f"membership {len(rows)} != {MEMBERSHIP_N}")
    return rows


def publish() -> dict[str, Any]:
    signal = write_signal()
    trades = membership_trades()
    pkg, norm = new_package(
        source="roller_generic",
        trades=trades,
        package_id=FOLDER_ID,
        research_object_id=FOLDER_ID,
        name="FIRST78 78/67",
        research_spec={
            "identity": {"name": "FIRST78 78/67"},
            "population_binding": {"leagues": ["NBA", "NCAAB"]},
            "signal_artifact": "research/stryke/first78_67/signal.json",
            "role": "membership pointer, not the Stryke sheet",
        },
        caveats=[
            "Membership pointer, not the signal sheet. Touch (N) stays 1.",
            "T40 decomposer was not run. A 67 stop is not a 40 stop.",
        ],
        dataset_version="DERIVED_FOUR_FIRST78",
        trade_origin="choosin_texas.first78.membership",
    )
    written = write_package(pkg, norm, windows=[], decomp=None, replace=True)
    pointer = {
        "folder_id": FOLDER_ID,
        "label": "FIRST78 78/67",
        "package_id": FOLDER_ID,
        "package_path": "research/superasi/library/FIRST78_67",
        "signal_artifact": "research/stryke/first78_67/signal.json",
        "population_n": pkg["population_n"],
        "population_note": "Derived-four membership pointer. Not Touch (N).",
        "live_execution": False,
        "note": "Pointer. Not a warehouse copy.",
    }
    dest = jump_pointer_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(pointer, indent=2) + "\n", encoding="utf-8")
    return {
        "signal": str(signal_path().relative_to(signal_path().parents[3])),
        "package": written,
        "jump": str(dest.relative_to(dest.parents[3])),
        "touch_n": "1",
        "membership_n": pkg["population_n"],
        "live_execution": False,
    }
