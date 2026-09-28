#!/bin/bash
# Live MLB orderbook snapshots. Research only. Not L2 reconstruction.
trap '' HUP
set -u
ROOT="/Users/user/Desktop/Momento"
ROLLER="$ROOT/ROLLER"
LOG="/tmp/mlb-orderbook-live.log"
cd "$ROLLER" || exit 1
while true; do
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) orderbook loop start" >>"$LOG"
  /usr/bin/caffeinate -dims "$ROLLER/.venv/bin/python" -u scripts/ingest_orderbook_snapshots.py \
    --root "$ROLLER" --sport MLB --interval-seconds 60 >>"$LOG" 2>&1
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) orderbook exit=$?; restart in 5s" >>"$LOG"
  sleep 5
done
