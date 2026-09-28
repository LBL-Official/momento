"""CLI: validate Phase 0 sample research_specs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from roller.dashboard_adapter.research_object import SAMPLES_DIR, validate_research_spec


def main() -> int:
    paths = sorted(SAMPLES_DIR.glob("*.json"))
    if not paths:
        print("No samples found", file=sys.stderr)
        return 1
    failed = 0
    for path in paths:
        spec = json.loads(path.read_text(encoding="utf-8"))
        result = validate_research_spec(spec)
        status = "RUNNABLE" if result.runnable else ("VALID_UNRESOLVED" if result.ok else "INVALID")
        print(f"{path.name}: schema_ok={result.ok} status={status} id={result.research_object_id}")
        if result.errors:
            for err in result.errors:
                print(f"  ERROR: {err}")
            failed += 1
        if result.unresolved:
            print(f"  unresolved: {result.unresolved}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
