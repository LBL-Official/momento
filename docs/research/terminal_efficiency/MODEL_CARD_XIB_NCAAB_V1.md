# Model card — XIB-NCAAB-V1

**Status:** FROZEN among evaluated 2024–25 VAL candidates for the **P5-vs-P5 verified-PBP universe only**.

| Field | Value |
|-------|-------|
| Purpose | Calibrated P(home win \| information at t) for NCAAB research |
| Universe | **In-game XIB: P5-vs-P5 with verified PBP only.** Dataset A may include D1 schedule/finals without PBP. Those rows must not receive in-game XIB. |
| Training data | ESPN D1 6,299 games; 816 P5 PBP files → Dataset B 71,108 obs. VAL n=15,546 |
| Selected model | **model1_plus_pregame** (prior win% / last-5). Net rating and pace UNAVAILABLE (no box lines) |
| VAL Brier | Model 0: 0.1577 · **Model 1: 0.1513** · Model 2: 0.1513 (no material gain) |
| MODEL 3 | **NOT RUN** (`libomp`). Best among evaluated candidates only. |
| 2025–26 OOS | **not run — Phase 7 gated** |
| Data gaps | 2024–25 Kalshi MISSING. KenPom MISSING. Non-P5 PBP not fabricated. |
| Consumer rule | non-P5 / missing PBP → `XIB UNAVAILABLE` (null). Null > fabricated coverage. |
| Prohibited uses | Apply in-game XIB to the full D1 Kalshi universe; live trading; edge claims |

Pregame-only, if used later, is a **separate object**.
