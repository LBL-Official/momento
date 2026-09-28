#!/usr/bin/env python3
"""Fail-hard integrity validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from roller.config import RollerConfig
from roller.io_csv import write_json
from roller.validation.integrity import run_integrity
from roller.validation.v4b_leakage import run_v4b_validate
from roller.validation.v4c_constructibility import run_v4c_constructibility_validate
from roller.validation.v4c_information_regime import run_v4c_information_regime_validate
from roller.validation.v4c_measurement_identity import run_v4c_identity_validate


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    p.add_argument("--sport", action="append")
    args = p.parse_args()
    cfg = RollerConfig(Path(args.root))
    report = run_integrity(cfg, sports=args.sport)
    out = cfg.root / "reports" / "integrity" / "integrity.json"
    write_json(out, report)
    print(json.dumps({"status": report["status"], "n_errors": len(report["errors"])}, indent=2))
    for e in report["errors"]:
        print(f"ERROR {e}")
    v4b = run_v4b_validate()
    write_json(cfg.root / "reports" / "integrity" / "v4b.json", v4b)
    print(json.dumps({"v4b_status": v4b["status"], "n_errors": len(v4b["errors"])}, indent=2))
    for e in v4b["errors"]:
        print(f"ERROR {e}")
    v4c_regime = run_v4c_information_regime_validate()
    v4c_cons = run_v4c_constructibility_validate(cfg)
    v4c_ident = run_v4c_identity_validate()
    v4c = {
        "status": "FAIL"
        if v4c_regime["errors"] or v4c_cons["errors"] or v4c_ident["errors"]
        else "PASS",
        "errors": v4c_regime["errors"] + v4c_cons["errors"] + v4c_ident["errors"],
        "information_regime": v4c_regime["status"],
        "constructibility": v4c_cons["status"],
        "identity": v4c_ident["status"],
    }
    write_json(cfg.root / "reports" / "integrity" / "v4c.json", v4c)
    print(json.dumps({"v4c_status": v4c["status"], "n_errors": len(v4c["errors"])}, indent=2))
    for e in v4c["errors"]:
        print(f"ERROR {e}")
    return 0 if report["status"] == "PASS" and v4b["status"] == "PASS" and v4c["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
