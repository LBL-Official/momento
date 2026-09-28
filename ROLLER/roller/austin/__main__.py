"""python -m roller.austin"""

from __future__ import annotations

import json

from roller.austin.build import run_build
from roller.austin.paths import summary_path


def main() -> None:
    summary = run_build()
    print(json.dumps(
        {
            "ok": True,
            "n_trades": summary.get("coverage", {}).get("n_trades"),
            "n_knn_observations": summary.get("coverage", {}).get("n_knn_observations"),
            "path": str(summary_path()),
            "live_feed": summary.get("live_feed"),
            "calibration": (summary.get("walkforward") or {}).get("calibration", {}).get("status"),
        },
        indent=2,
    ))


if __name__ == "__main__":
    main()
