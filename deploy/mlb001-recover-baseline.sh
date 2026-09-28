#!/usr/bin/env bash
# Recover the frozen MLB 001 production baseline onto this host.
# Operator SSM only. Never VITAL_AWS_CONTROL. Never edit live.toml.
# Does not roll back fb939b62. Process up is not success.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
IDENTITY="${HERE}/mlb001-production-baseline.json"
EXPECTED="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["binary"]["sha256"])' "$IDENTITY")"
SRC="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["binary"]["artifact"])' "$IDENTITY")"
HIST="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["historical_not_baseline"]["sha256"])' "$IDENTITY")"

test "$EXPECTED" != "$HIST"
test "$EXPECTED" = "66ca5420273779b6706e873c4a6640ef4fd603dd0bb02e9d044ee18077c2f3fd"

exec "$HERE/mlb001-atomic-deploy.sh" "$EXPECTED" "$SRC"
