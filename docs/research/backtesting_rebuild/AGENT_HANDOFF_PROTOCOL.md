# AGENT_HANDOFF_PROTOCOL.md

Every implementation agent must be able to answer these ten questions from the control plane **before writing code**. If any answer is “unclear,” STOP and record a blocker in `W#/PROGRESS.md`.

---

## 1. What am I authorized to build?

Read:

- [WATERFALL_MASTER_REGISTRY.md](WATERFALL_MASTER_REGISTRY.md) → your CTO-W# **authorization state**
- [PARALLEL_RULES.md](PARALLEL_RULES.md) §9
- Your `W#/README.md`

| If your W is… | You may… |
|---------------|----------|
| CTO-W1 IMPLEMENTING | Catalog, provenance, coverage, envelope v2, identity stub, integrity, derived artifacts **outside** Data-Real |
| CTO-W2 READY_FOR_CONTRACT_WORK / parallel | Schemas, adapter traits, synthetic fixtures, identity-graph **design**, UNAVAILABLE event-state labeling |
| CTO-W2 reconstruction of real PBP | **Not** until license + source + W1 catalog evidence |
| CTO-W3–W11 | Nothing in code unless the registry says otherwise. W5/W6: contracts/fixtures only |

You are **never** authorized to: mutate production, rewrite Data-Real, fabricate PBP/L2/2025 days, retune FIRST01, or advance a waterfall to COMPLETE without evidence.

---

## 2. What files do I own?

Read [FILE_OWNERSHIP_REGISTRY.md](FILE_OWNERSHIP_REGISTRY.md).

- Edit only files listed under your CTO-W# **or** newly created files you register there first.
- If the file is UNTOUCHED, LEGACY_V1 (no-extend), COORDINATED_SHARED, or owned by another W: **do not edit**.

---

## 3. What contracts are frozen?

Read [WATERFALL_CONTRACT_REGISTRY.md](WATERFALL_CONTRACT_REGISTRY.md).

Current freeze classes:

| Contract | Freeze | Owner |
|----------|--------|-------|
| FIRST01 v1 parameters (80/81/83/89/50%, one GameId lifecycle) | FROZEN (plugin control) | Production + W0 recon; W6 consumes |
| Observability vocabulary (OBSERVED/DERIVED/INFERRED/MODELED/UNAVAILABLE/LABEL_ONLY) | FROZEN (ADR-0011) | Control / W1 implements |
| Raw Data-Real v1 gzip/parquet/manifests | IMMUTABLE | No agent |
| `LakeCatalogV1` / `RawEnvelopeV2` / `IdentityStubV1` | DRAFT-IN-USE (W1 code) | W1 — version before semantic change |
| `GameState` / `PBPEvent` / `StateTransition` / `GameMarketEpisode` | DESIGN-ONLY (W0 domain model) | W2 / W5 as assigned — not implemented |

Do not silently extend a frozen enum with a new meaning.

---

## 4. What dependencies are satisfied?

Read [WATERFALL_DEPENDENCY_GRAPH.md](WATERFALL_DEPENDENCY_GRAPH.md) and `W#/DEPENDENCIES.md`.

Satisfied **now**:

- W0 recon + governance baseline = COMPLETE
- W1 implementation authorization = GRANTED
- W2 contract-parallel authorization = GRANTED

**Not** satisfied:

- Verified W1 catalog run over Data-Real with independent COMPLETE evidence (job may exist; control plane has not accepted COMPLETE)
- PBP source/license
- Historical L2
- Lifetime starting prices
- Event↔market sync engine
- Canonical `StateTransition` store

---

## 5. What data is actually available?

Authoritative until W1 catalog supersedes with checksums:

[DATA_INVENTORY.md](DATA_INVENTORY.md)

| Dataset | Available? |
|---------|------------|
| Kalshi MLB Data-Real 2026-06-18…30 (13 COMPLETE **partition** days) | YES — trades + 1-min candles + metadata + PIT ingest snapshots |
| Meaning of v1 COMPLETE | Close/settled PT-day collect — **not** lifetime, not L2, not PBP |
| 2025 MLB Kalshi | NO (PROBE_EMPTY) |
| 2026 outside those 13 days | NO (Jun 1–17 probed empty; rest not attempted here) |
| MLB PBP | NO |
| Historical L2 | NO |
| Market-open starting price | NOT GUARANTEED / UNAVAILABLE as proven open |
| Demo `Backtesting Suite/Data` | NOT HISTORY |

