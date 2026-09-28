#!/bin/bash
# Restart authorized MLB Kalshi backfill until trade + candle sidecars match.
# skip_existing: already-landed ticks/candles are not re-fetched.
trap '' HUP
set -u
ROOT="/Users/user/Desktop/Momento"
BIN="$ROOT/target/release/momento-research-ingest"
LOG="/tmp/mlb-kalshi-backfill.log"
WLOG="/tmp/mlb-kalshi-watchdog.log"
LOCK="$ROOT/Backtesting Suite/Foundation/Ingest/locks/ingest.lock"
LAND="$ROOT/Backtesting Suite/Foundation/Ingest/landing"
cd "$ROOT" || exit 1

sidecar_count() {
  find "$1" -name "$2" 2>/dev/null | wc -l | tr -d ' '
}

clear_stale_lock() {
  if [ -f "$LOCK" ] && ! pgrep -f 'momento-research-ingest (backfill|run|weekly)' >/dev/null; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) removing stale lock" | tee -a "$WLOG" >>"$LOG"
    rm -f "$LOCK"
  fi
}

while true; do
  trades=$(sidecar_count "$LAND/kalshi_historical_trades" "*.trades.json")
  candles=$(sidecar_count "$LAND/kalshi_historical_candles" "*.candles.json")
  if [ "$candles" -ge "$trades" ] && [ "$trades" -gt 0 ]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) complete trades=$trades candles=$candles" | tee -a "$WLOG" >>"$LOG"
    exit 0
  fi
  clear_stale_lock
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) start backfill trades=$trades candles=$candles" | tee -a "$WLOG" >>"$LOG"
  caffeinate -dims "$BIN" backfill \
    --authorize-network ENABLE_RESEARCH_INGEST_NETWORK \
    --window 2025-03-18:2026-09-11 \
    --out "Backtesting Suite/Foundation/Ingest" \
    --lake "Backtesting Suite/Data-Real" >>"$LOG" 2>&1
  code=$?
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) exit=$code; retry in 15s" | tee -a "$WLOG" >>"$LOG"
  sleep 15
done
