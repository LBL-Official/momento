#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from roller.canonical.identity_build import build_identity
from roller.config import RollerConfig


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    p.add_argument("--sport", action="append")
    args = p.parse_args()
    df = build_identity(RollerConfig(Path(args.root)), sports=args.sport)
    print(f"identity rows={len(df)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
