# CTO-W4 ACCEPTANCE

**Only the CTO may set ACCEPTED / CLOSED in the control-plane sense.**

## W4 engineering gate: COMPLETE (price-path foundation)

Checklist (2026-08-26 reconstruct):

- [x] historical market universe inventoried (8,428)
- [x] TRADES_ONLY markets retained
- [x] TRADES_ONLY paths reconstructable (238 / 238)
- [x] observation types remain distinct
- [x] L2 is never fabricated (0 L2 paths)
- [x] identity is explicit
- [x] ambiguous/unmatched records are retained
- [x] capability gates are enforced
- [x] provenance is preserved
- [x] chronology is deterministic
- [x] lookahead is tested
- [x] price-path research works on TRADES_ONLY
- [x] microstructure remains blocked without L2
- [x] maker simulation remains blocked without L2
- [x] artifacts are generated
- [x] tests pass
- [x] clippy passes
- [x] no W5 work has started

TRADES_ONLY is **not** a failed dataset. See [CAPABILITY.md](CAPABILITY.md) and
[RECONSTRUCTION.md](RECONSTRUCTION.md).

## Remaining (not W4 reconstruction; do not start W5 from these)

1. **DATA-INGEST:** MATCHED pairs are still `MARKET_METADATA_ONLY`. GameId-linked
   80% denominator is **0 / 2,377**.
2. **W5:** event ↔ market time synchronization / `SynchronizedState` / clock contract.
3. Settlement/outcome fields are not present on discovery envelopes.
4. Historical L2 remains UNAVAILABLE (honest).

## Prohibited

- Treating candles or PIT REST as historical L2
- Using `retrieved_at` as `t_game`
- Suffix-matching identity
- Reconstructing 8,190 metadata-only tickers as a market engine
- Implementing `SynchronizedState` (that is W5)
- Discarding TRADES_ONLY because L2 is missing
