# BACKTEST_ENGINE_CURRENT_STATE.md

**Audience:** a new engineer (or agent) who must understand the project **now**.  
**As of:** 2026-08-27  
**Exact current W/A/S:** W0 COMPLETE. W1 **ACCEPTED / CLOSED**. W2 engine COMPLETE for observed window. CTO-W3 **ACCEPTED / CLOSED**. DATA-INGEST **CODE READY** / **BACKFILL_PARTIAL** / cloud **LOCAL_CRON_ONLY**. CTO-W4 **COMPLETE** (price-path foundation). CTO-W5 event↔market sync **IMPLEMENTED**. CTO-W6 canonical MLB state engine **IMPLEMENTED**. CTO-W7 EventMarketPath **IMPLEMENTED**. CTO-W8 FIRST01 observational replay **IMPLEMENTED**. B1 price-dissection feature engine **IMPLEMENTED** (schema 1.1.0 + A1 entry/exit buckets). W9 not started.

Update this file at every S-step checkpoint.

---

## 1. What has been completed?

### Production MLB stack (untouched by this program)

Live FIRST01, Risk Decision Engine, execution, positions, PNL, trading-engine host,
Kalshi trading adapter, paper/live config with triple live gate. **Not** part of
the research-engine rebuild.

### Research platform

Candle-era FIRST01 backtester is **LEGACY_V1**. New platform: historical
event–market reconstruction engine.

### Waterfall 0

Complete (recon A1–A10 + governance baseline A11).

### Waterfall 1

CEO **ACCEPTED / CLOSED** 2026-08-26.

### Waterfall 2

Canonical MLB event/PBP **engine** COMPLETE for the observed committed window.

### Waterfall 3

CTO **ACCEPTED / CLOSED** 2026-08-26. Reconstruction layer over committed PBP.
See [backtesting_rebuild/W3_CTO_ACCEPTANCE.md](backtesting_rebuild/W3_CTO_ACCEPTANCE.md).

### DATA-INGEST

Waterstream `INGEST.2.1.2`. Identity `W2.IDENTITY.1.2.0`.

Landing-wide offline rejoin `rejoin-20260827T114739Z` (PBP through **2026-08-27**; Kalshi catalog from **2025-04-16**):

- StatsAPI PBP envelopes: **5,006**
- Kalshi markets landed: **8,458**
- Confidently mapped games: **4,143**
- Mapped game-market pairs: **8,286**
- Unmatched PBP games: 863 (mostly spring training Feb–Mar with no `KXMLBGAME`)
- Unmatched Kalshi markets: 1,035 (Apr-18 extra `*2` without game-2 PBP, All-Star special tickers, postponement date mismatch). **0 ambiguous**
- Identity: unique observed abbr concat + `gameNumber` vs ticker `G1`/`G2`/`2`; observed `AZ`↔`ARI` alias. No invented `gamePk`. HHMM is not used to disambiguate.
- 2023–2024 Kalshi: **UNAVAILABLE** (historical `KXMLBGAME` catalog begins ~2025-04-16)
- L2: not claimed / not invented

Pairs path: `Backtesting Suite/Foundation/Ingest/runs/rejoin-20260827T114739Z/game_market_pairs.json`.

Report: [backtesting_rebuild/ingest/WATERSTREAM_REPORT.md](backtesting_rebuild/ingest/WATERSTREAM_REPORT.md).

### Waterfall 6

Canonical MLB `GameState` / `StateTransition` engine. See
[backtesting_rebuild/W6_STATE_ENGINE.md](backtesting_rebuild/W6_STATE_ENGINE.md).
Landing reconstruction: **3,848** envelopes, **3,825** replayed, **23** fail-closed
`FINAL_TIE`. All **2,377** mapped-pair game_pks reconstructed.

### Waterfall 7

Canonical EventMarketPath join of W5 TRADE observations onto W6 game truth.
See [backtesting_rebuild/W7_EVENT_MARKET_PATH.md](backtesting_rebuild/W7_EVENT_MARKET_PATH.md).
W5 remains AS-OF authority. W6 remains game-truth authority. No invented L2.

### Waterfall 8

Observational FIRST01 replay over accepted W7 EventMarketPath.
See [backtesting_rebuild/W8_FIRST01_REPLAY.md](backtesting_rebuild/W8_FIRST01_REPLAY.md).
Qualifying price is the W7 TRADE print (`TRADE_PRINT_NOT_YES_BID`). No fills,
no P&L, no W9 outcome labels.

---

## 2. What is currently being built?

DATA-INGEST matched-trades skip-existing on the rejoined 8,286 mapped pairs, then
CTO-W4 → W5 → W6 → W7 → W8 on that corpus. Do not start W9. Do not invent L2.

---

## 3. What is the exact current W/A/S?

```text
COMPLETE:     W0-A11; W1 ACCEPTED/CLOSED; W2 engine (observed window);
              W3 ACCEPTED/CLOSED; W4 price-path foundation (238 TRADES_ONLY);
              W5 event↔market AS-OF sync (PBP ∩ MATCHED trades);
              W6 canonical MLB GameState / StateTransition engine;
              W7 EventMarketPath (W5 TRADE ⊕ W6 state);
              W8 FIRST01 observational replay;
              B1 observational price-dissection features (1.1.0 + A1 buckets);
              B1 exhaustive A1 bucket search COMPLETE (TRADE_PRINT_MODELED)
CURRENT:      B1 search reports in Foundation/B1. Not a trading rule.
NEXT:         STOP. Do not start W9 / B2 / ML / live FIRST01 changes.
AUTHORITY:    W9 / outcome labels / Greeks / fills / AWS ingest forbidden unless newly granted
```

