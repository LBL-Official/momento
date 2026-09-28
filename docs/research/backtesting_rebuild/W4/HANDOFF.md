# W4 → W5 handoff

W5 is **event ↔ market time synchronization**.

W4 provides:

- per-contract `MarketPath` (observed points + honest completeness)
- coupled two-YES episodes with explicit missing side
- identity **as consumed** (MAPPED / UNMATCHED / AMBIGUOUS)
- coverage and blocker lists

W5 must **not** treat a W4 path as synchronized to PBP. A path can exist with
`event_state = UNAVAILABLE`. Sync quality is a W5 contract (ADR-0003).

W4 does not emit `SynchronizedState`.
