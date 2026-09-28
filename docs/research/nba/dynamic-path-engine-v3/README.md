# Dynamic Path Engine V3 — post-entry barrier hazard

Research only. Does **not** change live FIRST01, Risk, Kalshi execution,
Path Engine V1, Game Path Engine V2, the frozen 80/40 audit, MLB research,
or `frontend/research-console`.

```text
MOMENTO_DYNAMIC_PATH_ENGINE_V3
```

V1 and V2 showed that **static** information at FIRST-80 did not yield a
robust OOS entry filter. V3 does not mine those models again.

V3 asks whether the **evolving post-entry path** predicts

```text
P(hit 40 in next Δ | alive above 40 at t, Z_t)
```

## Layout

| Role | Path |
| --- | --- |
| Spec | `docs/research/nba/dynamic-path-engine-v3/` |
| Code | `apps/nba-data/scripts/dynamic_path_engine_v3/` |
| Warehouse | `.../derived/nba/momento_dynamic_path_engine_v3/` |
| Dashboard | `nba-dynamic-path-engine-v3.canvas.tsx` |

```text
/tmp/momento-nba-venv/bin/python run_all.py
```
