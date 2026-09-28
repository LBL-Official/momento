# V4A fundamental conditioning

```text
MORE CONDITIONING ≠ BETTER ESTIMATION
```

Default schema: **`core_v1`**.

| Dimension | Source | Rule |
|-----------|--------|------|
| `period` | PBP period | identity |
| `clock_bucket` | `elapsed_game_seconds` | width 60; `bucket = (elapsed // 60) * 60` |
| `score_margin_bucket` | `score_differential_home` | edges `[-15, -5, 0, 5, 15]`; `[lo, hi)` |

Raw clock on PBP is **remaining** ISO (`PT06M32.00S`). Buckets use **elapsed** (regulation 720s / period; OT period ≥ 5 uses 300s). Missing period, clock, or score → `INVALID_CONDITION` / `MISSING_REQUIRED_INPUT`. No silent bucket.

Subject is **home**. `score_diff = home − away`. `Y = 1` iff `home_win == "1"`. Ties are both win flags `"0"` → `Y = 0`. `home_away` is not a conditioning dimension.

## Optional dimensions (off)

possession, `win_pct_pre`, volatility, market probability. A later `core_plus_possession_v1` would be a different estimator identity. V4A does not implement it.

## Identity

`condition_id = C_` + sha256 of `{conditioning_schema_version, dimensions}`. Raw dimensions are always persisted. V3 `config/conditioning.json` is not modified.
