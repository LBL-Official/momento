# PARALLEL_RULES.md

**Audience:** every implementation agent.  
**Default:** not parallel. Parallelism is allowed only when this document says so.

---

## 1. What may run concurrently (now)

### 1.1 W1 implementation ∥ W2 contract work

**Allowed.** Conditions:

| Condition | Required |
|-----------|----------|
| W1 exclusive files untouched by W2 | Yes |
| W2 exclusive files untouched by W1 | Yes |
| W2 does not claim historical PBP/L2/2025 coverage | Yes |
| W2 does not treat demo fixtures as history | Yes |
| W2 consumes W1 handoff types as **read-only** (`RawArtifactRef`, `RawMarketIdentity`, `IdentityStubV1`) | Yes |
| W2 does not edit `crates/research-data/src/foundation/**` | Yes |
| Shared files (`lib.rs`, collector `main.rs`) follow §4 | Yes |

W2 **implementation of real event reconstruction** remains blocked on: licensed PBP/schedule source **and** a W1 catalog that does not fabricate missing history. Synthetic fixtures are not that catalog.

### 1.2 Contract-only work on W5 / W6 (not implementation)

**Allowed** in parallel with W1/W2 **only** for:

- interface definitions
- schemas
- synthetic fixtures labeled `FIXTURE`
- documentation
- dependency analysis

**Forbidden:** claiming `StateTransition` historical completeness; implementing FIRST01 replay against reconstructed paths; changing live 80/81/83/89/50%.

### 1.3 Not parallel merely because it is convenient

W3 market reconstruction **implementation** is not authorized until W1 is **ACCEPTED / CLOSED** and the CTO grants W3. Green W1 tests do not authorize W3.  
W4 sync **implementation** depends on CTO-W2 **and** CTO-W3 outputs.  
W6 FIRST01 replay **implementation** depends on CTO-W5.  
W10 ML depends on a trustworthy labeled dataset (CTO-W7+).

---

## 2. What may not run concurrently

| Pair | Why |
|------|-----|
| Two agents on the same exclusive file | Ownership violation |
| W2 + W4 both defining `SynchronizedState` | W4 owns sync; W2 only preserves join keys |
| W3 + W9 both inventing L2 from candles | Data hallucination |
| Any research agent + production strategy/risk/execution/live config | Production contamination |
| W1 catalog writer + any agent rewriting Data-Real | Immutability |
| W6 plugin + W7 classifier changing FIRST01 v1 constants | Baseline freeze |
| PLAN-W# agent and CTO-W# agent using unprefixed IDs | Numbering collision |

---

## 3. File ownership rules

1. Every implementation file has **exactly one** owning waterfall (see [FILE_OWNERSHIP_REGISTRY.md](FILE_OWNERSHIP_REGISTRY.md)).
2. If two agents need the same file: **stop**. Record BLOCKED. Do not guess a merge.
3. New files must be registered **before** the second agent depends on them.
4. Documentation under `docs/research/backtesting_rebuild/W#/` is owned by that waterfall.
5. Control-plane files (`WATERFALL_*.md`, `PARALLEL_RULES.md`, `CTO_REVIEW_FLAGS.md`, …) are owned by the **CTO control agent**. Implementation agents may append evidence links only via their `W#/PROGRESS.md`.
6. `Backtesting Suite/Data-Real/**` is owned by **no implementation agent**. Read-only. Immutable.

---

## 4. Shared-file merge protocol (bottlenecks)

These files are **COORDINATED_SHARED**. Unstructured parallel edits are forbidden.

