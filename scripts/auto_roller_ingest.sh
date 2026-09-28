#!/bin/bash
# 02:00 AUTO ROLLER INGEST. Do not describe this as midnight.
set -euo pipefail
ROLLER="/Users/user/Desktop/Momento/ROLLER"
export PYTHONPATH="$ROLLER"
cd "$ROLLER"
extra=()
hour="$(date +%H)"
if [ "$hour" != "02" ]; then
  extra+=(--missed-schedule)
fi
exec "$ROLLER/.venv/bin/python" -m roller.auto_roller.ingest --skip-indexes "${extra[@]}"
