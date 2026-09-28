# Historical Engine Rebuild — Control Plane + Waterfall 0 Recon

**Control-plane status:** ACTIVE (2026-08-26)  
**Execution authority:** CTO 11-waterfall graph (W0–W11)  
**Planning reference:** [`../HISTORICAL_ENGINE_DEVELOPMENT_PLAN.md`](../HISTORICAL_ENGINE_DEVELOPMENT_PLAN.md) (W0–W26) — **not replaced**  
**W0 recon artifacts:** FROZEN / COMPLETE — do not rewrite

This directory now contains two layers:

1. **Control plane** (this rewrite’s orchestration authority)
2. **Waterfall 0 reconnaissance** (approved audit package; linked, not rewritten)

---

## Control plane (read this first)

| Document | Purpose |
|----------|---------|
| [WATERFALL_MASTER_REGISTRY.md](WATERFALL_MASTER_REGISTRY.md) | W0–W11 status, auth, ownership, acceptance |
| [WATERFALL_DEPENDENCY_GRAPH.md](WATERFALL_DEPENDENCY_GRAPH.md) | Serial graph + legitimate parallelism |
| [WATERFALL_CONTRACT_REGISTRY.md](WATERFALL_CONTRACT_REGISTRY.md) | Canonical contracts and freeze rules |
| [PARALLEL_RULES.md](PARALLEL_RULES.md) | What may run concurrently |
| [AGENT_HANDOFF_PROTOCOL.md](AGENT_HANDOFF_PROTOCOL.md) | Ten questions every implementation agent must answer |
| [WATERFALL_ALIAS_CROSSWALK.md](WATERFALL_ALIAS_CROSSWALK.md) | CTO W0–W11 ↔ Plan W0–W26 |
| [FILE_OWNERSHIP_REGISTRY.md](FILE_OWNERSHIP_REGISTRY.md) | Exclusive file owners |
| [CTO_REVIEW_FLAGS.md](CTO_REVIEW_FLAGS.md) | Observed conflicts (do not silently “fix” in control) |
| [PROGRESS_LEDGER.md](PROGRESS_LEDGER.md) | Control-plane + observed W1/W2 progress |
| [W1_ACCEPTANCE_CRITERIA.md](W1_ACCEPTANCE_CRITERIA.md) | Binding W1 closeout bar (CTO) |
| [W1_ACCEPTANCE_PACKAGE.md](W1_ACCEPTANCE_PACKAGE.md) | PASS/FAIL package for CTO sign-off (NOT_AUDITED) |

Per-waterfall documentation packages: [W0/](W0/) … [W11/](W11/).  
**Directories are not implementation authorization.**

---

## Current authorization (execution)

| Waterfall | Authorization |
|-----------|----------------|
| **W0** | COMPLETE. Do not rewrite recon. |
| **W1** | Implementation granted. **VALIDATING.** Closeout bar: [W1_ACCEPTANCE_CRITERIA.md](W1_ACCEPTANCE_CRITERIA.md). Package: [W1_ACCEPTANCE_PACKAGE.md](W1_ACCEPTANCE_PACKAGE.md) **NOT_AUDITED**. Agent COMPLETE is not acceptance. |
| **W2** | Parallel **contract / fixture / adapter** work only. Historical PBP reconstruction **BLOCKED** on data + license. |
| **W3** | **Not** authorized to implement until CTO **ACCEPTS / CLOSES W1**. Then W3 may be authorized separately. |
| **W4–W11** | Not authorized to implement. W5/W6 may do contract design only. |

W1 and W2 may run in parallel **only** under [PARALLEL_RULES.md](PARALLEL_RULES.md).

---

## Data truth (do not “upgrade”)

As of W0 inventory ([DATA_INVENTORY.md](DATA_INVENTORY.md)), unless a **verified W1 catalog** proves otherwise:

| Claim | Status |
|-------|--------|
| MLB PBP | **UNAVAILABLE** |
| Historical L2 | **UNAVAILABLE** |
| Guaranteed market-open starting price | **UNAVAILABLE** |
| 2025 MLB Kalshi coverage | **UNAVAILABLE** (empty probes only) |

Do not infer availability from filenames, demo `Data/`, current API snapshots, candles, or settlement-day first rows.

Never: candle→tick, candle→L2, `received_at`→exchange timestamp, first settlement-day candle→market-open price.

---

## Frozen Waterfall 0 reconnaissance (do not rewrite)

| # | Document | Purpose |
|---|----------|---------|
| 1 | [REPOSITORY_RECONNAISSANCE.md](REPOSITORY_RECONNAISSANCE.md) | What exists in the repo |
| 2 | [CURRENT_ARCHITECTURE_MAP.md](CURRENT_ARCHITECTURE_MAP.md) | Current vs intended layers |
| 3 | [DATA_INVENTORY.md](DATA_INVENTORY.md) | Local 2025–2026 MLB/Kalshi holdings |
| 4 | [FIRST01_BASELINE_SEMANTICS.md](FIRST01_BASELINE_SEMANTICS.md) | Frozen live-aligned FIRST01 rules |
| 5 | [REWRITE_BOUNDARY.md](REWRITE_BOUNDARY.md) | Preserve / wrap / replace / deprecate / untouched |
| 6 | [PROPOSED_CANONICAL_DOMAIN_MODEL.md](PROPOSED_CANONICAL_DOMAIN_MODEL.md) | Dual-domain + sync + provenance |
| 7 | [MLB_DATA_RECONSTRUCTION_REQUIREMENTS.md](MLB_DATA_RECONSTRUCTION_REQUIREMENTS.md) | MLB event-domain reconstruction |
| 8 | [KALSHI_DATA_OBSERVABILITY_MATRIX.md](KALSHI_DATA_OBSERVABILITY_MATRIX.md) | What Kalshi can and cannot provide |
| 9 | [GOOGLE_REPORTING_ARCHITECTURE.md](GOOGLE_REPORTING_ARCHITECTURE.md) | Drive/Sheets as human archive |
| 10 | [WATERFALL_NEXT_STEP.md](WATERFALL_NEXT_STEP.md) | W1 spec as of W0-A10 (**historical**; W1 is now authorized) |

W0-A10 said “do not implement W1 yet.” That authorization is **superseded** by CEO/CTO authorization of W1 implementation. The W0 document itself is not rewritten.

Related governance (Plan 0–26 numbering — planning reference, not execution IDs):

- [`../BACKTEST_ENGINE_WATERFALL.md`](../BACKTEST_ENGINE_WATERFALL.md)
- [`../BACKTEST_ENGINE_SYSTEM_SPECIFICATION.md`](../BACKTEST_ENGINE_SYSTEM_SPECIFICATION.md)
- [`../BACKTEST_ENGINE_WATERFALL_REGISTRY.csv`](../BACKTEST_ENGINE_WATERFALL_REGISTRY.csv)
- [`../BACKTEST_ENGINE_CURRENT_STATE.md`](../BACKTEST_ENGINE_CURRENT_STATE.md)
- [`../architecture-decisions/`](../architecture-decisions/)

**Numbering collision:** Plan “W2” is identity; CTO “W2” is MLB event/PBP. Always prefix **CTO-W#** or **PLAN-W#**. See [WATERFALL_ALIAS_CROSSWALK.md](WATERFALL_ALIAS_CROSSWALK.md).
