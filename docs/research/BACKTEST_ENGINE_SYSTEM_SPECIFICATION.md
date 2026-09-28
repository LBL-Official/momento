# BACKTEST_ENGINE_SYSTEM_SPECIFICATION.md

**CEO / CTO technical contract** for the MLB-first Historical Market/Game State
Backtesting & Research Engine.

**Status:** BINDING for research-engine work  
**Date:** 2026-08-26  
**Does not authorize:** Waterfall 1+ implementation, FIRST01 retune, production
trading changes, or other-sport adapters.

Governing roadmap: [`BACKTEST_ENGINE_WATERFALL.md`](BACKTEST_ENGINE_WATERFALL.md).  
ADRs: [`architecture-decisions/`](architecture-decisions/).  
Blueprint: [`HISTORICAL_ENGINE_DEVELOPMENT_PLAN.md`](HISTORICAL_ENGINE_DEVELOPMENT_PLAN.md).

Do not leave these concepts implicit. If code disagrees with this contract, the
contract wins until an ADR supersedes it.

---

## 1. System purpose

Reconstruct, at any MLB game time `t`, a causal historical state sufficient to:

- know event state and prior events
- know Kalshi market/book state (to the observability actually available)
- know the **path** that produced that market state for **both** contracts
- know event-derived and market-derived research variables (when defined)
- replay what FIRST01 **would have done** (plugin, later waterfall)
- know what happened next and what could have predicted the outcome

The system is a **historical state engine**. It is not a P&L spreadsheet generator
and not an extension of the LEGACY_V1 candlestick FIRST01 runner.

---

## 2. Canonical terminology

| Term | Meaning |
|------|---------|
| **EVENT domain** | Sporting contest: MLB game, PBP, game clock/situation |
| **MARKET domain** | Kalshi contracts, trades, quotes/candles/book |
| **Game** | One sporting contest instance |
| **Market / Contract** | One Kalshi YES contract (Team A or Team B) |
| **GameId** | Internal canonical game identity (u128 hash of event_ticker today) |
| **MarketId** | Internal canonical market identity (u128 hash of ticker today) |
| **Team A / Team B** | The two YES contracts in a game pack; not “the traded side” |
| **EventState / GameState** | Sport situation at a point |
| **MarketState** | Book/trade/status of one contract at a point |
| **SynchronizedState** | Event + both markets + sync metadata |
| **StateTransition** | Atomic research object: before → trigger → after |
| **GameMarketEpisode** | Container: one game, both contracts, full paths, outcomes |
| **FIRST01** | Frozen live MLB/WNBA desk strategy; first **plugin** |
| **LEGACY_V1** | Candle collector + FIRST01 runner; regression only |
| **OBSERVED / DERIVED / INFERRED / MODELED / LABEL_ONLY / UNAVAILABLE** | Availability classes (ADR-0011) |
| **Waterfall / Architecture / Step** | W / A / S hierarchy (ADR-0019) |

A **trade** is never the unit of truth.

---

## 3. Historical data philosophy

Acquire the deepest **available** 2025–2026 MLB + Kalshi history. Do not silently
substitute candles for ticks, last trade for bid, or mid for a venue field Kalshi
does not publish.

Coverage holes are first-class facts. Empty API probes are evidence, not data to
delete or invent.

Demo fixtures (`Backtesting Suite/Data`) are not MLB history.

---

## 4. Raw-data immutability

ADR-0001. Once ingested, raw is never rewritten to fix parsing.

Existing June 2026 `events.jsonl.gz` + published parquet + manifests are
`immutable_raw_kalshi_v1`. New writers fail closed if they would change those hashes.

---

## 5. Normalized-data versioning

Transforms write new version directories (or equivalent), never overwrite raw.

```text
RAW → NORMALIZED → RECONSTRUCTED → FEATURED → LABELED → MODELED
```

Each transform records `schema_version`, generator version, UTC time, input
checksums. Same inputs → same outputs (sort-stable).

Schema 1.0.0 LEGACY normalize is frozen (WRAP). Observability and candle OHLC
gaps are documented; they are fixed in a **new** normalize version.

---

## 6. Game identity

Internal `GameId` is canonical (ADR-0018). Tickers are aliases.

Waterfall 1 stub: `mlb_game_pk = null`, `match_status = UNMAPPED`. Do not invent
official ids.

