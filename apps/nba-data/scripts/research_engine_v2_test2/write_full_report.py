#!/usr/bin/env python3
"""Copy the spec report into derived output."""

from __future__ import annotations

import shutil

from common import OUT, SPEC_DIR


def main() -> int:
    src = SPEC_DIR / "NBA_80_40_ENGINE_V2_TEST_2_REPORT.md"
    shutil.copy2(src, OUT / "NBA_80_40_ENGINE_V2_TEST_2_REPORT.md")
    print("copied", src.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
