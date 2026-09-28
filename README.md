# Momento

Production-grade algorithmic sports prediction and execution platform.

MLB is first. Live trading is disabled. See [`AGENTS.md`](AGENTS.md) and
[`docs/architecture/`](docs/architecture/).

## Workspace

Rust workspace. Trading dashboard is a later milestone.

Internal **research console** (not the public website):

```sh
./scripts/dev-research.sh
```

See [`docs/architecture/current-state.md`](docs/architecture/current-state.md)
and [`docs/research/RESEARCH_ENGINE_V1.md`](docs/research/RESEARCH_ENGINE_V1.md).

```text
apps/           trading-engine, replay-engine
crates/         core, risk, execution, positions, kalshi, ...
strategies/mlb  unimplemented (emits no intents)
config/         paper by default; live cannot be armed
```

## Commands

```sh
cargo test
cargo clippy --workspace --all-targets -- -D warnings
```

Do not place live orders. Do not add credentials.
