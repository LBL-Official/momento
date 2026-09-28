# Complete Path Engine V4 — arrival-path discrimination

Research only. Does **not** change live FIRST01, Risk, Kalshi execution,
Path Engine V1, Game Path Engine V2, Dynamic Path Engine V3, the frozen
80/40 audit, MLB research, or `frontend/research-console`.

```text
MOMENTO_COMPLETE_PATH_ENGINE_V4
```

V1: market **state** at first-80. No robust OOS entry filter.
V2: game **state / collapsed path summaries** at first-80. No robust filter.
V3: **post-entry** hazard after first-80. No robust dynamic exit signal.

V4 does not rescue those models by mining more snapshots.

The object is the **complete arrival path** to first-80:

```text
Are the 320 close-path-40 failures distinguishable from the 910 survivors
by the trajectory through which the contract and game arrived at 80,
rather than by Z at 80 or by post-80 evolution?
```

A negative result is a successful scientific outcome.

```text
/tmp/momento-nba-venv/bin/python run_all.py
```
