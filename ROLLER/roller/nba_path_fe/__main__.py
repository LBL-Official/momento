"""python -m roller.nba_path_fe [--synthetic]"""

from __future__ import annotations

import json
import sys

from roller.nba_path_fe.build import run_synthetic_e2e, run_warehouse
from roller.nba_path_fe.paths import walkforward_summary_path


def main() -> None:
    if "--synthetic" in sys.argv:
        summary = run_synthetic_e2e(leakage=False)
    else:
        summary = run_warehouse(leakage=False, ingest=True)
    print(
        json.dumps(
            {
                "wrote": str(walkforward_summary_path()),
                "source": summary.get("source"),
                "promotion": summary.get("promotion"),
                "pooled": summary.get("pooled"),
                "promotion_blockers": summary.get("promotion_blockers"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
