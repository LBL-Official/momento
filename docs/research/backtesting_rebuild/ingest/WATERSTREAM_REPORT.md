# DATA-INGEST waterstream — completion report

**Date:** 2026-08-27  
**W1:** ACCEPTED / CLOSED  
**W2:** COMPLETE (event/PBP engine)  
**W3:** ACCEPTED / CLOSED ([W3_CTO_ACCEPTANCE.md](../W3_CTO_ACCEPTANCE.md))  
**CTO-W4–W8:** IMPLEMENTED (expand on rejoined pairs after matched-trades)

**Final status (evidence-based):**

| State | Value |
|-------|--------|
| CODE READY | **YES** (`INGEST.2.1.2`) |
| NETWORK READY | **YES** — authorized phrase `ENABLE_RESEARCH_INGEST_NETWORK` |
| BACKFILL COMPLETE | **NO** — 2024 Kalshi UNAVAILABLE; L2 not historical; trades not yet upgraded for every ticker |
| CONTINUOUS FEED OPERATIONAL | **NO** |
| Cloud | **IMPLEMENTED_NOT_DEPLOYED** |
| Research corpus target (2,000+ linked games) | **MET** (measured below) |

Do not read this as SUCCESS for 2024–2026 L2 completeness. Quantity below is **mapped identity**, not complete order books.

## Measured corpus (rejoin `rejoin-20260827T114739Z`)

Landing-wide identity rejoin of all committed StatsAPI envelopes + Kalshi discovery. Identity `W2.IDENTITY.1.2.0`: unique abbr concat, observed `gameNumber` vs ticker `G1`/`G2`/trailing `2`, observed `AZ`↔`ARI`. HHMM is not a mapping key. No invented `gamePk`.

| Metric | Count |
|--------|------:|
| StatsAPI PBP games committed | **5,006** |
| Kalshi markets discovered/landed | **8,458** |
| **Confidently mapped games** (unique `gamePk`) | **4,143** |
| Mapped game-market pairs | **8,286** |
| Unmatched PBP games | 863 |
| Unmatched Kalshi markets | 1,035 |
| Ambiguous | **0** |
| Completeness on mapped pairs this rejoin | **TRADES_ONLY** 228; **MARKET_METADATA_ONLY** 8,058 (L2 never inferred) |
| `pbp_target_met` (≥2,000 PBP games) | **true** |
| `pair_target_met` (≥2,000 mapped pairs) | **true** |

Pairs: `Backtesting Suite/Foundation/Ingest/runs/rejoin-20260827T114739Z/game_market_pairs.json`.

Unmatched PBP is mostly spring training (2025-03, 2026-02/03) with no `KXMLBGAME`. Unmatched Kalshi includes 2025-04-18 extra `*2` tickers without a StatsAPI game 2, All-Star special suffixes, and postponement official-date mismatch. 2023–2024 Kalshi remains **UNAVAILABLE**.

## Prior measured corpus (run `ingest-20260826T095038Z-2bc3d10b5833`)

Window: **2025-04-16 .. 2026-08-26**. PBP source: **MLB StatsAPI** (not ESPN). Kalshi: `KXMLBGAME` historical series + live remainder. Identity: **MAPPED / UNMATCHED / AMBIGUOUS** only — no best-guess joins.

| Metric | Count |
|--------|------:|
| StatsAPI PBP games committed | **2,937** |
| Kalshi markets discovered/landed | **8,428** |
| **Confidently mapped games** (unique `gamePk`) | **2,377** |
| Mapped game-market pairs | **4,754** |
| Unmatched PBP games | 560 |
| Unmatched Kalshi markets | 4,234 |
| Ambiguous | **0** |
| Completeness on mapped pairs this run | **MARKET_METADATA_ONLY** 4,754 (L2 never inferred) |
| `pbp_target_met` (≥2,000 PBP games) | **true** |
| `pair_target_met` (≥2,000 mapped pairs) | **true** |

June 18–30 subset still has on-disk **TRADES_ONLY** envelopes (multi-MB). The identity-scale pass used `--kalshi-metadata-only` so the run histogram is metadata; existing trade files were not deleted. Historical Kalshi MLB catalog **starts ~2025-04-16** (no 2024 tickers observed). PIT REST books are **not** historical L2.

## 1. What was implemented

Crate `momento-research-ingest` **INGEST.2.1.1** + CLI `momento-research-ingest`:

- Gated live network: `--authorize-network ENABLE_RESEARCH_INGEST_NETWORK`
- Kalshi historical discovery by `series_ticker=KXMLBGAME` (timestamp filters are mutually exclusive on `/historical/markets` and must not be used)
- Client-side date-token attribution; **MAPPED / UNMATCHED / AMBIGUOUS**
- `--window`, `--max-days`, `--kalshi-metadata-only`, `skip_existing` with metadata→trades upgrade when artifacts are requested
- `--window` does **not** expand via overlap to `as_of` (historical backfill stays in-window)
- Write fence: Data-Real, Foundation/W1, Foundation/W2/raw, production trees
- Cloud worker spec (not deployed)

W4, Greeks, production, and Data-Real writes were not implemented.

## 2. Isolation

W1/W2/W3 crates were not modified. Production trees, `strategies/mlb`, `crates/risk`, `config/live.toml` were not modified. Ingest landing only under `Backtesting Suite/Foundation/Ingest/landing/**`.