Waterfall 2 maps: MLB game (date, home, away, game number / DH) ↔ GameId ↔
Kalshi event_ticker ↔ both contracts. Handle naming, abbreviations, postponements,
doubleheaders, canceled/missing markets, settlement mapping.

---

## 7. Market identity

`MarketId` from ticker hash (shared with live). Each pack has two YES contracts.
`side_label` from Kalshi subtitle is not a canonical TeamId. Waterfall 2
introduces a team registry for canonicalization.

---

## 8. Game / market relationship

One game ↔ one Kalshi event (when mapped) ↔ two contracts (when both exist).

If one contract is missing: retain the other; mark opponent UNAVAILABLE.
If join fails: retain both domains independently (ADR-0003).

Never drop raw because identity is UNMAPPED.

---

## 9. Timestamp semantics

ADR-0002. Distinct clocks; no silent substitution.

| Clock | Role |
|-------|------|
| Exchange / official source time | Authority for “knowable at t” |
| Candle `end_period_ts` | Period **end**, 1-minute bucket |
| Collector `received_at` / ingestion | Provenance only |
| Partition date | America/Los_Angeles close **or** settlement day (v1) |

v1 partitions are **not** market lifetime. Starting-price research requires
lifetime queries keyed by `open_time` (later collection, not a timestamp lie).

---

## 10. Event time

ADR-0004. Sport-specific situation clock. For MLB: inning, half, outs, remaining
outs (derived), bases, plate appearance, pitch state if observed, score, batter,
pitcher, game status. Wall clock is stored alongside, never as a substitute.

---

## 11. Market time

Market-domain time is exchange time of trades/quotes/candles/status, plus
derived path time (time since market open / first observation). Do not truncate
the conceptual lifetime to the settlement-day file without labeling coverage
`LIFETIME_INCOMPLETE`.

---

## 12. Event theta

ADR-0010. Empirical sporting quantity. Inputs preserved before formulas.
Not a hardcoded option formula. Versioned `value, timestamp, window, method`.
Deferred to Waterfall 9. Unavailable PBP → UNAVAILABLE theta.

---

## 13. Market theta

ADR-0009. Empirical relationship among price path, spread, liquidity, book,
and event state. Not Black-Scholes-as-truth. Deferred to Waterfall 10.
Missing L2 → do not invent implied Greeks from last trade.

---

## 14. Event state

Canonical `GameState` at every meaningful point (Waterfall 4): inning/half/outs,
score/differential, runners, batter/pitcher, pitch count, batting-order position,
base/out state, home/away, game status, remaining opportunity inputs.

`eventual_outcome` is **forbidden** on replay-at-t views.

---

## 15. Market state

Per contract (Waterfall 6): bid/ask/sizes/spread, last trade/size/volume,
depth/imbalance/liquidity if OBSERVED, quote/trade intensity, velocity/acceleration
as DERIVED later, market status.

Observability on every path: FULL_L2 | TOP_OF_BOOK_ONLY | CANDLESTICK_ONLY |
NO_EXECUTION_DATA (ADR-0008).

---

## 16. State transitions

Waterfall 5/8. Atomic object:

```text
State(t-1) → trigger → State(t)
```

Triggers include PBP_EVENT, TRADE, CANDLE_CLOSE, BOOK_UPDATE, TIMER.
Record previous/new event and market states, timestamps, sequence, provenance,
observability, dataset version. Plugin-visible fields must be causal (ADR-0012).

---

## 17. PBP synchronization

ADR-0003. Independent reconstruction, then join with confidence:

```text
EXACT | WITHIN_1S | WITHIN_3S | WITHIN_5S | WITHIN_INNING | AMBIGUOUS | UNMATCHED | UNAVAILABLE
```

Never silently upgrade confidence. No PBP download until source/license approved.

---

## 18. Orderbook representation

ADR-0008. Preserve observed microstructure. If historical L2 is unavailable,
mark it. **Never fabricate.** Candles are not books. Collection-time REST
snapshots are not game-time L2. Raw candle OHLC (high/low/open) exists in gzip
and is largely dropped in normalize v1 — catalog that gap; fix in v2+.

---

## 19. Starting contract prices

Mandatory to preserve **whenever available** for **both** Team A and Team B:

- first observed bid/ask/spread/liquidity
- market-open timestamp if in metadata
- lag from open to first observation
- source of start: first trade vs first candle vs metadata open

