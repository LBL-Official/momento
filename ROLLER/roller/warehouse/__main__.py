"""CLI: python -m roller.warehouse validate | gap_audit"""

from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m roller.warehouse")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate", help="validate declared datasets that exist on disk")
    sub.add_parser("gap_audit", help="machine-readable coverage / gap report")
    args = parser.parse_args(argv)
    if args.cmd == "validate":
        from roller.warehouse.validate_cmd import run_validate

        print(json.dumps(run_validate(), indent=2))
        return 0
    if args.cmd == "gap_audit":
        from roller.warehouse.gap_audit import run_audit

        print(json.dumps(run_audit(), indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
