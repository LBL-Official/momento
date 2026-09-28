# ADR-0014 — Google Drive architecture

# Decision

Google Drive is the **human-readable research archive**, not the canonical raw
warehouse. Raw data stays on the lake (and later object storage). Drive stores
aggregates, reports, and run packages.

# Context

LEGACY_V1 already uses Drive folder `1WKopI1xCPIHQ7yuPs3X10M5EFVhvvZlL` and
FIRST01 Runs folder. MCP Drive is the documented write path. No secrets in repo.

# Problem

Uploading gzip ticks to Drive would make a spreadsheet/folder the source of
truth, break immutability, and mix demo with real.

# Alternatives Considered

1. Drive as canonical lake.
2. No Drive; machine artifacts only.
3. Lake canonical; Drive human archive after the reporting layer exists.

# Decision Made

Alternative 3. Canonical hierarchy:

```text
RAW DATA
  → canonical database / object storage
  → research artifacts
  → Google Drive human-readable archive
  → Google Sheets executive/research index
```

Organization:

```text
SPORT → YEAR → DATASET → RUN → WATERFALL → EXPERIMENT
```

Drive is **not optional** after Waterfall 20 is implemented. It is **not
implemented** in W0–W19 except as design.

Do not overwrite LEGACY FIRST01 run meaning; new engine uses a new tree
(`Momento Research Archive/`) plus `legacy_v1_first01/` preservation.

# Rationale

Humans need reports; machines need checksummed parquet.

# Consequences

Reporting pipeline must not call Kalshi order APIs or overwrite Data-Real.
Every major research phase eventually produces methodology, assumptions,
limitations, experiment ids, dataset/model versions.

# Data/Model Implications

Drive copies are not inputs to training.

# Testing Implications

W20: artifact names labeled LEGACY_V1 vs new-engine; no raw-tick warehouse tests.

# Future Compatibility

Cloud object storage can replace local lake as machine canonical without
changing Drive’s role.

# Status

ACCEPTED (implementation deferred to Waterfall 20)

# Date

2026-08-26
