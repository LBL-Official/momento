# FIRST78 Live V1 — performance

No p50/p95/p99 figures are published here. They were not measured on a production host or a recorded feed in this increment.

Intended instruments (when a supervised run is CONNECTED):

- signal → durable intent → (blocked send while compiled out)
- fill → position update
- exit trigger → intent
- recon lag
- ingest / outbox / alert queue depth

A 1-contract fixture is not 1,500-contract impact evidence.
Do not treat dashboard latency as an SLO.
