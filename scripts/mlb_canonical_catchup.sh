#!/bin/bash
# After Kalshi candle sidecars finish landing, rebuild MLB canonical + observation indexes.
# Does not start a second backfill. Does not invent yes_bid. Does not touch live trading.
trap '' HUP
set -u
ROOT="/Users/user/Desktop/Momento"
ROLLER="$ROOT/ROLLER"
LAND="$ROOT/Backtesting Suite/Foundation/Ingest/landing"
LOG="/tmp/mlb-canonical-catchup.log"
DEADLINE=$(( $(date +%s) + 12 * 3600 ))
PY="$ROLLER/.venv/bin/python"

sidecar_count() {
  find "$1" -name "$2" 2>/dev/null | wc -l | tr -d ' '
}

ingest_running() {
  pgrep -f 'momento-research-ingest (backfill|run|weekly)' >/dev/null
}

watchdog_running() {
  pgrep -f 'mlb_kalshi_backfill_watchdog.sh' >/dev/null
}

log() {
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" | tee -a "$LOG"
}

cd "$ROOT" || exit 1
log "catchup start deadline=$(date -u -r "$DEADLINE" +%Y-%m-%dT%H:%M:%SZ)"

while true; do
  trades=$(sidecar_count "$LAND/kalshi_historical_trades" "*.trades.json")
  candles=$(sidecar_count "$LAND/kalshi_historical_candles" "*.candles.json")
  now=$(date +%s)
  running=0
  ingest_running && running=1
  wd=0
  watchdog_running && wd=1
  log "wait trades=$trades candles=$candles ingest=$running watchdog=$wd"
  if [ "$candles" -ge "$trades" ] && [ "$trades" -gt 0 ] && [ "$running" -eq 0 ]; then
    log "sidecars matched; ingest idle"
    break
  fi
  if [ "$now" -ge "$DEADLINE" ]; then
    log "deadline reached; ingesting landed candles as-is trades=$trades candles=$candles"
    break
  fi
  sleep 120
done

# Do not overlap a still-running authorized backfill.
if ingest_running; then
  log "backfill still running after wait; sleeping until it exits"
  while ingest_running; do
    sleep 60
  done
fi

log "canonical ingest start"
if ! (cd "$ROLLER" && PYTHONUNBUFFERED=1 "$PY" -u -m roller.mlb.ingest >>"$LOG" 2>&1); then
  log "FAIL canonical ingest"
  exit 1
fi
log "canonical ingest done"

log "rebuild MLB last_trade index"
if ! (cd "$ROLLER" && PYTHONUNBUFFERED=1 "$PY" -u -m roller.research_query.indexes build \
  --league MLB --season 2025-2026 --basis LAST_TRADE_PRINT >>"$LOG" 2>&1); then
  log "FAIL last_trade index"
  exit 1
fi

log "rebuild MLB tradable index"
if ! (cd "$ROLLER" && PYTHONUNBUFFERED=1 "$PY" -u -m roller.research_query.indexes build \
  --league MLB --season 2025-2026 --basis TRADABLE_YES_BID >>"$LOG" 2>&1); then
  log "FAIL tradable index"
  exit 1
fi

log "golden compile + warehouse identity"
(cd "$ROLLER" && "$PY" -m pytest tests/test_mlb_golden_fixture.py -q --tb=line >>"$LOG" 2>&1) || log "golden test reported failure (coverage may have changed)"

log "catchup complete"
exit 0
