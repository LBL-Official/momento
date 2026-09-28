#!/bin/bash
# 00:00 AUTO ROLLER VERIFY. Late start is MISSED_SCHEDULE, not a silent success.
set -euo pipefail
ROLLER="/Users/user/Desktop/Momento/ROLLER"
export PYTHONPATH="$ROLLER"
cd "$ROLLER"
extra=()
hour="$(date +%H)"
if [ "$hour" != "00" ]; then
  extra+=(--missed-schedule)
fi
exec "$ROLLER/.venv/bin/python" -m roller.auto_roller.verify --fast "${extra[@]}"
