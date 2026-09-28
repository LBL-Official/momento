# Architecture Decision Records — Historical Research Engine

This directory is the ADR system for the MLB-first Historical Market/Game State
Backtesting & Research Engine.

## Rules

1. Every important architectural decision gets an ADR.
2. Filename: `ADR-XXXX-kebab-title.md` (zero-padded four-digit id).
3. ADRs are append-only. Supersession is recorded by a new ADR that cites the old one.
4. Do not bury decisions only in chat, code comments, or stale plans.
5. Status values: `PROPOSED` | `ACCEPTED` | `SUPERSEDED` | `DEPRECATED` | `DEFERRED`.
6. Research ADRs must not silently change production trading behavior.

## Required sections

Every ADR must contain:

- Decision
- Context
- Problem
- Alternatives Considered
- Decision Made
- Rationale
- Consequences
- Data/Model Implications
- Testing Implications
- Future Compatibility
- Status
- Date

## Index

| ID | Title | Status | Date |
|----|-------|--------|------|
| [0001](ADR-0001-raw-data-immutability.md) | Raw data immutability | ACCEPTED | 2026-08-26 |
| [0002](ADR-0002-timestamp-authority.md) | Timestamp authority | ACCEPTED | 2026-08-26 |
| [0003](ADR-0003-pbp-synchronization.md) | PBP synchronization | ACCEPTED | 2026-08-26 |
| [0004](ADR-0004-event-time-representation.md) | Event-time representation | ACCEPTED | 2026-08-26 |
| [0005](ADR-0005-mlb-54-out-representation.md) | MLB 54-out representation | ACCEPTED | 2026-08-26 |
| [0006](ADR-0006-first-80-semantics.md) | First-80 semantics | ACCEPTED | 2026-08-26 |
| [0007](ADR-0007-team-a-b-canonicalization.md) | Team A / Team B canonicalization | ACCEPTED | 2026-08-26 |
| [0008](ADR-0008-orderbook-representation.md) | Orderbook representation | ACCEPTED | 2026-08-26 |
| [0009](ADR-0009-market-theta.md) | Market theta | ACCEPTED | 2026-08-26 |
| [0010](ADR-0010-event-theta.md) | Event theta | ACCEPTED | 2026-08-26 |
| [0011](ADR-0011-feature-availability.md) | Feature availability classifications | ACCEPTED | 2026-08-26 |
| [0012](ADR-0012-no-lookahead-rules.md) | No-lookahead rules | ACCEPTED | 2026-08-26 |
| [0013](ADR-0013-model-promotion.md) | Model promotion / research–production boundary | ACCEPTED | 2026-08-26 |
| [0014](ADR-0014-google-drive-architecture.md) | Google Drive architecture | ACCEPTED | 2026-08-26 |
| [0015](ADR-0015-google-sheets-architecture.md) | Google Sheets architecture | ACCEPTED | 2026-08-26 |
| [0016](ADR-0016-primary-research-objects.md) | StateTransition and GameMarketEpisode | ACCEPTED | 2026-08-26 |
| [0017](ADR-0017-first01-as-plugin.md) | FIRST01 is a strategy plugin | ACCEPTED | 2026-08-26 |
| [0018](ADR-0018-identity-gameid-canonical.md) | Internal GameId is canonical | ACCEPTED | 2026-08-26 |
| [0019](ADR-0019-waterfall-methodology.md) | W/A/S waterfall methodology | ACCEPTED | 2026-08-26 |
| [0020](ADR-0020-observability-honesty.md) | Observability honesty | ACCEPTED | 2026-08-26 |
| [0021](ADR-0021-continuous-ingestion-plane.md) | Continuous historical + forward ingestion plane | ACCEPTED | 2026-08-26 |

Governing documents:

- [`../BACKTEST_ENGINE_WATERFALL.md`](../BACKTEST_ENGINE_WATERFALL.md)
- [`../BACKTEST_ENGINE_SYSTEM_SPECIFICATION.md`](../BACKTEST_ENGINE_SYSTEM_SPECIFICATION.md)
- [`../HISTORICAL_ENGINE_DEVELOPMENT_PLAN.md`](../HISTORICAL_ENGINE_DEVELOPMENT_PLAN.md)
