# WATERFALL_CONTRACT_REGISTRY.md

**Source of truth for names.** Field lists for unimplemented types are **DESIGN** (from W0 domain model + ADRs), not Rust.  
**Version rule:** semantic change ⇒ new version. Never silent mutation.

Observability on every important field: `OBSERVED | DERIVED | INFERRED | MODELED | LABEL_ONLY | UNAVAILABLE` (ADR-0011). W1 adds `L2_HISTORICAL_UNAVAILABLE` and `OUTCOME_LABEL` as aliases — FLAG-007.

Timestamp kinds (ADR-0002): never promote ingestion → exchange.

---

## Freeze legend

| Freeze | Meaning |
|--------|---------|
| IMMUTABLE | Bytes never change |
| FROZEN | Semantics locked; new version to change |
| DRAFT-IN-USE | Code exists; not control-plane accepted |
| DESIGN | Docs only; no Rust in this program yet |
| DOWNSTREAM | Required later; not implemented by control or W1 |

---

## 1. RawObservation

| | |
|--|--|
| **Purpose** | One immutable source payload (Kalshi REST row, future PBP row, future WS frame) |
| **Owner** | CTO-W1 (Kalshi v1/v2 envelope). Future PBP raw: CTO-W2 **new** raw tree, not overwrite |
| **Producer** | LEGACY collector (v1 gzip); W1 envelope lift (v2 sample, additive) |
| **Consumers** | W1 catalog, W2/W3 reconstructors |
| **Mutability** | IMMUTABLE (v1 files). v2 is new files only |
| **Required** | payload; ingestion_timestamp; source; path/line or equivalent |
| **Optional** | source_record_id; source_timestamp; ticker |
| **Timestamps** | `ingestion_timestamp` = collector clock. `source_timestamp` = venue/official when present + kind |
| **Observability** | Payload presence = OBSERVED. Clock kind must be explicit |
| **Version** | v1 `RawMarketEvent` schema 1.0.0 FROZEN; v2 `RawEnvelopeV2` 2.0.0 DRAFT-IN-USE |
| **Compatibility** | v2 must round-trip v1 without rewriting gzip |
| **SoT** | Data-Real `events.jsonl.gz`; types: `schema.rs`, `foundation/envelope_v2.rs` |

---

## 2. DataProvenance

| | |
|--|--|
| **Purpose** | Trace a file or row to source, query, checksum, coverage |
| **Owner** | CTO-W1 |
| **Producer** | W1 catalog/integrity job |
| **Consumers** | All downstream; Drive later (aggregates only) |
| **Mutability** | REPRODUCIBLE derived |
| **Required** | source, original_path, checksum when file exists, coverage_status, timestamp **role** |
| **Optional** | request_query, collector_version, retrieval_timestamp |
| **Timestamps** | `source_timestamp_semantics` is a role, not a substitute clock |
| **Observability** | Provenance of UNAVAILABLE sources is itself OBSERVED evidence of absence |
| **Version** | `ProvenanceRecord` DRAFT-IN-USE |
| **Compatibility** | File-level provenance is not row-level clock (FLAG-010) |
| **SoT** | `foundation/provenance.rs` |

---

## 3. Game

| | |
|--|--|
| **Purpose** | One sporting contest instance. Internal `GameId` canonical (ADR-0018) |
| **Owner** | Identity graph: CTO-W2. Stub: CTO-W1 |
| **Producer** | W1 stub from Kalshi `event_ticker` hash; W2 maps official ids |
| **Consumers** | Every later W |
| **Mutability** | Stub REPRODUCIBLE; official mapping versioned |
| **Required** | `game_id`; aliases (event_ticker) |
| **Optional** | `mlb_game_pk` (null until mapped) |
| **Timestamps** | Game clock is EVENT domain (W2), not partition date |
| **Observability** | UNMAPPED is valid |
| **Version** | `IdentityStubV1` DRAFT-IN-USE |
| **Compatibility** | Do not change live hash algorithm |
| **SoT** | `kalshi/identity.rs` (WRAP); `foundation/identity_stub.rs` |

---

## 4. GameMarketEpisode

