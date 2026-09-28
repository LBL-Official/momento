# DATA-INGEST README

Cross-cutting **MLB waterstream**: historical partition + forward feed + Kalshi
discovery landing. Not W4. Does not reconstruct `MarketState`.

- Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
- Operator runbook: [OPERATOR_RUNBOOK.md](OPERATOR_RUNBOOK.md)
- Waterstream report: [WATERSTREAM_REPORT.md](WATERSTREAM_REPORT.md)
- Prior infra note: [IMPLEMENTATION_REPORT.md](IMPLEMENTATION_REPORT.md)
- ADR: [../../architecture-decisions/ADR-0021-continuous-ingestion-plane.md](../../architecture-decisions/ADR-0021-continuous-ingestion-plane.md)

Crate: `crates/research-ingest` (`INGEST.2.0.0`)  
Binary: `apps/research-ingest` (`schedule-info`, `plan-windows`, `cloud-spec`, `run`, `backfill`, `weekly`, `replay`)

**Status:** CODE READY. Cloud **IMPLEMENTED_NOT_DEPLOYED**. Historical backfill **not** complete.
