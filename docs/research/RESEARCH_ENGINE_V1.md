# Research Engine v1 — operator notes

See also:

- [current-state.md](../architecture/current-state.md)
- [target-state.md](../architecture/target-state.md)

## What this is

A research operating system wrapped around the existing B1 first-exact-83
pipeline. It does **not** change live FIRST01, invent L2, or start W9.

## Start locally

```sh
./scripts/dev-research.sh
```

Console: `http://127.0.0.1:5173`  
API: `http://127.0.0.1:8787`  
Token: `momento-local` (override `MOMENTO_RESEARCH_TOKEN`)

## Locked B1 universe

`B1_FIRST83` / `v1` registers `Backtesting Suite/Foundation/B1/first83/`.
Do not overwrite `B1/features.sqlite` (Universe A, first in-band 80–83).

Canonical event: first exact 83¢ TRADE, W8-bound else earliest.

## FDR warning

Imported experiment `EXP_B1_FIRST83_EXHAUSTIVE_v1` carries q-values from
**6,128 tests**. A new console grid computes FDR only over **that grid**.
A one-cell 40–49 re-run will not reproduce q=0.17.

## CLI

`momento-research-b1` is unchanged for extract/search flags and also accepts
`--run-experiment experiment.json` (same engine as the API).

## Prospective validation (`B1_FIRST83_PROSPECTIVE/v1`)

Existing TEST through `2026-06-27` is **LOCKED / CONSUMED**. Frozen candidates
A–F are scored only on games strictly after that cutoff.

```sh
./target/release/momento-research-b1 --prospective-83
# aliases: --validate-83-prospective   capital-only: --83-capital-sim
```

Optional: `--prospective-start`, `--prospective-end`, `--candidate-set`,
`--bootstrap`, `--permutations`, `--cost-grid`, `--seed`.

The CLI, `GET /api/prospective83`, and the console `/prospective` page use the
same engine. Historical panel evaluation does not retune on locked TEST.
The holdout remains empty until W7 paths exist after 2026-06-27.

Artifacts: `Backtesting Suite/Foundation/B1/prospective83/`.

If W7 EventMarketPath is not reconstructed after the cutoff, the official
result is `PROSPECTIVE_DATA_NOT_YET_AVAILABLE` / `INSUFFICIENT DATA`.
Do not invent 83¢ TRADE prints from W6 state.

Console: `/prospective`. API: `GET /api/prospective83`.

Layers are labeled separately:

- `FROZEN HISTORICAL RESULT`
- `PROSPECTIVE VALIDATION RESULT`
- `POST_HOLDOUT_DISCOVERY`

`PRODUCTION_COUNT` remains 0. No live FIRST01 / W9 / L2 / orders.

Imported experiment `EXP_B1_FIRST83_EXHAUSTIVE_v1` always pins:

- `start_price_band=40_49` CANDIDATE, q≈0.173 from 6,128 tests
- `inning_grp=7&p_max_vs_83=PEAK_AT` CANDIDATE (VAL-selected primary)

A new console grid computes FDR only over **that grid**.