| | |
|--|--|
| **Purpose** | **Container:** one game, both contracts, full paths, coverage, outcome |
| **Owner** | CTO-W5 |
| **Producer** | W5 engine (not FIRST01) |
| **Consumers** | W6 plugin, W7 labels, W8–W10, W11 reports |
| **Mutability** | REPRODUCIBLE reconstructed version |
| **Required** | identity; both market ids or UNAVAILABLE opponent; path refs; coverage; provenance |
| **Optional** | first-touch nodes as DID_NOT_OCCUR rather than omitted |
| **Timestamps** | Paths, not a single snapshot |
| **Observability** | Per-layer coverage required |
| **Version** | DESIGN (W0 domain model §9) |
| **Compatibility** | Data layer must compile without FIRST01 |
| **SoT** | `PROPOSED_CANONICAL_DOMAIN_MODEL.md` |

---

## 5. GameState

| | |
|--|--|
| **Purpose** | EVENT-domain situation at a point (MLB adapter view) |
| **Owner** | CTO-W2 |
| **Producer** | PBP reconstruction or UNAVAILABLE placeholder |
| **Consumers** | W4 sync, W5 transitions, W8 event greeks |
| **Mutability** | REPRODUCIBLE |
| **Required (representable)** | game_id; inning/half/outs **or UNAVAILABLE**; score **or UNAVAILABLE**; game_status |
| **Optional** | runners, batter, pitcher, pitch_count, pitch_state |
| **Forbidden on replay-at-t** | eventual winner |
| **Timestamps** | official PBP time vs wall clock — both stored when present |
| **Observability** | remaining_outs is DERIVED (ADR-0005, definition v1 later) |
| **Version** | DESIGN |
| **Compatibility** | Sport-specific fields behind `GameStateAdapter` |
| **SoT** | W0 MLB reconstruction requirements; PLAN-W4 |

---

## 6. PBPEvent

| | |
|--|--|
| **Purpose** | Discrete official (or licensed) play/pitch event |
| **Owner** | CTO-W2 |
| **Producer** | Authorized PBP source only |
| **Consumers** | GameState reconstruction |
| **Mutability** | Raw IMMUTABLE in a **new** tree; never stuffed into Kalshi gzip |
| **Required** | source_record_id; sequence; provenance |
| **Optional** | pitch-level fields |
| **Timestamps** | `pbp_official` kind; never invented from trade time |
| **Observability** | Local lake: UNAVAILABLE |
| **Version** | DESIGN. Synthetic FIXTURE allowed, labeled |
| **Compatibility** | Failed join does not drop PBP or market raw (ADR-0003) |
| **SoT** | none in repo |

---

## 7. MarketObservation

| | |
|--|--|
| **Purpose** | One market-domain observation (trade, candle close, quote) with honesty |
| **Owner** | CTO-W3 (reconstruction). W1 preserves raw |
| **Producer** | W3 from catalogued Kalshi files |
| **Consumers** | W4, W5, W9 |
| **Mutability** | REPRODUCIBLE normalize version |
| **Required** | market_id; observability; timestamp + kind |
| **Optional** | sizes, depth |
| **Timestamps** | trade `created_time`; candle `end_period_ts` (period **end**) |
| **Observability** | candle ≠ tick ≠ L2 |
| **Version** | DESIGN for reconstructed type; raw is W1 |
| **Compatibility** | Exclude PIT RestSnapshot from game-time path |
| **SoT** | KALSHI_DATA_OBSERVABILITY_MATRIX.md |

---

## 8. OrderBookObservation

| | |
|--|--|
| **Purpose** | Book levels / TOB at t if OBSERVED |
| **Owner** | CTO-W9 (research) / CTO-W3 (storage of what exists) |
| **Producer** | Historical: none (UNAVAILABLE). Forward WS: future W11/PLAN-W26 |
| **Consumers** | Execution model (W6), microstructure (W9) |
| **Mutability** | IMMUTABLE if captured; never interpolated into June gzip |
| **Required** | observability = L2_HISTORICAL_UNAVAILABLE unless real WS artifact catalogued |
| **Optional** | levels, sizes |
| **Timestamps** | exchange sequence if WS; ingest-only if PIT REST |
| **Observability** | ADR-0008 |
| **Version** | DESIGN |
| **Compatibility** | `orderbook.parquet` name is not L2 |
| **SoT** | ADR-0008; W1 observability contract |

