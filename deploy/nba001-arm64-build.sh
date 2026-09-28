#!/usr/bin/env bash
# Build and verify the NBA Bot 001 worker on a throwaway ARM64 Amazon Linux host.
# Do not cross-compile from macOS. The order adapter is linked for fixture and
# demo use only; the build fails unless production submission is compiled out.
set -euo pipefail

ROOT="${1:-.}"
OUT_DIR="${2:-/tmp/nba001}"
BUILD_ID="${3:-$(date -u +%Y%m%dT%H%M%SZ)}"
cd "$ROOT"

test "$(uname -m)" = aarch64
test -f apps/nba-001/Cargo.toml
test -f config/nba-001.toml
test -f research/vital/bots/nba-001/strategy/execution_contract.json

grep -q 'pub const PRODUCTION_ORDERS_COMPILED: bool = false;' apps/nba-001/src/venue.rs
grep -q 'const _: () = assert!(!PRODUCTION_ORDERS_COMPILED);' apps/nba-001/src/venue.rs
if grep -rqE 'ProductionTradingTransport|NbaVenue::production|place_order' apps/nba-001/src strategies/nba/src; then
  echo "BUILD_FAIL production order path found in NBA worker" >&2
  exit 1
fi

cargo test -p momento-strategy-nba
cargo test -p momento-nba-001
cargo test -p momento-kalshi --test production_auth production_observe_is_get_only
NBA001_BUILD_ID="$BUILD_ID" cargo build --release -p momento-nba-001

BIN=target/release/momento-nba-001
file "$BIN" | grep -q "ARM aarch64"
"$BIN" --version | grep -q "$BUILD_ID"
"$BIN" --version | grep -q "production_orders_compiled=false"
mkdir -p "$OUT_DIR"
cp -a "$BIN" "$OUT_DIR/momento-nba-001"
cp -a config/nba-001.toml "$OUT_DIR/nba-001.toml"
cp -a research/vital/bots/nba-001/strategy/execution_contract.json "$OUT_DIR/execution_contract.json"
cp -a deploy/momento-nba-001.service deploy/nba001-fetch-secret.sh deploy/nba001-atomic-deploy.sh "$OUT_DIR/"
(cd "$OUT_DIR" && sha256sum momento-nba-001 nba-001.toml execution_contract.json momento-nba-001.service nba001-fetch-secret.sh nba001-atomic-deploy.sh | tee SHA256)
echo "BUILD_OK build_id=$BUILD_ID"
