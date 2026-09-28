# Increment 2 design (gated)

Increment 1 goldens exist. Identity equations hold on all four generic matrix
queries. FIRST80 frozen N=290 is unchanged.

## Named bottleneck (actual audit)

| Stage | Observation |
|---|---|
| NBA warehouse load | **45 341 ms** (`load_dataset` CSV → pandas → records) |
| Frozen FIRST80 | **109 ms**, N=290 |
| Generic entry scan | 10–23 s (2704 tickers, quality+cross+PBP each) |
| Generic path | 3–14 s and nearly equals entry when `evaluate_ticker` repeats `nth_touch` |
| Interactive RUN | load + scan ≈ **60–75 s** |

No DuckDB. Warehouse is CSV partitions, not Parquet. Adding a query engine
without a cited conversion cost would violate the gate. Default remains
existing files + Python semantics.

## What Increment 2 changes

```text
PRECOMPUTE ATOMIC FACTS     (tradable bars + crossings)
QUERY COMPOSED CONDITIONS   (ordinal / price / period / path / terminal)
```

Not a template cache of every question.

1. **Universe cache** — `universe_hash + dataset_version` → loaded payloads.
2. **Tradable bar index** — one `quality()` pass per ticker; reused.
3. **Entry reuse** — first-pass `TouchEvent` objects feed path/terminal.
   Do not call `evaluate_ticker` (second full scan).
4. **Semantic layer cache** — `entry_hash` population reused when only
   `measurement_hash` (terminal YES/NO/BOTH) changes.
5. Optional JSONL dump of touch events under `derived/research_query/` for
   the audit price grid. Not every 5¢ × quarter × ordinal combination.

## Equivalence

Must match Increment 1 goldens:

```text
second_touch_80          N=1087
first_60_q2              N=271
sequential_40_recover_80 N=1552
layered_and              N=288
FIRST80_frozen           N=290
```

Mismatch → revert. Do not edit goldens.

Verified: `test_increment2_matches_increment1_goldens` passed against the
committed Increment 1 counts (1087 / 271 / 1552 / 288 / frozen 290).

## Structural finding (not “fixed” by substitution)

Generic `kalshi_markets` load is empty (census markets=0). Every generic
matrix row has `terminal_missing = N`. Frozen FIRST80 still settles (missing=0).
ROLLER does not invent a second settlement source.
