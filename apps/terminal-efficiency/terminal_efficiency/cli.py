from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="terminal_efficiency", description="Terminal Efficiency Phases 0–6")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_ls(sp):
        sp.add_argument("--league", required=True, choices=["NBA", "NCAAB"])
        sp.add_argument("--season", default="2024-2025")

    add_ls(sub.add_parser("ingest"))
    sub.choices["ingest"].add_argument("--kalshi-live", action="store_true")
    sub.choices["ingest"].add_argument("--ncaab-max-days", type=int, default=None)
    add_ls(sub.add_parser("build-states"))
    add_ls(sub.add_parser("audit-leakage"))
    add_ls(sub.add_parser("train-xib"))
    sub.choices["train-xib"].add_argument("--freeze", action="store_true")
    add_ls(sub.add_parser("train-mcd"))
    add_ls(sub.add_parser("apply-candles"))
    insp = sub.add_parser("inspect-frozen")
    add_ls(insp)
    insp.add_argument("--model-version", default=None)
    ev = sub.add_parser("evaluate")
    ev.add_argument("--season", required=True)

    args = p.parse_args(argv)
    try:
        if args.cmd == "inspect-frozen":
            from terminal_efficiency.consume import inspect_frozen

            out = inspect_frozen(args.league, args.season, model_version=args.model_version)
        else:
            from terminal_efficiency.pipeline import (
                apply_candles,
                audit_leakage,
                build_states,
                evaluate_oos,
                ingest,
                train_mcd,
                train_xib,
            )

            if args.cmd == "ingest":
                out = ingest(
                    args.league,
                    args.season,
                    kalshi_dry_run=not args.kalshi_live,
                    ncaab_max_days=args.ncaab_max_days,
                )
            elif args.cmd == "build-states":
                out = build_states(args.league, args.season)
            elif args.cmd == "audit-leakage":
                out = audit_leakage(args.league, args.season)
            elif args.cmd == "train-xib":
                out = train_xib(args.league, args.season, freeze=args.freeze)
            elif args.cmd == "train-mcd":
                out = train_mcd(args.league, args.season)
            elif args.cmd == "apply-candles":
                out = apply_candles(args.league, args.season)
            elif args.cmd == "evaluate":
                evaluate_oos(args.season)
                out = {}
            else:
                p.error("unknown command")
                return 2
    except Exception as exc:
        from terminal_efficiency.consumption.errors import (
            ConsumptionForbidden,
            FrozenUnavailable,
            ProvenanceRequired,
        )

        name = type(exc).__name__
        if name == "LeakageAuditFailed":
            print("LEAKAGE AUDIT FAIL", exc, file=sys.stderr)
            return 2
        if name == "Phase7NotAuthorized":
            print(exc, file=sys.stderr)
            return 3
        if isinstance(exc, FrozenUnavailable):
            print(f"UNAVAILABLE: {exc}", file=sys.stderr)
            return 4
        if isinstance(exc, (ConsumptionForbidden, ProvenanceRequired)):
            print(exc, file=sys.stderr)
            return 3
        raise
    print(json.dumps(out, indent=2, default=str)[:8000])
    return 0