Filenames are not evidence.

---

## 6. What am I prohibited from touching?

From [REWRITE_BOUNDARY.md](REWRITE_BOUNDARY.md) and this control plane:

**UNTOUCHED (production):**

- `strategies/mlb/**`, `strategies/wnba/**`
- `crates/risk/**`, `crates/execution/**`, `crates/positions/**`, `crates/pnl/**`
- `apps/trading-engine/**`
- `config/live.toml`, `config/paper.toml`
- `deploy/momento-live.service`, `momento-paper.service`, live secret/auth scripts
- `crates/kalshi/src/{production,venue,transport,auth,ws,sandbox,secret,http}.rs`

**IMMUTABLE:**

- `Backtesting Suite/Data-Real/**` raw gzip, parquet, manifests (no overwrite, no silent repair, no delete)

**DO NOT EXTEND AS PLATFORM:**

- `crates/research-backtest` candle FIRST01 runner (LEGACY_V1)
- Treating `orderbook.parquet` as L2

**Shared core:** `crates/core/**` — default UNTOUCHED. Additive research types only with explicit control-plane approval (must not change money, `can_attempt_entry`, or 80/81 meaning).

---

## 7. What acceptance tests must pass?

See `W#/ACCEPTANCE.md` and PLAN registry test columns where aliased.

W1 minimum (from W0-A10 spec, still binding):

- checksum replay vs manifests
- v1 schema round-trip
- no_synthetic_rows
- demo ≠ real
- envelope v2 missing `source_timestamp` allowed with reason; `received_at` never copied to exchange time
- non-overwrite fail-closed
- observability: PIT RestSnapshot = ingest-time; candles = CANDLESTICK
- production fence
- no invented 2025 games

W2 minimum (contract phase):

- `mlb_game_pk` remains null unless mapped from an authorized official source
- synthetic PBP fixtures labeled FIXTURE
- no claim that PARTITION_COMPLETE_V1 ⇒ event-complete
- GameState replay view has no eventual winner

---

## 8. Where must I document progress?

1. `docs/research/backtesting_rebuild/W#/PROGRESS.md`
2. `docs/research/completions/{CTO-or-PLAN-step-id}.md` using [`../templates/WATERFALL_STEP_COMPLETION.md`](../templates/WATERFALL_STEP_COMPLETION.md)
3. Do **not** mark the PLAN CSV complete with colliding W1-ledger IDs
4. Do **not** edit control-plane registries except via the control agent

---

## 9. What evidence must I leave behind?

For every completed S-step:

| Field | Required |
|-------|----------|
| step ID (namespaced) | Yes |
| date/time UTC | Yes |
| agent | Yes |
| files changed | Yes |
| implementation summary | Yes |
| tests run / tests passed | Yes |
| artifacts generated (paths) | Yes |
| Data-Real hashes unchanged (if lake was read) | Yes |
| blockers | Yes (or “none”) |
| next step | Yes |
| Drive/Sheets | `NO` until CTO-W11 reporting; local derived artifacts OK |

Never mark complete without evidence. A ledger that auto-completes every ID in one function is **not** independent evidence ([CTO_REVIEW_FLAGS.md](CTO_REVIEW_FLAGS.md) FLAG-002).

---

## 10. What must I hand off to the next agent?

Write in `W#/PROGRESS.md`:

```text
HANDOFF
  from: CTO-W#
  to:   CTO-W# (or STOP)
  frozen_contracts: …
  artifacts: paths + checksums
  data_still_unavailable: PBP / L2 / starting price / 2025 / …
  files_you_must_not_edit: …
  known_flags: link CTO_REVIEW_FLAGS IDs
  next_authorized_step: …
```

W1 → W2 handoff **minimum**:

- `LakeCatalogV1` (or documented equivalent) distinguishing DEMO vs REAL, PROBE_EMPTY vs PARTITION_COMPLETE_V1 vs NOT_ATTEMPTED
- `RawArtifactRef` + checksums
- `IdentityStubV1` with `mlb_game_pk = null`
- Explicit UNAVAILABLE: PBP, L2, proven market-open price
- Promise that W2 must not rewrite raw

Then **STOP** unless the execution instruction authorizes the next S-step.
