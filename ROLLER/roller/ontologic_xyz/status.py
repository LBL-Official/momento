"""Joint X/Y status. No average, and no probability when either side is missing."""

from __future__ import annotations

import json
from typing import Any

from roller.ontologic_xyz.probe import probe_path


def joint_status(day: str, probe: dict[str, Any] | None = None) -> dict[str, Any]:
    from roller.ontologic_y.capability import capability_matrix

    if probe is None:
        path = probe_path(day)
        if path.is_file():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            probe = loaded if isinstance(loaded, dict) else {}
        else:
            probe = {"status": "SOURCE_UNAVAILABLE", "quotes": []}
    x_status = str(probe.get("status") or "SOURCE_UNAVAILABLE")
    y_ready = any(row.get("status") == "OBSERVED" for row in capability_matrix())
    y_status = "OBSERVED" if y_ready else "MARKET_MODEL_UNAVAILABLE"
    return {
        "date": day,
        "live_execution": False,
        "submits": False,
        "x": {
            "role": "sportsbook quote",
            "provider": "the_odds_api",
            "bookmaker": probe.get("bookmaker") or "williamhill",
            "status": x_status,
            "quote_count": len(probe.get("quotes") or []),
        },
        "y": {
            "role": "in-house probability",
            "status": y_status,
        },
        "z": {
            "role": "joint calibration",
            "status": "NOT_CALIBRATED",
            "method": "JOINT_CALIBRATION_NOT_AN_AVERAGE",
            "probability": None,
            "reason": "Z waits for an observed X quote and an observed Y probability on the same game.",
        },
    }
