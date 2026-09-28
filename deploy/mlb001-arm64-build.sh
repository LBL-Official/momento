#!/usr/bin/env bash
# Build and verify the MLB 001 live binary on an ARM64 Amazon Linux host.
# Do not cross-compile from macOS. Do not treat this as a submit gate.
set -euo pipefail

ROOT="${1:-.}"
OUT_DIR="${2:-/tmp/mlb001-engine}"
cd "$ROOT"

test "$(uname -m)" = aarch64
test -f crates/core/src/fill.rs
test -f config/live.toml

grep -q same_venue_event crates/core/src/fill.rs
grep -q recon_cleared apps/trading-engine/src/live.rs
grep -q run_desk_housekeeping apps/trading-engine/src/live.rs
grep -q leftover_fill crates/positions/src/tracker.rs || grep -q "already-complete order" crates/positions/src/tracker.rs

cargo test -p momento-positions --test tracker leftover
cargo test -p momento-positions --test tracker incremental_fill
cargo test -p momento-risk --test open_position_cap adopt_
cargo test -p momento-trading-engine --test live_host leftover_integer_fill -- --test-threads=1
cargo test -p momento-trading-engine --test live_host housekeeping_gates -- --test-threads=1
cargo test -p momento-trading-engine --test live_host fill -- --test-threads=1
cargo build --release -p momento-trading-engine

BIN=target/release/momento-trading-engine
file "$BIN" | grep -q "ARM aarch64"
mkdir -p "$OUT_DIR"
cp -a "$BIN" "$OUT_DIR/momento-trading-engine"
sha256sum "$BIN" | tee "$OUT_DIR/SHA256"
echo BUILD_OK
