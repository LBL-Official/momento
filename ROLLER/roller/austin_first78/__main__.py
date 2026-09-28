"""python -m roller.austin_first78"""

from __future__ import annotations

import json

from roller.austin_first78.build import run_build
from roller.austin_first78.paths import summary_path


def main() -> None:
    summary = run_build()
    coverage = summary.get("coverage") or {}
    print(
        json.dumps(
            {
                "ok": True,
                "n_trades": coverage.get("n_trades"),
                "n_q2": coverage.get("n_q2"),
                "n_q3": coverage.get("n_q3"),
                "n_knn_observations": coverage.get("n_knn_observations"),
                "path": str(summary_path()),
                "model_version": summary.get("model_version"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
