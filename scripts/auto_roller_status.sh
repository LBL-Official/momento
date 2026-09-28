#!/bin/bash
set -euo pipefail
ROLLER="/Users/user/Desktop/Momento/ROLLER"
export PYTHONPATH="$ROLLER"
cd "$ROLLER"
"$ROLLER/.venv/bin/python" -m roller.auto_roller status
echo "--- launchctl ---"
launchctl list | grep -F auto-roller || echo "no auto-roller agents loaded"
