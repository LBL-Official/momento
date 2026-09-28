#!/bin/zsh
# Detached, caffeinated, resumable NBA PBP overnight ingest.
set -euo pipefail
ROOT="/Users/user/Desktop/Momento"
PY="/tmp/momento-nba-venv/bin/python"
SCRIPT="$ROOT/apps/nba-data/scripts/nba_pbp_overnight_ingest.py"
LOG="$ROOT/Backtesting Suite/Data/NBA/2025-2026/warehouse/manifests/nba/pbp_ingest.nohup.log"
PIDFILE="$ROOT/Backtesting Suite/Data/NBA/2025-2026/warehouse/manifests/nba/pbp_ingest.launch.pid"

mkdir -p "$(dirname "$LOG")"

# Kill prior ingest python only (not other python).
if pgrep -f 'nba_pbp_overnight_ingest.py' >/dev/null 2>&1; then
  pkill -f 'nba_pbp_overnight_ingest.py' || true
  sleep 1
fi

# -d idle sleep, -i idle sleep, -m disk sleep, -s system sleep (AC).
nohup caffeinate -dims "$PY" -u "$SCRIPT" >>"$LOG" 2>&1 &
echo $! >"$PIDFILE"
echo "launched pid=$(cat "$PIDFILE") log=$LOG"
