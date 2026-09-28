# CTO-W2 — MLB Event / PBP Reconstruction

**Status:** W2-E/W2-B complete on StatsAPI 2026-06-18..30. 2025 PBP = `MISSING_HISTORICAL_SOURCE`. Event Theta value deferred (W9).  
**Owner:** W2 implementation agent (`crates/research-event`)

This directory is the control-plane documentation package. Closeout: [../W2_COMPLETION_REPORT.md](../W2_COMPLETION_REPORT.md).

| Doc | Role |
|-----|------|
| [SPEC.md](SPEC.md) | Objective, inputs, outputs |
| [DEPENDENCIES.md](DEPENDENCIES.md) | Upstream / downstream / blockers |
| [CONTRACTS.md](CONTRACTS.md) | Contracts owned or consumed |
| [ACCEPTANCE.md](ACCEPTANCE.md) | Done-when |
| [PROGRESS.md](PROGRESS.md) | Ledger pointer |

**Data truth:** 174 official PBP games (StatsAPI) live under `Foundation/W2/raw/statsapi/` — **not** Data-Real. 2025 PBP, historical L2, and proven market-open remain unavailable. The 13 Kalshi COMPLETE days are still **market** coverage.

**W3:** not started.
