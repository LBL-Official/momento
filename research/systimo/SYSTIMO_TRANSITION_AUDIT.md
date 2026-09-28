# Systimo transition audit

Systimo owns the audited transition loop. CSV SSOT under `research/systimo/transitions/`.

Tables: `transition_traces`, `transition_events` (append-only), `transition_sources`.
Hash: SHA-256 of canonical JSON payload chained to `previous_event_hash`.
Tamper of the previous pointer is `HASH_MISMATCH`. Do not regenerate to hide it.

Locked schemas live in `ROLLER/roller/systimo/transitions/types.py`.
Missing is `UNAVAILABLE`, never `$0`.
