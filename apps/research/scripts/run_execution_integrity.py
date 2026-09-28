#!/usr/bin/env python3
"""CLI: Execution Integrity Engine + DRE_BASELINE_V1."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from execution_integrity_engine.reporting import write_reports  # noqa: E402
from execution_integrity_engine.runner import run_all  # noqa: E402
from execution_integrity_engine.tests import run_unit  # noqa: E402


def main() -> int:
    run_unit()
    out = run_all()
    write_reports(out["sports"], out["dash"]["meta"])
    print(json.dumps({"docs": out["docs"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