---

## 9. StateTransition

| | |
|--|--|
| **Purpose** | **Atomic** research object: before → trigger → after |
| **Owner** | CTO-W5 |
| **Producer** | W5 engine from event + market streams |
| **Consumers** | W6 plugin, W7–W10 |
| **Mutability** | REPRODUCIBLE |
| **Required** | game_id; timestamp; trigger; before/after (or explicit gap); path refs; provenance; observability; dataset_version |
| **Optional** | strategy_state, execution_state (plugin-owned, empty in data layer) |
| **Forbidden at t for plugins** | future PBP, future book, eventual winner |
| **Timestamps** | declared clock + kinds |
| **Observability** | per field |
| **Version** | DESIGN |
| **Compatibility** | Event-only PBP transitions (PLAN-W5) are inputs, not a rival schema |
| **SoT** | ADR-0016; domain model §8 |

---

## 10. ThresholdTransition

| | |
|--|--|
| **Purpose** | First-touch of YES **bid** at configured cents (20–95 including 80/81/83/89) |
| **Owner** | CTO-W5 (tables). FIRST01 consumes 80 as plugin (W6) |
| **Producer** | Generic first-touch engine |
| **Consumers** | W6, W7 |
| **Mutability** | REPRODUCIBLE |
| **Required** | level; first_touch ts/price or DID_NOT_OCCUR; observability of the bid |
| **Optional** | preceding/following price |
| **Timestamps** | same clock as the qualifying bid |
| **Observability** | candle bid allowed with CANDLESTICK; not mid; not last trade (ADR-0006) |
| **Version** | DESIGN |
| **Compatibility** | Data layer must not hard-code FIRST01-only 80 |
| **SoT** | ADR-0006 |

---

## 11. FIRST01Opportunity

| | |
|--|--|
| **Purpose** | Plugin output: what FIRST01 **would have done** on a causal stream |
| **Owner** | CTO-W6 |
| **Producer** | FIRST01 plugin v1 (frozen) |
| **Consumers** | W7 labels (trade family), reports |
| **Mutability** | FROZEN parameters; outputs REPRODUCIBLE per dataset version |
| **Required** | game_id; one canonical opportunity per GameId; sticky first_80; 81 confirm; maker 80–83; lock ≥89; 50% VWAP stop |
| **Optional** | fill — only if execution quality allows; else no fill / MODELED |
| **Timestamps** | document same-quote vs next-quote 81 clock vs live |
| **Observability** | signals OBSERVED-from-bid; fills MODELED |
| **Version** | v1 FROZEN |
| **Compatibility** | Do not edit `strategies/mlb`. Do not retune because a loser cohort looks interesting |
| **SoT** | FIRST01_BASELINE_SEMANTICS.md; ADR-0017 |

---

## 12. OutcomeLabel

| | |
|--|--|
| **Purpose** | Future labels (price/adverse/horizon/trade/settlement). Training targets |
| **Owner** | CTO-W7 |
| **Producer** | Labeler from observed settlement/path **after** t |
| **Consumers** | W8 features (LABEL_ONLY split), W10 |
| **Mutability** | Experiment-scoped |
| **Required** | label family; as-of timestamp; LABEL_ONLY flag |
| **Forbidden** | presence on replay-at-t / live-available feature views |
| **Timestamps** | label time > decision time |
| **Observability** | LABEL_ONLY / W1 `OutcomeLabel` |
| **Version** | DESIGN |
| **Compatibility** | ADR-0012 no-lookahead |
| **SoT** | PLAN-W15 |

---

## 13. FeatureVector

| | |
|--|--|
| **Purpose** | Versioned features with availability class per column |
| **Owner** | CTO-W8 |
| **Producer** | Feature warehouse |
| **Consumers** | W10 |
| **Mutability** | Versioned |
| **Required** | feature_version; live-available vs LABEL_ONLY split |
| **Optional** | greeks (UNAVAILABLE if inputs missing) |
| **Timestamps** | all live-available inputs ≤ t |
| **Observability** | ADR-0011 |
| **Version** | DESIGN |
| **Compatibility** | Reject future PBP/quotes in live-available set |
| **SoT** | ADR-0011 |

