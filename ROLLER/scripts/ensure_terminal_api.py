"""Start the terminal API only if :8791 is not already healthy.

Does not kill, restart, or reclaim a running process.
The frontend must never invoke this.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

HOST = "127.0.0.1"
PORT = 8791
HEALTH = f"http://{HOST}:{PORT}/health"


def healthy() -> bool:
    try:
        with urllib.request.urlopen(HEALTH, timeout=2) as resp:
            if resp.status != 200:
                return False
            body = json.loads(resp.read().decode())
            return body.get("status") == "ok"
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return False


def main() -> int:
    if healthy():
        print(f"API_REACHABLE {HEALTH} — using existing process. Not started. Not killed.", flush=True)
        return 0
    print(f"API_UNREACHABLE {HEALTH} — starting scripts/terminal_api.py", flush=True)
    from terminal_api import main as run_api

    run_api()
    return 0


if __name__ == "__main__":
    sys.exit(main())
