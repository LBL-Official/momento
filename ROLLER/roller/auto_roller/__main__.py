"""python -m roller.auto_roller status|verify|ingest"""

from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m roller.auto_roller")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    v = sub.add_parser("verify")
    v.add_argument("--fast", action="store_true")
    v.add_argument("--missed-schedule", action="store_true")
    i = sub.add_parser("ingest")
    i.add_argument("--skip-indexes", action="store_true")
    i.add_argument("--missed-schedule", action="store_true")
    args = p.parse_args(argv)
    if args.cmd == "status":
        from roller.auto_roller.status import status_payload

        print(json.dumps(status_payload(), indent=2))
        return 0
    if args.cmd == "verify":
        from roller.auto_roller.verify import run_verify

        rec = run_verify(semantic=not args.fast, missed_schedule=args.missed_schedule)
        print(json.dumps(rec, indent=2))
        return 0 if rec["status"] == "COMPLETE" else 1
    if args.cmd == "ingest":
        from roller.auto_roller.ingest import run_ingest

        rec = run_ingest(rebuild_indexes=not args.skip_indexes, missed_schedule=args.missed_schedule)
        print(json.dumps(rec, indent=2))
        return 0 if rec["status"] != "FAILED" else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
