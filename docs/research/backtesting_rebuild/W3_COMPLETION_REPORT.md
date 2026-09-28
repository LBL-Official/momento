# W3 Completion Report

**Waterfall:** CTO-W3 — MLB Game / PBP Reconstruction  
**Run:** `w3-20260826T083802Z`  
**Artifact version:** `W3.0.0`  
**CTO decision:** **ACCEPTED / CLOSED** — [W3_CTO_ACCEPTANCE.md](W3_CTO_ACCEPTANCE.md)

W3 is the reconstruction **layer**. It reuses the W2 parser and fail-closed replay engine. It does not download, does not write Data-Real, does not reconstruct Kalshi books, and does not compute theta.

## 1. Implementation summary

- Crate `momento-research-reconstruction` + CLI `momento-research-w3`
- Committed-artifact gate (DATA-INGEST handoff or checksum-verified W2 collect manifest)
- Lifecycle classifier (Postponed/Cancelled/Suspended/Final/…)
- Honest window coverage (no COMPLETE inferred from a date range)
- Evidence-only `CTO-W3-A#-S#` ledger (not auto-completed)
- Docs under `docs/research/backtesting_rebuild/W3/`

## 2. Source coverage

Authorized source: MLB StatsAPI (already landed by prior W2 collect / DATA-INGEST policy).  
This run used **legacy committed** `Foundation/W2/statsapi_collect_manifest.json` after per-file SHA-256 verify.

| Metric | Count |
|--------|-------|
| Discovered (schedule listed) | 178 |
| Fetched (Final envelopes) | 174 |
| Committed (checksum ok) | 174 |
| Skipped (not played Final) | 4 Postponed |
| Duplicate SHA | 0 |
| Checksum failures | 0 |

## 3. Game coverage

| Metric | Count |
|--------|-------|
| Reconstructed | 174 |
| VALID replay | 174 |
| FAILED | 0 |
| Cancelled | 0 |
| Suspended | 0 |

## 4. PBP event coverage

**13315** canonical events across 174 VALID games (W2 parser). Synthetic fixtures excluded from this total.

## 5. Identity mapping

From W2 identity join on this window (not invented):

| Status | Count |
|--------|-------|
| Mapped Kalshi alias | 168 |
| Unmatched | 4 |
| Ambiguous | 2 |

`gamePk` observed from StatsAPI. No manufactured official ids.

## 6. Reconstruction results

174/174 fail-closed replay VALID. Anomalies list empty. Theta values calculated: **0**.

## 7. Anomaly counts

0 reconstruction anomalies. 4 skipped postponed (not anomalies).

## 8. Unavailable fields / windows

- 2024–2025 local committed PBP: **UNAVAILABLE** (not COMPLETE)
- 2025-03-18..2026-06-17: **UNAVAILABLE**
- Event theta **value**: UNAVAILABLE (W10 / later estimator)
- Historical L2 / market paths: not W3

## 9–10. Tests executed

| Command | Exit |
|---------|------|
| `cargo fmt -p momento-research-reconstruction -p momento-research-w3 -- --check` | **0** |
| `cargo check -p momento-research-reconstruction -p momento-research-w3 --offline` | **0** |
| `cargo test -p momento-research-reconstruction --offline` | **0** (18 tests) |
| `cargo clippy -p momento-research-reconstruction -p momento-research-w3 --all-targets --no-deps --offline -- -D warnings` | **0** |
| `cargo test -p momento-research-event --offline --test w2_engine` | **0** |
| `cargo test -p momento-research-data --offline --test w1_foundation overwrite_guard_blocks_lake_writes -- --exact` | **0** |
| `cargo run -p momento-research-w3 -- --out Foundation/W3 …` | **0** |

## 11. Data-Real integrity

W3 writes only `Backtesting Suite/Foundation/W3/`. `LakeWriteGuard` refuses lake paths.

Measured latest Data-Real file mtime after W3 work: **2026-08-25T11:05:01** (`Backtesting Suite/Data-Real/WNBA/2025-2026/manifests/date=2026-06-24.json`). Unchanged vs W1 audit. Production trees (`strategies/mlb`, `crates/risk`, `config/live.toml`) also unchanged by this pass.

## 12. Production isolation

`momento-research-reconstruction` Cargo.toml has no `momento-risk` / `momento-execution` / `momento-strategy-mlb`. Production trees not edited.

## 13. DATA-INGEST compatibility

W3 consumes `W1CommitHandoff` (COMMITTED + SHA-256) or a checksum-verified collect manifest. W3 does not schedule, download, or overwrite landing. Weekly Sunday 00:00 PT remains ingest-owned.

Ingest’s current `w2_gate` still calls W2 `reconstruct_paths` internally; W3 is the dedicated reconstruction job for committed artifacts. That dual consume is documented, not a W4 market path.

## 14. Known limitations

- 2024–2025 and most 2025–2026 PBP not locally committed
- Four postponed games have no PBP envelope (correct SKIPPED)
- W2 collect landing is frozen; new bytes must come through DATA-INGEST
- Ledger rows without evidence stay NOT_STARTED (intentional)

## 15. W4 handoff

See [W3/HANDOFF.md](W3/HANDOFF.md). **Do not start W4 in this report.**
