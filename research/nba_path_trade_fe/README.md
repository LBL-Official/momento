# NBA path-trade feature engineering

Research-only second filter. Touch-80 is kept. Fragile members are rejected.

This is **not** a live FIRST01 / 80/81/83/89 change, not Choosin Texas, and not
a remount of the 604 reverse-feature store.

```text
LIVE EXECUTION = FALSE
CANDLE PATH ≠ FILL
Family E never enters enter_skip
Missing L2 = SOURCE_UNAVAILABLE, never fabricated
r ∈ [0.12, 0.25]
Failed promotion → tighten, do not expand
```

## Contract

Binding order: `docs/AGENTS.md` → `docs/AMENDMENT_v3.md` → `docs/FEATURE_ENGINEERING_SPEC.md`.

`features/registry.yaml` is the SSOT for feature names.

## Warehouse run (default)

```bash
cd ROLLER
.venv/bin/python -m roller.nba_path_fe
```

Ingests 2025–26 regular-season 1m TRADABLE_YES_BID paths into `data/raw/`,
then walk-forwards. Candle path ≠ fill. L2 is `SOURCE_UNAVAILABLE`.
Production `KalshiFeeModel` is `UNRESOLVED` — fee EV is not a gate.

`--synthetic` is the old harness only. Do not use it to cosmeticize \(r\).

Writes `artifacts/walkforward/summary.json`.

Do not treat synthetic books as Kalshi L2. Fee PnL uses
`ESTIMATED_PLACEHOLDER_CENTS_PER_SIDE`, not production `KalshiFeeModel`.

## τ policy (tighten)

Band compliance is claimable only when **τ ∈ [0.77, 0.84]** and fold **r ∈ [0.12, 0.25]**.
A τ below the spec band is `out_of_band_synthetic` and forces **promotion FAILED**.
`train_rate_target` undershoot is not a success path.

Pooled r in-band does not hide fold `r_in_band` failures.

## Warehouse close (2025–26)

`filter_status=INACTIVE_NO_RESIDUAL_EDGE`. One decision-layer τ grid failed
recover criteria. Unfiltered touch-80 (desk 78–82 / bail-40) beats this filter.
Do not expand features. See `docs/WAREHOUSE_CONCLUSION.md`.