---

## 14. ModelArtifact

| | |
|--|--|
| **Purpose** | Trained model bytes + dataset/feature/hyperparam versions |
| **Owner** | CTO-W10 / registry CTO-W11 |
| **Producer** | Experiment runs |
| **Consumers** | Validation; never auto-production |
| **Mutability** | Immutable once registered |
| **Required** | model_id, version, dataset_version, status RESEARCH→… |
| **Optional** | — |
| **Timestamps** | train window recorded |
| **Observability** | Predictions are MODELED |
| **Version** | DESIGN |
| **Compatibility** | ADR-0013 promotion; ML is not historical truth |
| **SoT** | PLAN-W24 |

---

## 15. Experiment

| | |
|--|--|
| **Purpose** | Versioned override vs FIRST01 v1 **control** |
| **Owner** | CTO-W10 |
| **Producer** | Experiment framework |
| **Consumers** | Validation, registry |
| **Mutability** | Append-only experiment rows |
| **Required** | control always reported; isolated overrides |
| **Forbidden** | silent write to `strategies/mlb` |
| **Version** | DESIGN |
| **SoT** | PLAN-W18 |

---

## 16. Prediction

| | |
|--|--|
| **Purpose** | Model output (probabilities, expected MAE, etc.) |
| **Owner** | CTO-W10 |
| **Producer** | Models |
| **Consumers** | Research; future RiskInput only via W11 + Risk engine |
| **Mutability** | Experiment-scoped |
| **Required** | MODELED; model_version; as-of t |
| **Forbidden** | bypassing Risk |
| **Version** | DESIGN |
| **SoT** | `crates/prediction` is a stub — not this contract |

---

## 17. RiskInput

| | |
|--|--|
| **Purpose** | Interface to production Risk Decision Engine |
| **Owner** | CTO-W11 (design). **Production Risk crate UNTOUCHED** |
| **Producer** | Future bridge |
| **Consumers** | `crates/risk` (only after live-safety auth) |
| **Mutability** | FROZEN production behavior |
| **Required** | cannot create exposure without Risk |
| **Version** | DESIGN; FORBIDDEN to implement wiring by default |
| **SoT** | AGENTS.md hierarchy |

---

## 18. ExecutionInput

| | |
|--|--|
| **Purpose** | Approved intent → order path |
| **Owner** | CTO-W11 design; production execution UNTOUCHED |
| **Producer** | Future bridge |
| **Consumers** | `crates/execution` / Kalshi venue (only after auth) |
| **Required** | paper vs live isolation; no accidental live |
| **Version** | DESIGN; FORBIDDEN by default |
| **SoT** | trading safety rules |

---

## 19. Downstream path / theta requirements (register only)

Not implemented by the control agent. Owner: CTO-W5 (path store), CTO-W8 (theta estimators).

For a first-80% observation the **eventual** dataset must be able to retain **where available**:

- contract starting price; Team A start; Team B start
- market path to observation; event/PBP path to observation
- game state at observation
- event theta path; market theta path
- deltas, volatility (versioned empirical, not OBSERVED formulas)
- liquidity, spread, depth **where actually observable**
- threshold crossing history

If a field is not in source: UNAVAILABLE + reason. Do not implement here.

---

## 20. W1 DRAFT-IN-USE types (binding for W2 readers)

W2 **reads**, does not fork:

| Type | File |
|------|------|
| `LakeCatalogV1` / `LakeFileEntry` | `foundation/catalog.rs` |
| `CoverageRecord` / `PartitionCoverage` | `foundation/coverage.rs` |
| `RawEnvelopeV2` | `foundation/envelope_v2.rs` |
| `IdentityStubV1` | `foundation/identity_stub.rs` |
| `ObservabilityKind` | `foundation/observability.rs` |
| `StartingPriceClass` | `foundation/starting_price.rs` |
| `RawArtifactRef` / `RawMarketIdentity` | `foundation/w2_contract.rs` (**W1-owned**) |

`PARTITION_COMPLETE_V1` ≠ PBP-complete ≠ lifetime-complete ≠ L2-complete.