---

## 4. What is blocked?

| Work | Why |
|------|-----|
| Full 2024 Kalshi | Historical `KXMLBGAME` catalog begins ~2025-04-16; not fabricated |
| Cloud weekly ingest | Torn down; local cron only. Do not redeploy. |
| W4 8k metadata-only reconstruct | Intentionally not run. 8,190 METADATA_ONLY excluded from paths. |
| MATCHED W4 price-path reconstruct | Optional; W5 consumes MATCHED trade sidecars directly |
| W5 event↔market sync | Implemented; see Foundation/W5 reports |
| W6 canonical state engine | Implemented; see Foundation/W6 reports. 23 FINAL_TIE fail-closed |
| Historical L2 | Unavailable (honest). TRADE print ≠ YES bid. |
| W9 outcome / Greeks / fills | Not authorized |

---

## 5. What has been validated?

- W1 integrity + clippy `-D warnings` on `momento-research-data`
- Ingest waterstream tests (31 passed) + clippy `-D warnings`
- W2 engine tests (`w2_engine`: 32 passed)
- W3 reconstruction tests (`w3_reconstruction`: 18 passed)
- Real committed window 2026-06-18..30: 174/174 VALID replay; 4 postponed SKIPPED
- StatsAPI schedule probe 2026-06-18: HTTP 200, 9 games, observed gamePk
- W4 market tests (`w4_market`: 34 passed + 12 unit)
- W4 2026-06-18: 18/18 reconstructed TRADES_ONLY; 9 coupled both-YES; 8 PIT excluded
- W4 universe: 8,428 inventoried; 238 TRADES_ONLY paths; 137 with 80% print; L2_COMPLETE 0
- W5 sync tests (`w5_sync`: 34 passed)
- W6 state tests (`w6_state`: 30 passed)
- W6 reconstruction: 3848 landing envelopes; 3825 replayed; 23 FINAL_TIE fail-closed
- W7 path tests (`w7_path`: 18 passed)
- W7 EventMarketPath: 1684/1684 overlap games; 2,089,269 TRADE observations; anti-lookahead PASS
- W8 replay tests (`w8_replay`: 27 passed); truncation gate PASS
- W8 FIRST01 replay: 1684 games; 16,020 80¢ prints; 1,558 FIRST80; 1,483 confirm81; 1,306 entry-eligible; 1,528 GAME_LOCK; observations reconcile to W7
- Workspace `cargo test --workspace` (**726** passed, 1 ignored) + `clippy -D warnings`
- Production strategy/risk/execution trees not modified by this work

---

## 6. What remains unverified?

- Live StatsAPI backfill of 2024–2025 / remainder of 2026
- Live Kalshi historical market discovery (not invoked)
- Cloud ingest stack (deleted; do not recreate)
- Remaining MATCHED-pair historical trades not yet sidecared (catalog 4,754)
- W9 outcome labels / Greeks / fill simulation
- Settlement/outcome on discovery envelopes

---

## 7. What artifacts exist?

| Artifact | Location |
|----------|----------|
| W0 recon | `docs/research/backtesting_rebuild/` |
| W1 derived | `Backtesting Suite/Foundation/W1/` |
| W2 derived | `Backtesting Suite/Foundation/W2/` |
| W3 derived | `Backtesting Suite/Foundation/W3/` |
| Ingest landing | `Backtesting Suite/Foundation/Ingest/` (runtime; gitignored landing/runs) |
| W4 derived | `Backtesting Suite/Foundation/W4/` |
| W5 derived | `Backtesting Suite/Foundation/W5/` |
| W6 derived | `Backtesting Suite/Foundation/W6/` |
| W7 derived | `Backtesting Suite/Foundation/W7/` |
| W8 derived | `Backtesting Suite/Foundation/W8/` |
| Lake | `Backtesting Suite/Data-Real/` (immutable) |

---

## 8. What data exists?

Unchanged Kalshi Data-Real: 13 COMPLETE MLB days 2026-06-18…30. 2025 probes empty.
W2 StatsAPI envelopes may exist under frozen `Foundation/W2/raw/` from earlier W2-E.
New ingest landing is separate. PBP 2024–2025 / full 2025–2026 **not** claimed complete.

---

## 9. What assumptions remain?

1. Data-Real remains immutable.
2. Ingest is the only writer of `Foundation/Ingest/landing`.
3. W2/W3 consume only COMMITTED landing.
4. FIRST01 v1 numbers stay frozen.
5. Kalshi market reconstruction is W4.
6. Event↔market time join is W5. Canonical MLB state is W6. EventMarketPath is W7. FIRST01 observational replay is W8. W9 is not started.

---

## 10. What is the next authorized step?

**STOP.** Do not start W9 (outcome labeling, future returns, Greeks, fills).

```text
W1: ACCEPTED/CLOSED
W2 engine: observed window reconstructed
W3: ACCEPTED/CLOSED
DATA-INGEST: CODE READY; BACKFILL_PARTIAL; LOCAL_CRON_ONLY
W4: COMPLETE (price-path foundation)
W5: IMPLEMENTED (event↔market AS-OF; PBP ∩ MATCHED trades)
W6: IMPLEMENTED (canonical MLB state engine; 3825/3848; 23 FINAL_TIE)
W7: IMPLEMENTED (EventMarketPath; W5 TRADE ⊕ W6 state)
W8: IMPLEMENTED (FIRST01 observational replay; TRADE print ≠ YES bid)
B1: IMPLEMENTED (price features 1.1.0; A1 entry/exit buckets; L2 UNAVAILABLE)
W9: NOT AUTHORIZED
PRODUCTION ORDERS: 0
```
