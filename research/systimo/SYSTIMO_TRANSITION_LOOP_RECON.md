# Systimo transition loop — recon

Systimo owns/operates the audited transition loop. Not a second database.

```text
CSV SSOT = research/systimo/
SHA-256 artifacts already exist
QUERY_TYPES have no TRANSITION_* yet
Orchestra app does not exist
```

## Today

16 tables in [`schema.py`](../../ROLLER/roller/systimo/store/schema.py).
Append-only: connection_events, health_snapshots, agent_runs, action_runs.
Hash: `hashlib.sha256` on artifact bodies and CSV bytes.
Query types: systems, connections, dependencies, reverse_dependencies,
datasets, interfaces, health, artifacts, provenance, paths, path_back,
drift, governance.

No `trace_id` SSOT in DRE/PM/momento.

PM edges DECLARED DENY. Jump data plane has Ballhog/TK Ultra reads,
not Positman/Drevo.

## V0 add

CSV tables `transition_traces`, `transition_events` (append-only),
`transition_sources`. Register in schema.py. Hash chain per event.
Query types for traces + `ORCHESTRA_CONTEXT`. Same `:5193` UI.

Orchestra = `system_orchestration` product name, lifecycle DECLARED.
No Orchestra Vite app. Orchestra queries Systimo only.
