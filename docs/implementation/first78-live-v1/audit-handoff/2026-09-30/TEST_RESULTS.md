# Test results — recorded 2026-09-30

Toolchain: Rust 1.98.0 / cargo 1.98.0 from `rust-toolchain.toml`.
Commands used `--locked` and `--offline` on the authoring workstation after implementation commit `2a22a2a2f7797f9d54b6372c6f4f8ccb5379bcc2` (same tree; tests were run immediately before that commit).

## Predeclared expected outcome

Local NBA + Kalshi crates stay green. Production send remains compiled out. No fabricated fills. Ignored tests stay ignored.

## Observed

| Command | Result |
|---|---|
| `cargo test --locked -p momento-strategy-nba` | **121 passed** (lib 8, first78 61, live_v1 4, live_v1_exits 7, orders 35, sizing_epoch 6) |
| `cargo test --locked -p momento-nba-001` | **67 passed, 1 ignored** (`tests::real_candles_replay_through_cross_tracker`) |
| `cargo test --locked -p momento-kalshi` | **18 passed** (14 lib + 4 sandbox) |
| `python3 ROLLER/roller/systimo/nba001_v1.py` | pass (`nba001_v1_self_test_ok`) |
| `ROLLER/.venv` pytest `test_systimo_v1.py` | **not run** — venv absent |

Combined strategy + worker: **188 passed, 1 ignored**. Incoming merge baseline was 170 + 1 ignored.

## Ignored / skipped

- `real_candles_replay_through_cross_tracker` — existing ignore; needs a local candle dump, not invented.
- Full ROLLER pytest suite — no project venv on the authoring Mac.
- Systimo UI browser pass — `:8791` and `:5193` were down.

## Known untested (do not treat as green)

- Kalshi demo E2E of the V1 supervisor
- Production-credential recorded-feed replay
- ARM64 **release** binary of commit `2a22a2a` on the host (not built, not installed)
- p50/p95/p99 latency — see `docs/implementation/first78-live-v1/PERFORMANCE.md` (not measured)
- Signed whole-account V1 recon vs host GET heartbeat
- Restart/reboot of the V1 supervisor (not deployed). FIRST78_67 `Restart=always` / exit 78 is **configured**, not re-proven in this handoff
- Destructive disk-full / fsync-error on the live host (forbidden while MLB is Live)

## Failures

None in the commands that were run.