If not available (v1 close-day window): UNAVAILABLE + reason. Do not impute
from settlement or from 100 − opponent last.

---

## 20. Team A / Team B representation

ADR-0007. Every game preserves both sides’ starting prices, price paths,
event-state paths, event Greek paths, market Greek paths.

Also preserve: which team first reached 80%, when, game state, inning, half,
outs, runners, score, batter, pitcher, PBP sequence, market state, orderbook
state (or UNAVAILABLE).

Never discard the losing side because FIRST01 selected the other contract.

---

## 21. Price paths

For each contract, retain the ordered path of observed (and honestly classified)
prices from start through settlement, including threshold nodes. Pointers into
immutable streams are preferred over snapshot-only rows.

---

## 22. Event paths

Ordered PBP / game-state sequence from first pitch (or first OBSERVED play)
through terminal status. Missing pitch-by-pitch: store play-level; mark pitch
fields UNAVAILABLE. Do not backfill missing PBP from final score.

---

## 23. Greek paths

Event and market Greek paths are first-class **after** W9/W10. Until then,
preserve the inputs (state and market paths). Each Greek point: value, time,
window, method, version, observability.

---

## 24. First-touch threshold semantics

ADR-0006. First timestamp where **YES bid** reaches/crosses the threshold.
Not average time above, not last trade, not mid, not ask.

Levels: 20, 30, 40, 50, 60, 70, 80, 81, 83, 89, 90, 95. `DID_NOT_OCCUR` if
never touched. FIRST01 first_80 is the 80 node with sticky bind.

---

## 25. FIRST01 lifecycle

ADR-0017. Frozen control baseline (live-aligned):

```text
qualifying YES bid only
sticky first_80 on (GameId, MarketId, Side)
81 confirmation (same bound)
maker entry 80–83 inclusive, bid < ask
GAME_LOCK ≥ 89 (no new entry; does not flatten)
50% stop of actual entry-fill VWAP
one canonical opportunity / lifecycle per GameId
unfilled cancel → re-Build same opportunity, not a new trade
```

Risk `max_open_positions=5` and 12.5% budget are **not** FIRST01 rules.

Data layer must not hard-code these constants. Plugin parameters stay frozen
until a separately authorized experiment.

Live same-quote 81-confirm vs LEGACY research next-quote confirm: document;
do not change live to match research.

---

## 26. One-trade-per-game invariant

One FIRST01 opportunity per `GameId`. Sticky first_80 prevents opponent takeover.
`can_attempt_entry` is false for Flat, OpenComplete, Holding, StopTriggered,
LiquidationActive, SettlementPending, Settled, game lock, abandoned,
paused-above-max (live). Research `canonical_lifecycle_consumed` matches this.

Obsolete text in `FIRST01_live_entry_state_machine.md` (“may allow new
opportunity”) is **not** canonical.

---

## 27. Outcome labels

Waterfall 15. Future information stored as labels:

- price: hit 81/83/89/90/95
- adverse: −5/−10/−20/−30¢, −50%
- horizons: 1s … 60m, settlement
- trade: stop, settle W/L, MFE, MAE, time to adverse/favorable, P&L (MODELED if fills are)

Settlement labels from **observed** Kalshi result when present; else UNAVAILABLE.
Do not copy suspected live ledger settlement bugs into historical labels.

---

## 28. Lookahead prevention

ADR-0012. Features for decisions at t use only information available at t.
Future data: labels/outcomes/retrospective only.

Reject LABEL_ONLY from the live-available feature set.

---

## 29. Observability classifications

ADR-0011 + ADR-0020. OBSERVED, DERIVED, INFERRED, MODELED, LABEL_ONLY,
UNAVAILABLE. Never promote INFERRED → OBSERVED. Never interpolate L2.

Execution quality on a path/day must not be upgraded because one PIT snapshot
exists.

---

## 30. Model governance

ADR-0013.

```text
RESEARCH → CANDIDATE → VALIDATED → SUPERVISED → APPROVED → PRODUCTION
```

No silent replacement. No automatic production mutation.

---

## 31. Research / production boundary

Research crates must not depend on `momento-risk`, `momento-execution`,
`momento-strategy-mlb`, or `apps/trading-engine`.

Allowed: `momento-core` types (without changing money / `can_attempt_entry` /
80-81 meaning) and Kalshi **public** HTTP.

