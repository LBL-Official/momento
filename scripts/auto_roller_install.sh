#!/bin/bash
# Install AUTO ROLLER VERIFY (00:00 local) and INGEST (02:00 local).
# Does not claim a missed job ran. RunAtLoad is false.
set -euo pipefail
ROOT="/Users/user/Desktop/Momento"
ROLLER="$ROOT/ROLLER"
PY="$ROLLER/.venv/bin/python"
export PYTHONPATH="$ROLLER"
cd "$ROLLER"
"$PY" - <<'PY'
from roller.auto_roller.scheduler import INGEST_LABEL, VERIFY_LABEL, install_plists, launch_agents_dir
from pathlib import Path
import subprocess

written = install_plists()
agents = launch_agents_dir()
for label, path in written.items():
    dest = Path(path)
    subprocess.run(["launchctl", "unload", str(dest)], check=False)
    subprocess.run(["launchctl", "load", str(dest)], check=True)
    print(f"loaded {label} {dest}")
print("VERIFY=00:00 INGEST=02:00")
print("Catch-up: if the Mac slept through the hour, launchd may run on wake.")
print("Jobs pass --missed-schedule only when the wrapper detects a late start.")
PY
