# WATERFALL_DEPENDENCY_GRAPH.md

**Execution graph (authorization sequence):**

```text
CTO-W0 → CTO-W1 → CTO-W2 → CTO-W3 → CTO-W4 → CTO-W5 → CTO-W6 → CTO-W7 → CTO-W8 → CTO-W9 → CTO-W10 → CTO-W11
```

This is the **control** order. It is not a claim that every byte of W(n+1) must wait for W(n) COMPLETE when the parallel rules apply.

PLAN 0–26 mapping: [WATERFALL_ALIAS_CROSSWALK.md](WATERFALL_ALIAS_CROSSWALK.md).

---

## 1. Serial meaning (what actually depends on what)

```text
CTO-W0  recon + contracts (docs)
   │
   ▼
CTO-W1  immutable catalog / provenance / coverage honesty
   │
   ├────────────────────────────┐
   ▼                            ▼
CTO-W2  EVENT domain            CTO-W3  MARKET domain
        GameState / PBP                 MarketState both sides
        (PBP may be UNAVAILABLE)        (L2 may be UNAVAILABLE)
   │                            │
   └────────────┬───────────────┘
                ▼
           CTO-W4  Event ↔ Market sync (confidence never upgraded)
                │
                ▼
           CTO-W5  StateTransition (atomic) in GameMarketEpisode (container)
                │
                ▼
           CTO-W6  FIRST01 plugin replay + MODELED execution
                │
                ▼
           CTO-W7  80% research + outcome labels + classification
                │
                ├──────────────┐
                ▼              ▼
           CTO-W8  Greeks /    CTO-W9  microstructure
                   features            (mostly UNAVAILABLE historically)
                │              │
                └──────┬───────┘
                       ▼
                  CTO-W10  ML / XGB / MC / HPO / validation
                       │
                       ▼
                  CTO-W11  Drive/Sheets/registry/bridge
                           (production wiring separately gated)
```

**Hierarchy (inviolable):**

```text
RAW → NORMALIZED → EVENT STATE → MARKET STATE → STATE TRANSITION
  → STRATEGY REPLAY → SIGNAL → ORDER → FILL → POSITION → OUTCOME
```

`StateTransition` is atomic. `GameMarketEpisode` is the container. FIRST01 is a plugin. A trade is downstream.

---

## 2. Legitimate parallelism (not convenience)

Parallelism requires: stable contracts, no unfinished implementation outputs as inputs, no shared mutable files, no historical-coverage claims, no contradictory downstream semantics.

| Parallel pair | Allowed now? | Why / why not |
|---------------|--------------|----------------|
| **W1 impl ∥ W2 contracts/fixtures** | **YES** | W2 can design `GameState`/`PBPEvent` and FIXTURE streams without W1 COMPLETE. W2 cannot claim PBP availability. W1 handoff types are read-only. |
| W1 impl ∥ W2 **real PBP reconstruction** | **NO** | PBP UNAVAILABLE; license not approved. Would fabricate or scrape. |
| W1 impl ∥ W3 market **implementation** | **NO** | W3 not authorized. Also should consume catalog coverage flags. |
| W2 contracts ∥ W3 contracts | **YES (docs only)** | Independent domains. Neither may define `SynchronizedState`. |
| W2 impl ∥ W3 impl | **YES later**, after auth | Independent reconstruction; join is W4. |
| W5/W6 **contracts** ∥ W1/W2 | **YES** | Schemas/fixtures only; no completeness claims. |
| W4 sync ∥ W2/W3 impl | **NO** | Sync consumes both reconstructed streams (or explicit UNAVAILABLE sides). |
| W6 FIRST01 replay ∥ W5 engine | **NO** | Plugin walks transitions; engine must exist. |
| W7 classification ∥ W6 | **Partial later** | Labels need paths; must not retune FIRST01. |
| W8 greeks ∥ W9 book | **Later, limited** | Greeks need paths (W5). Book features need OBSERVED depth (historically UNAVAILABLE). |
| W10 ML ∥ anything earlier | **NO** | Dataset must be trustworthy. |
| W11 production bridge ∥ research | **NO** | Separate CEO live auth. |
| Any W ∥ production edits | **NO** | Fence. |

---

## 3. Current parallel authorization (2026-08-26, updated after W3 grant)

The 2026-08-26 W3 grant remaps execution names vs the serial diagram above:

```text
CTO-W3  MLB game/PBP reconstruction layer (reuses W2 engine; IMPLEMENTING)
CTO-W4  Kalshi market reconstruction (NOT STARTED)
CTO-W5  Event ↔ market time sync (NOT STARTED)
```

```text
COMPLETE:   CTO-W0, CTO-W1 ACCEPTED/CLOSED, CTO-W2 engine (observed window),
            CTO-W3 ACCEPTED/CLOSED
ACTIVE:     DATA-INGEST waterstream (CODE READY / BACKFILL_PARTIAL / not deployed)
NOT ACTIVE: CTO-W4–W11 implementation
```

---

## 4. Blocking conditions (dependency, not preference)

| Downstream | Blocked by |
|------------|------------|
| W2 official `mlb_game_pk` mapping | No authorized schedule/PBP source |
| W2 reconstructed GameState from real games | Same + no local PBP files |
| W3 lifetime starting prices as OBSERVED | v1 partitions are close-day; lifetime collect not authorized (PLAN-W1-A8 DEFERRED) |
| W3 FULL_L2 MarketState | Historical L2 UNAVAILABLE |
| W4 EXACT sync | Needs event timestamps **and** market timestamps |
| W5 historical episodes | Needs W1 catalog + W3 paths; event side may be UNAVAILABLE |
| W6 live-equivalent fills | Needs book quality ≠ CANDLESTICK_ONLY |
| W8 event theta values | Needs W2 event state (else UNAVAILABLE) |
| W9 historical microstructure | Needs OBSERVED book |
| W10 | Needs W7 labels + W19-style validation protocol |
| W11 production wiring | Explicit live-safety authorization |

---

## 5. Adapter plug-in points (no premature NBA implementation)

Core (future, W5-owned interfaces; W2 implements MLB adapters):

```text
SportAdapter
GameStateAdapter
PBPAdapter
MarketAdapter      (W3)
OutcomeAdapter
FeatureAdapter     (W8)
```

NBA/NHL/NCAAB/NFL: **trait bounds only**. Do not implement.

---

## 6. Google reporting (not canonical truth)

```text
Raw / canonical lake  →  research artifacts  →  Google Drive archive  →  Sheets index
```

Do not implement Drive/Sheets in W1–W10 except **local** derived files. Per-W publish targets are listed in each `W#/SPEC.md`.
