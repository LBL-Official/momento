# Test run — 2026-09-30

Toolchain: `rust-toolchain.toml` (cargo test --locked --offline).

## Predeclared

Local crate tests must stay green. Production send remains compiled out. No fabricated fills.

## Observed

| Suite | Result |
|---|---|
| `cargo test --locked -p momento-strategy-nba` | 121 passed (lib 8 + first78 61 + live_v1 4 + live_v1_exits 7 + orders 35 + sizing_epoch 6) |
| `cargo test --locked -p momento-nba-001` | 67 passed, 1 ignored (`real_candles_replay_through_cross_tracker`) |
| `cargo test --locked -p momento-kalshi` | 18 passed (14 lib + 4 sandbox) |
| Systimo projection self-test `nba001_v1.py` | pass (missing control room → UNAVAILABLE) |
| `ROLLER/.venv` pytest | not run — venv absent on this workstation |

Combined NBA strategy + worker: **188 passed, 1 ignored**. Incoming baseline was 170 + 1 ignored.

## Not run

- Kalshi demo E2E V1
- Recorded-feed replay on production credentials
- Host ARM64 release binary
- Performance p50/p95/p99
- Browser verification of Systimo `:5193` (API `:8791` down; no venv)
