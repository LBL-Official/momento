# CTO-W3 DEPENDENCIES

**Upstream:** W1 (ACCEPTED/CLOSED), W2 event engine, DATA-INGEST committed handoff  
**Downstream:** W4 Kalshi market reconstruction (not started)

## Blocking

None for the observed 2026-06-18..30 committed window.

## Not blocking W3 closeout

Full 2024–2025 / 2025–2026 PBP on disk. Those windows are reported **UNAVAILABLE** locally, not fabricated COMPLETE.

## Parallelism

DATA-INGEST may acquire more committed partitions. W3 consumes them on subsequent runs. W3 does not own the scheduler.
