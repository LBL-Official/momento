#!/usr/bin/env python3
"""Fail-hard future-information leakage audit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from roller.config import RollerConfig
from roller.io_csv import write_json
from roller.validation.leakage import run_leakage


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    p.add_argument("--sport", action="append")
    args = p.parse_args()
    cfg = RollerConfig(Path(args.root))
    report = run_leakage(cfg, sports=args.sport)
    write_json(cfg.root / "reports" / "integrity" / "leakage.json", report)
    print(json.dumps({"status": report["status"], "n_errors": len(report["errors"])}, indent=2))
    for e in report["errors"]:
        print(f"ERROR {e}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
