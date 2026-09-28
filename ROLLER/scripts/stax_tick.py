"""CLI wrapper for STAX due-run tick. Same function as POST /stax/automation/tick."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from roller.stax.automation import tick


def main() -> None:
    print(json.dumps(tick(), indent=2))


if __name__ == "__main__":
    main()
