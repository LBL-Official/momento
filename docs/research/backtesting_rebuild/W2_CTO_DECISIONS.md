# W2 CTO decisions (closeout freeze)

W2 did **not** modify `crates/research-data/src/foundation/**`.

## Decision 1 — SourceTimestampKind / official PBP clock

**Current state:** W1 `SourceTimestampKind` = TradeCreated | CandleEnd | VenueMetadata | IngestOnly | Unknown. No PBP variant.

**Reasoning:** Official PBP time is an EVENT-domain clock. Mapping it to `TradeCreated` would lie. Patching W1 in this run would violate W1 ownership.

**Decision:** W2 local `MlbTimestampKind::PbpOfficial`. Adapter `w1_kind_for_mlb` → W1 `Unknown`. Collector time stays `IngestOnly`.

**Consequences:** Join of PBP time to Kalshi trade time is W4, with an explicit confidence enum — not a silent clock alias.

**Consumers:** W2 ingest/event; later W4 sync.

**Implement now:** local enum + tests. **Deferred:** optional W1 schema addition `PbpOfficial` (W1 follow-up, not required to close W2).

---

## Decision 2 — PBP source

**Current state:** No historical official PBP locally. No download/license this run.

**Reasoning:** Fabricating PBP would poison every downstream waterfall.

**Decision:** Adapter/parser (StatsAPI-shaped envelope) exists. Coverage remains `MISSING_HISTORICAL_SOURCE`. Source contract forbids automatic substitution of Kalshi market files for PBP.

**Consequences:** Engine can be tested on `SYNTHETIC_TEST_FIXTURE`. Historical GameState reconstruction is BLOCKED on CEO+license+files.

**Consumers:** W2 coverage; W4/W5 event side may be UNAVAILABLE.

**Implement now:** interface only. **Deferred:** authorized ingest after license (still W2-owned ingest, not W3).

---

## Decision 3 — W1 `w2_contract`

**Current state:** W1 **exports** `RawArtifactRef` and `RawMarketIdentity` (including `starting_price_class`). A former W2 mirror diverged (`SportCode` vs `String`; missing `starting_price_class`).

**Reasoning:** Two structs with the same name is a contract failure.

**Decision:** Consume W1 types. Delete the fork. Keep an explicit adapter for `IdentityStubV1` (lossy: `open_time` and `match_status` are not `RawMarketIdentity` fields; `starting_price_class` is not an `IdentityStubV1` field).

**Consequences:** W2 Kalshi aliases always carry `StartingPriceUnverified`. Venue `open_time` on a stub is not market-open price.

**Consumers:** W2 identity, market_ref, W3 readers of W1 catalog.

**Implement now:** consume + adapter. **Deferred:** none. A W1 field change later would be a W1 follow-up, not a W2 silent patch.

**Incompatibility requiring W1 change:** none. Optional PBP kind is Decision 1 (deferred).

---

## Decision 4 — Kalshi-only identity

**Current state:** Lake games have Kalshi tickers; no official `mlb_game_pk`.

**Reasoning:** Inventing MLB ids would create false joins forever.

**Decision:** Canonical id `kalshi:{kalshi_game_id}` while UNMAPPED. `mlb_game_pk = None`. When an official pk is later observed, mint official `CanonicalGameId` and attach the Kalshi id as an **alias**. Do not rewrite history by replacing the kalshi: id in place without an explicit mapping record.

**Consequences:** W3/W4 must join UNMAPPED games on Kalshi aliases until mapping exists.

**Consumers:** W2 identity, W3 market identity, W4 sync keys.

**Implement now:** prefix + refuse invented pk. **Deferred:** real mapping when authorized official source exists (still W2 identity graph).

---

## Decision 5 — W5 `StateTransition` name

**Decision:** W2 type is `MlbPbpTransition`. W5 owns canonical `StateTransition` / `GameMarketEpisode`. No collision.
