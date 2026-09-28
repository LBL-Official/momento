#!/bin/bash
# Daily BetOnline NBA collection for Ontologic X. Research only; does not submit.
# launchd starts this at midnight, at login, and hourly. Only the first complete
# OBSERVED pass of each local day is kept; later checks that day exit at once.
set -u

ROOT="/Users/user/Desktop/Momento"
STAMP="$ROOT/research/ontologic_x/v1/betonline_daily_last_ok"
TODAY="$(date +%Y-%m-%d)"

if [ -f "$STAMP" ] && [ "$(cat "$STAMP")" = "$TODAY" ]; then
  exit 0
fi

cd "$ROOT/ROLLER" || exit 1
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) start local_date=$TODAY"
OUT="$(./.venv/bin/python -m roller.ontologic_x.betonline.collect 2>&1)"
CODE=$?
echo "$OUT"

if [ "$CODE" -eq 0 ] && printf '%s' "$OUT" | grep -q "'status': 'OBSERVED'"; then
  echo "$TODAY" > "$STAMP"
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) done local_date=$TODAY"
else
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) not complete (exit $CODE); the next hourly check retries"
fi
