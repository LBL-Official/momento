#!/usr/bin/env bash
# Start the local research API + console. Research only. No live orders.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export MOMENTO_ROOT="$ROOT"
export MOMENTO_RESEARCH_TOKEN="${MOMENTO_RESEARCH_TOKEN:-momento-local}"
export MOMENTO_RESEARCH_BIND="${MOMENTO_RESEARCH_BIND:-127.0.0.1:8787}"

echo "building momento-research-api"
cargo build -p momento-research-api

echo "API on $MOMENTO_RESEARCH_BIND (token=$MOMENTO_RESEARCH_TOKEN)"
cargo run -p momento-research-api &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT

cd "$ROOT/frontend/research-console"
if [[ ! -d node_modules ]]; then
  npm install
fi
echo "console on http://127.0.0.1:5173"
npm run dev
