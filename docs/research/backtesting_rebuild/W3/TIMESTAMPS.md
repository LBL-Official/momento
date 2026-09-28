# Timestamps

| Clock | Role |
|-------|------|
| source event time | PBP official (`startTime`/`endTime`) when present |
| retrieved_at / collector | ingest wall clock — **not** event time |
| Kalshi trade time | **forbidden** as PBP time (W5) |

If source event time is absent: `DataField::Unavailable`. Never fill from market clocks.