UNTOUCHED: live strategy, risk, execution, positions, pnl, live/paper config,
trading Kalshi transport, deploy units for live/paper.

Default trading mode is not LIVE. Research tasks transmit **0** production orders.

---

## 32. Reproducibility

Same input + same transform version → identical output. Catalogs sort-stable.
Checksums of inputs and outputs. Run manifests: engine version, schema version,
dataset version, UTC, lake root.

This workspace copy currently has **no git metadata**; when git exists, record
commit on completion records.

---

## 33. Experiment versioning

Every experiment: id, dataset version, feature version, plugin params (or
explicit FIRST01 v1 control), train/val/OOS windows, metrics, status.
FIRST01 canonical baseline remains the **control** under hyperparameterization.

---

## 34. Google Drive reporting

ADR-0014. Human-readable archive after W20. Not the raw warehouse.
Layout: SPORT → YEAR → DATASET → RUN → WATERFALL → EXPERIMENT.
Must include methodology, assumptions, limitations, identifiers, versions.

---

## 35. Google Sheets reporting

ADR-0015. Index after W21. Not the database. Do not mix LEGACY candle P&L with
reconstruction metrics. Index datasets, runs, validation, opportunities, trades,
classifications, experiments, metrics, errors, coverage, sync quality, model
versions, deployment candidates.

---

## 36. Cloud architecture

Local lake is the current machine source of truth
(`Backtesting Suite/Data-Real/`). Future: object storage + research DB as
canonical machine store; Drive remains human archive.

Research collector systemd (`deploy/momento-research-collector.*`) is isolated
from live. New engine collectors are separate units. Do not point research
collectors at order endpoints.

Production live remains AWS us-east-1 with triple live gate. Research work does
not change that.

---

## 37. Multi-sport architecture

Core names are sport-agnostic (`Sport`, adapter traits). MLB is the reference
adapter. `ResearchSport::{Mlb,Wnba}` today is too small; WRAP rather than delete.

NBA / WNBA / NHL / NCAAB: trait bounds only until MLB completes reconstruction,
research, validation, model, execution-model, reporting, and production-readiness
waterfalls.

WNBA raw in Data-Real is **preserved**, not implemented against.

---

## 38. MLB reference implementation

MLB (`KXMLBGAME`) is taken through the complete waterfall before other sports
become implementation targets. Local seed: 13 COMPLETE days Jun 18–30 2026,
172 games × 2 contracts, trades + 1-min candles, no PBP, no L2.

`crates/sports/src/mlb.rs` is currently an empty module comment. Event types
belong to W4+, not W0.

---

## 39. Future NBA / WNBA / NHL / NCAAB extensibility

After MLB gates pass: extract sport-agnostic interfaces; implement other sports
as **adapters**, not five independent systems. Remaining-opportunity measures
are sport-specific (do not reuse 54-out). Market packs may differ; Team A/B
coupling is the two-outcome pattern where applicable.

Do not begin those adapters because interfaces exist.

---

## 80% transition path (first-class object)

For every qualifying Team A / Team B market, preserve:

```text
STARTING PRICE
  → PRICE PATH
  → EVENT PATH
  → EVENT STATE PATH
  → EVENT GREEK PATH
  → MARKET GREEK PATH
  → ORDERBOOK PATH
  → FIRST 80% TOUCH
  → 81% CONFIRMATION
  → ENTRY
  → POST-ENTRY PATH
  → 89% LOCK
  → 50% STOP IF APPLICABLE
  → SETTLEMENT
  → FINAL OUTCOME
```

Do not store only the state at 80%. Nodes that never occur: `DID_NOT_OCCUR`.

---

## Do not invent data

If historical data does not exist: DOCUMENT IT.  
If synchronization cannot be proven: DOCUMENT IT.  
If an orderbook field is unavailable: DOCUMENT IT.  
If a Greek cannot be empirically derived: DOCUMENT IT.  
If a feature requires future information: REJECT IT FROM THE LIVE-AVAILABLE SET.

Accuracy is more important than completeness.

---

```text
PRODUCTION ORDERS TRANSMITTED BY THIS SPECIFICATION: 0
FIRST01 LIVE PARAMETER CHANGES: 0
WATERFALL 1 IMPLEMENTATION AUTHORIZED: NO
```
