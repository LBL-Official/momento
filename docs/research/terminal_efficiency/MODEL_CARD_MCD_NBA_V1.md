# Model card — MCD-NBA-V1

**Status:** `PROTOTYPE EVALUATED · NOT SELECTED · LIMITED VALIDATION COVERAGE`

| Field | Value |
|-------|-------|
| Purpose | Generative remaining-game simulator (separate object from XIB) |
| Assumptions | Poisson remaining possessions from prior pace; 0/2/3 PMF from ORTG vs opp DRTG; no foul/bonus/timeout; tied leftover = one extra pair |
| Simulations | 200 per evaluated row |
| VAL evidence | **800-row sample only** — not the full 90,380 VAL population |
| Sample Brier | 0.1815 vs XIB 0.1596 on the full VAL |
| Conclusion | Did **not** demonstrate competitiveness on the tested 800-row sample. **No ensemble.** Not a definitive rejection of MCD on the full VAL. |
| 2025–26 OOS | **not run — Phase 7 gated** |
| Intended use | Research comparison object |
| Prohibited uses | Live trading, automatic blend with XIB, treating the 800-row score as a full-population result |

XIB_t, MCD_t, and K_t remain three objects.