| File | Protocol |
|------|----------|
| `crates/research-data/src/lib.rs` | W1 frozen except `pub mod foundation` + existing re-exports. W2 **must not** add event types here. W2 creates a **new crate** (`momento-research-event`, reserved) or waits for CTO to assign a single additive `pub mod event` line. |
| `apps/research-collector/src/main.rs` | W1 owns `w1-foundation` subcommand. W2 does **not** add commands here. W2 uses a new binary or waits. |
| `crates/research-data/Cargo.toml` | W1 owns additive research-data deps that foundation needs. W2 does not add event-engine deps to this crate. |
| `docs/research/BACKTEST_ENGINE_WATERFALL_REGISTRY.csv` | PLAN namespace. Control agent / W1 may add PLAN rows; must not reuse colliding IDs without alias. |

---

## 5. Contract freeze rules

1. A contract is **DRAFT** until its owner writes it to [WATERFALL_CONTRACT_REGISTRY.md](WATERFALL_CONTRACT_REGISTRY.md).
2. A contract is **FROZEN** when the owner’s waterfall marks the schema step COMPLETE with fixtures + tests.
3. Frozen contracts change only via **version bump** (`v1` → `v2`), never in-place semantic mutation.
4. Consumers must not fork a frozen contract under a new name with the same meaning.
5. W1 `RawEnvelopeV2`, `LakeCatalogV1`, `ObservabilityKind`, `IdentityStubV1`, `RawArtifactRef` are **DRAFT-IN-USE** (code exists; not control-plane COMPLETE). W2 may depend on the **documented intent**, not on undocumented extra fields.

---

## 6. Dependency rules

1. Downstream implementation may not start because upstream **types compile**.
2. Downstream may not start because **fixtures exist**.
3. Historical-coverage claims require the W1 catalog (or a later verified catalog version) as evidence.
4. If an S-step discovers a later-waterfall dependency: document it in `W#/PROGRESS.md` and **STOP that step**. Do not silently pull the later W into scope.

---

## 7. Merge rules

1. Prefer small, waterfall-scoped changes.
2. Do not rewrite LEGACY_V1 as the platform.
3. Additive derived artifacts only: new version directories, never hash-changing overwrites of raw.
4. If a merge would change production behavior, it is out of scope regardless of test greenness.
5. Control-plane docs are updated by the control agent; implementation agents update only their `W#/PROGRESS.md` and `docs/research/completions/{step_id}.md`.

---

## 8. Validation rules

A step is not COMPLETE because the compiler passed.

Required, as applicable:

- unit / schema fixture tests
- no_synthetic_rows (candles ≠ L2)
- timestamp kind tests (`received_at` ≠ exchange)
- demo ≠ real
- production fence (no `momento-risk` / `momento-execution` / `momento-strategy-mlb` deps)
- immutability (checksum of Data-Real inputs unchanged)
- no-lookahead on any plugin-visible field

Never delete a failing production test to make research work pass.

---

## 9. Authorization rules

| Work | Who authorizes |
|------|----------------|
| CTO-W1 implementation | CEO (granted). **Closeout** only via W1_ACCEPTANCE_PACKAGE + CTO sign-off |
| CTO-W1 ACCEPTED / CLOSED | CTO, after independent audit vs [W1_ACCEPTANCE_CRITERIA.md](W1_ACCEPTANCE_CRITERIA.md) |
| CTO-W2 contract / synthetic fixtures | Granted (data-truth limits). Unchanged by W1 close |
| CTO-W2 real PBP download / parse of official games | CEO + license/ToS |
| CTO-W3 Kalshi market reconstruction **implementation** | Only after W1 ACCEPTED/CLOSED **and** explicit CTO auth |
| CTO-W4…W11 implementation | Explicit later authorization |
| Kalshi re-query of empty dates (PLAN-W1-A8) | Separate CEO auth (still DEFERRED) |
| Any production / live / risk / execution change | Separate CEO live-safety authorization — **not this program** |

---

## 10. Stop conditions (agents)

Stop and hand back when:

- authorized S-step is done, tested, documented
- a shared-file collision appears
- a contract contradiction appears
- data would have to be invented to continue
- production files would have to change
- Data-Real would have to be rewritten
- the next step belongs to another waterfall

Do **not** start the next waterfall because the directory exists.
