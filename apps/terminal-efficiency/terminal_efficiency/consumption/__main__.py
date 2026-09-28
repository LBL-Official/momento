"""Read-only consumption CLI. Does not import the training pipeline."""

from __future__ import annotations

import argparse
import json
import sys

from terminal_efficiency.consumption.errors import (
    ConsumptionForbidden,
    FrozenUnavailable,
    ProvenanceRequired,
)
from terminal_efficiency.consumption.loader import FrozenObjectLoader
from terminal_efficiency.frozen_artifacts.registry import resolve_published


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="terminal_efficiency.consumption",
        description="Read-only frozen object loader. No train, no Phase 7, no Kalshi join.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_identity(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--league", required=True, choices=["NBA", "NCAAB"])
        sp.add_argument("--season", required=True)
        sp.add_argument("--dataset-version", default=None)
        sp.add_argument("--feature-set-version", default=None)
        sp.add_argument("--model-version", default=None)
        sp.add_argument("--code-version", default=None)
        sp.add_argument("--artifact-manifest-hash", default=None)

    add_identity(sub.add_parser("inspect"))
    load = sub.add_parser("lookup-game")
    add_identity(load)
    load.add_argument("--game-id", required=True)

    args = p.parse_args(argv)
    try:
        identity, _ = resolve_published(
            league=args.league,
            season=args.season,
            dataset_version=args.dataset_version,
            feature_set_version=args.feature_set_version,
            model_version=args.model_version,
            code_version=args.code_version,
            artifact_manifest_hash=args.artifact_manifest_hash,
        )
        loader = FrozenObjectLoader()
        if args.cmd == "inspect":
            out = loader.inspect(identity)
        elif args.cmd == "lookup-game":
            view = loader.lookup_game(identity, args.game_id)
            frame = view.to_frame()
            out = {
                "n": int(len(frame)),
                "prediction_available_n": int(frame["prediction_available"].sum()) if len(frame) else 0,
                "availability_status": frame["availability_status"].value_counts().to_dict() if len(frame) else {},
                "coverage_status": frame["coverage_status"].value_counts().to_dict() if len(frame) else {},
                "sample": frame.head(3).to_dict("records"),
            }
        else:
            p.error("unknown command")
            return 2
    except FrozenUnavailable as exc:
        print(f"UNAVAILABLE: {exc}", file=sys.stderr)
        return 4
    except (ConsumptionForbidden, ProvenanceRequired) as exc:
        print(exc, file=sys.stderr)
        return 3
    print(json.dumps(out, indent=2, default=str)[:8000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
