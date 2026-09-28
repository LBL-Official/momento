# Verification

AUTO ROLLER VERIFY levels:

1. Files / manifests / parquet readable / E4 sample / PIT columns
2. Freshness (source-aware; historical-only is not stale)
3. `rq_index_v1.0.0` leaves present
4. Semantic sentinels: increment2 `first_60_q2` N=271 and MLB 554, reference == optimized
5. Do not auto-overwrite goldens

`--fast` skips level 4–5 (launchd 00:00 default so the Mac is not blocked on a 2-minute NBA CSV load every night). Checksums of `rq_index` parquet files still run unless a test opts out. A planted manifest hash mismatch is FAILED and does not rewrite warehouse bytes. Run full verify before claiming a semantic release.

CLI: `python -m roller.auto_roller.verify` (full) or `--fast`.
