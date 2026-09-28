# W4 TEST PLAN

Crate tests (`crates/research-market/tests/w4_market.rs`) plus completeness
unit tests. Fixtures only unless a test explicitly opts into on-disk June 18.

Required:

1. Candle path is `CANDLES_ONLY`, never L2
2. Trades path is `TRADES_ONLY` even if candles also exist (spec: no
   `TRADES_AND_CANDLES` class)
3. Metadata-only path does not invent a bid
4. PIT REST snapshot excluded from t_game path
5. Integer cents round-trip; no `f64` money in types
6. UNMATCHED ticker still emits a path
7. AMBIGUOUS identity is preserved
8. Missing side of a two-contract event is explicit
9. Unsorted trades: sort + anomaly; duplicates: keep first
10. Checksum mismatch refuses reconstruction
11. No Data-Real writes (path fence)
12. No `struct SynchronizedState` and no theta
13. Production crates unchanged (Cargo.toml fence)
14. `event_type = candlestick` + `l2_snapshot` invalid
15. One PIT snapshot does not yield `L2_COMPLETE`
16. TRADES_ONLY market is retained
17. TRADES_ONLY is PRICE_PATH ALLOWED and ORDERBOOK / MAKER_FILL BLOCKED
18. Missing L2 never synthesizes bid/ask from trades
19. Candles never become quotes or L2
20. UNMATCHED / AMBIGUOUS preserved and GAME_ID_LINKED BLOCKED
21. MATCHED permits GAME_ID_LINKED (does not implement W5)
22. Capability metadata survives JSON round-trip
23. Price-path API succeeds on TRADES_ONLY; orderbook/maker/synthetic bid-ask fail closed
24. L2_COMPLETE vs L2_PARTIAL capability (fixtures; not invented history)
25. Chronology sorts by source time, not retrieval
26. `as_of` excludes later trades (no lookahead)
27. Provenance fields trace to raw trade id
28. Identical input → identical MarketPath
29. First trade is not labeled market open
30. Metadata-only skipped by `--reconstruct-price-paths`
