# ADR-0001 — Raw data immutability

# Decision

Raw historical source data is immutable. Parsers, normalizers, and reconstructors
never overwrite raw files. Derived layers are versioned.

# Context

The research engine will ingest Kalshi REST payloads, future PBP, settlements, and
prospective WebSocket captures. A parser bug or schema improvement must not destroy
the original evidence. The existing lake (`Backtesting Suite/Data-Real/`) already
holds gzip JSONL plus published parquet for June 2026 MLB.

# Problem

If a fix rewrites `events.jsonl.gz` or parquet in place, historical truth is lost,
checksums break, and no later reconstruction can prove what the source contained.

# Alternatives Considered

1. Mutate raw in place when a parser improves.
2. Keep a single “latest” normalized tree and discard prior transforms.
3. Immutable raw + versioned derived layers (RAW → NORMALIZED → RECONSTRUCTED →
   FEATURED → LABELED → MODELED).

# Decision Made

Alternative 3. Pipeline:

```text
RAW (immutable)
  → NORMALIZED (versioned)
  → RECONSTRUCTED (versioned)
  → FEATURED (versioned)
  → LABELED (experiment-scoped)
  → MODELED (experiment-scoped)
```

Existing v1 gzip remains `immutable_raw_kalshi_v1`. Envelope v2 is additive
(`events.v2.jsonl.gz` or equivalent), never a hash-changing overwrite of v1.

# Rationale

Accuracy and auditability beat convenience. Every derived record must be
traceable to source. This is a financial research system.

# Consequences

- Catalog and checksum jobs must fail closed on overwrite attempts.
- Disk use grows with versions.
- Waterfall 1 must register v1 hashes before any new writer exists.

# Data/Model Implications

Models train on versioned featured/labeled datasets, never by mutating raw.
Missing source is `UNAVAILABLE`, not imputed into raw.

# Testing Implications

Checksum replay, non-overwrite fail-closed, v1 schema round-trip, and
no-synthetic-rows tests are Waterfall 1 acceptance gates.

# Future Compatibility

Later sports and PBP sources append new raw trees. They do not rewrite Kalshi v1.

# Status

ACCEPTED

# Date

2026-08-26
