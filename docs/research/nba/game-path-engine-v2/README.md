# Game Path Engine V2 — conditional 40-barrier risk after first-80

Research only. Does **not** change live FIRST01, Risk, Kalshi execution,
Path Engine V1, the frozen 80/40 audit, MLB research, or
`frontend/research-console`.

```text
MOMENTO_GAME_PATH_ENGINE_V2
```

## Scientific object

V2 is **not** another market-microstructure classifier and **not** an NBA
winner model.

V1 asked whether pre-entry *market* state predicted the 40¢ barrier.
It did not, robustly.

V2 asks whether **how the basketball game and the contract arrived at 80¢**
changes barrier risk:

```text
P(Y_40 = 1 | Z_τ80^market, Z_τ80^game, Path_τ80)
```

versus the frozen unconditional:

```text
P(Y_40 = 1 | first-80) = 26.02%
```

Same terminal probability (≈80¢) is **not assumed** to imply the same path
risk. That proposition is tested, not granted.

Terminal probability `P(X_T = 1 | I_t)` and path probability
`P(K_{t+Δ} | K_t, G_t, τ_t, M_t)` are distinct. This engine estimates the
latter after first-80.

## Layout

| Role | Path |
| --- | --- |
| Spec | `docs/research/nba/game-path-engine-v2/` |
| Code | `apps/nba-data/scripts/game_path_engine_v2/` |
| Derived warehouse | `Backtesting Suite/Data/NBA/2025-2026/warehouse/derived/nba/momento_game_path_engine_v2/` |
| Frozen audit (read-only) | `.../derived/nba/first80_execution_audit/` |
| V1 (read-only) | `.../derived/nba/momento_path_engine_v1/` |
| Dashboard | `nba-game-path-engine-v2.canvas.tsx` |

## Pipeline

```text
NBA PBP ──► TIME ALIGNMENT ──► GAME STATE / PATH
                                      │
Kalshi 1m candles ──► MARKET PATH ────┤
                                      ▼
                               Z_τ80 SNAPSHOT
                                      ▼
                         BUCKETS → TESTS → MODELS
                                      ▼
                    ECONOMICS → PORTFOLIO → ONE OOS → VERDICT
```

Run (NBA research venv):

```text
/tmp/momento-nba-venv/bin/python run_pipeline.py
```

## Non-negotiables

- Frozen labels: 1,230 first-80 / 320 close-path 40 / 910 survivors.
- Primary target remains close-path `Y_40_CLOSE`. Wick is execution stress.
- No feature may use information after `ENTRY_DECISION_TIME`.
- Bucket discovery and model selection stay inside TRAIN / VALIDATION.
- OOS is one frozen pass. Failed experiments stay in the ledger.
- Nothing here arms live trading.
