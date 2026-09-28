#!/usr/bin/env python3
"""CLI: A1 Hybrid Hedge Optimization research runner."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from a1_hybrid_hedge.reporting import write_report  # noqa: E402
from a1_hybrid_hedge.runner import run_all  # noqa: E402
from a1_hybrid_hedge.test_a1_invariants import (  # noqa: E402
    test_gap_does_not_fill,
    test_lock_identity,
    test_no_opportunity,
    test_observed_price_not_normalized,
)


def main() -> int:
    test_gap_does_not_fill()
    test_observed_price_not_normalized()
    test_no_opportunity()
    test_lock_identity()
    print("invariants ok", flush=True)
    out = run_all()
    write_report(out["sports"], out["dash"]["meta"])
    print(json.dumps({"docs": out["docs"], "dashboard": out["dashboard"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
